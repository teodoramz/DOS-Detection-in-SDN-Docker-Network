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
    assert "-p \"$" not in text
    assert "SSHPASS" in text


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
