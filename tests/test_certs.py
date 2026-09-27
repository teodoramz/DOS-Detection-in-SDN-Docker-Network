"""The deploy scripts run this unattended, so it must not prompt."""
import os
import re
import stat
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path("build/certs/generate-certs.sh")


def test_script_is_executable():
    assert os.stat(SCRIPT).st_mode & stat.S_IXUSR


def test_every_prompt_sits_behind_the_non_interactive_guard():
    """A prompt reached with no terminal attached would hang the deploy."""
    text = SCRIPT.read_text()
    reads = [i for i, line in enumerate(text.splitlines()) if re.match(r"\s*read\s", line)]
    guard = next(i for i, line in enumerate(text.splitlines()) if "CERT_MODE" in line)
    assert reads, "no prompt found; this test is guarding nothing"
    assert all(i > guard for i in reads)


def test_generates_a_certificate_without_a_terminal(tmp_path):
    pytest.importorskip("subprocess")
    env = {**os.environ, "DDOS_DETECTION_HOME": str(Path.cwd()), "CERT_MODE": "1"}
    result = subprocess.run(
        ["bash", str(SCRIPT), str(tmp_path)],
        env=env, stdin=subprocess.DEVNULL,
        capture_output=True, timeout=60,
    )
    assert result.returncode == 0, result.stderr.decode()[-500:]
    assert (tmp_path / "cyberstuff.crt").is_file()
    assert (tmp_path / "cyberstuff.key").is_file()


def test_the_certificate_carries_the_expected_name(tmp_path):
    env = {**os.environ, "DDOS_DETECTION_HOME": str(Path.cwd()), "CERT_MODE": "1"}
    subprocess.run(["bash", str(SCRIPT), str(tmp_path)], env=env,
                   stdin=subprocess.DEVNULL, capture_output=True, timeout=60)
    out = subprocess.run(
        ["openssl", "x509", "-in", str(tmp_path / "cyberstuff.crt"), "-noout", "-subject"],
        capture_output=True, text=True,
    ).stdout
    assert "cyberstuff.local" in out
