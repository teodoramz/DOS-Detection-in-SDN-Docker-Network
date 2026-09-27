"""Every shell script the deploy scripts invoke must be executable in git."""
import subprocess
from pathlib import Path

import pytest

TRACKED = subprocess.run(
    ["git", "ls-files", "-s", "--", "*.sh"],
    capture_output=True, text=True, check=True,
).stdout.splitlines()

SCRIPTS = [(line.split()[0], line.split(maxsplit=3)[3]) for line in TRACKED]


@pytest.mark.parametrize("mode,path", SCRIPTS, ids=[p for _, p in SCRIPTS])
def test_tracked_script_is_executable(mode, path):
    assert mode == "100755", f"{path} is {mode}; deploy invokes it as ./{Path(path).name}"


@pytest.mark.parametrize("mode,path", SCRIPTS, ids=[p for _, p in SCRIPTS])
def test_tracked_script_is_valid_bash(mode, path):
    assert subprocess.run(["bash", "-n", path]).returncode == 0
