"""One command, from a workstation, brings up both hosts.

The orchestrator is the only piece that handles credentials, so these tests
mostly guard how it does that.
"""
import os
import re
import stat
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path("deploy/remote.sh")
LIB = Path("deploy/lib.sh")


def test_the_script_exists_and_is_executable():
    assert SCRIPT.is_file()
    assert os.stat(SCRIPT).st_mode & stat.S_IXUSR


def test_the_script_is_valid_bash():
    assert subprocess.run(["bash", "-n", str(SCRIPT)]).returncode == 0


def test_it_takes_both_hosts_and_says_so():
    text = SCRIPT.read_text()
    assert "--host1" in text and "--host2" in text
    assert "--clean" in text


def test_it_refuses_to_run_with_one_host():
    result = subprocess.run(["bash", str(SCRIPT), "--host1", "user@10.0.0.1"],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode != 0
    assert "host2" in (result.stdout + result.stderr).lower()


def test_help_exits_cleanly():
    result = subprocess.run(["bash", str(SCRIPT), "--help"],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0
    assert "host1" in result.stdout


def test_no_password_is_ever_passed_as_an_argument():
    """sshpass -p puts the password in the process list for every user on the
    box; -e takes it from the environment instead."""
    text = SCRIPT.read_text()
    assert "sshpass -p" not in text
    assert not re.search(r"sshpass[^\n|]*-p\s", text)
    assert "SSHPASS" in text, "the password must travel through the environment"


def test_host2_is_brought_up_before_host1():
    """host1 starts publishing captures immediately, so Kafka and the workers
    have to exist first."""
    text = SCRIPT.read_text()
    assert text.index("host2.sh") < text.index("host1.sh")


def test_it_rewrites_the_host_inventory_from_the_given_addresses():
    text = SCRIPT.read_text()
    assert "hosts.csv" in text
    assert "render_hosts_csv" in text


def test_render_hosts_csv_writes_both_addresses(tmp_path):
    out = tmp_path / "hosts.csv"
    subprocess.run(
        ["bash", "-c",
         f'source {LIB}; render_hosts_csv 10.1.1.1 10.1.1.2 "{out}"'],
        check=True, capture_output=True,
    )
    lines = out.read_text().strip().splitlines()
    assert lines[0].startswith("Name,")
    assert lines[1].startswith("host1,10.1.1.1,")
    assert lines[2].startswith("host2,10.1.1.2,")
    assert "10.255.255.254/24" in lines[1]
    assert "10.255.255.253/24" in lines[2]


def test_render_hosts_csv_keeps_the_management_addresses_stable(tmp_path):
    """Those are internal to the testbed and every script and the whitelist
    refer to them, so moving hosts must not change them."""
    out = tmp_path / "hosts.csv"
    subprocess.run(
        ["bash", "-c", f'source {LIB}; render_hosts_csv 9.9.9.9 8.8.8.8 "{out}"'],
        check=True, capture_output=True,
    )
    text = out.read_text()
    assert "10.255.255.254/24" in text and "10.255.255.253/24" in text


def test_render_hosts_csv_rejects_a_non_address(tmp_path):
    result = subprocess.run(
        ["bash", "-c",
         f'source {LIB}; render_hosts_csv not-an-ip 10.0.0.2 "{tmp_path}/h.csv"'],
        capture_output=True, text=True,
    )
    assert result.returncode != 0


def test_the_readme_documents_the_one_command_path():
    readme = Path("README.md").read_text()
    assert "deploy/remote.sh" in readme


def test_host_keys_are_verified():
    """The script sends a password over this connection. Without host-key
    pinning, the first contact can be intercepted and a swapped key is never
    noticed, so accept-new (pin on first use, refuse changes) is the floor."""
    text = SCRIPT.read_text()
    assert "StrictHostKeyChecking=no" not in text
    assert "UserKnownHostsFile=/dev/null" not in text
    assert "StrictHostKeyChecking=accept-new" in text


def test_a_known_hosts_file_can_be_supplied():
    """Re-imaged machines legitimately change keys; that has to be an explicit
    choice, not the default."""
    text = SCRIPT.read_text()
    assert "--known-hosts" in text


def test_the_known_hosts_option_appears_in_the_help():
    result = subprocess.run(["bash", str(SCRIPT), "--help"],
                            capture_output=True, text=True, timeout=30)
    assert "--known-hosts" in result.stdout


def test_the_bundle_comes_from_the_repository_not_the_working_directory():
    """`tar .` ships whatever directory the operator happened to be in."""
    text = SCRIPT.read_text()
    assert "REPO_ROOT" in text
    assert re.search(r'tar\s+[^\n]*-C\s+"\$REPO_ROOT"', text) or "ls-files" in text


def test_generated_secrets_are_not_shipped():
    """.env carries the MinIO credentials and is regenerated on each host by
    generate_env, so it has no business crossing the network."""
    text = SCRIPT.read_text()
    assert "ls-files" in text or "--exclude=.env" in text


def test_the_script_can_run_from_another_directory(tmp_path):
    """A deploy tool that only works from the repository root is a trap."""
    result = subprocess.run(
        ["bash", str(Path(SCRIPT).resolve()), "--help"],
        cwd=tmp_path, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr


def test_the_deployed_revision_is_recorded_on_the_host():
    """The bundle is a working tree, not a checkout, so a host that was once
    cloned shows the newer files as local modifications — and `git checkout .`
    there would silently revert the running system to older code."""
    text = SCRIPT.read_text()
    assert "DEPLOYED_REVISION" in text or ".deployed" in text
    assert "rev-parse" in text


def test_it_warns_when_the_host_checkout_no_longer_matches_its_git_state():
    text = SCRIPT.read_text()
    assert "git checkout" in text, "the hazard has to be named where it is seen"
