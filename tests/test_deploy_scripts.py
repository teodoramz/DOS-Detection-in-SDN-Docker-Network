import os
import stat
import subprocess
from pathlib import Path

import pytest

NAMES = ["host1", "host2", "lib"]


@pytest.mark.parametrize("name", NAMES)
def test_script_exists_and_is_executable(name):
    path = Path(f"deploy/{name}.sh")
    assert path.is_file()
    assert os.stat(path).st_mode & stat.S_IXUSR


@pytest.mark.parametrize("name", NAMES)
def test_script_is_valid_bash(name):
    assert subprocess.run(["bash", "-n", f"deploy/{name}.sh"]).returncode == 0


@pytest.mark.parametrize("name", ["host1", "host2"])
def test_script_fails_fast(name):
    assert "set -euo pipefail" in Path(f"deploy/{name}.sh").read_text()


@pytest.mark.parametrize("name", ["host1", "host2"])
def test_script_supports_clean(name):
    assert "--clean" in Path(f"deploy/{name}.sh").read_text()


def test_host1_runs_the_numbered_scripts_in_order():
    text = Path("deploy/host1.sh").read_text()
    positions = [text.index(f"./{n}.") for n in range(1, 10)]
    assert positions == sorted(positions)


def test_host1_brings_up_compose_before_wiring_the_network():
    """The veth scripts need container PIDs, so compose must run first."""
    text = Path("deploy/host1.sh").read_text()
    assert text.index("compose -f docker-compose-host1.yml up") < text.index("./1.config_br0.sh")


def test_host2_wires_sw5_and_the_containers():
    text = Path("deploy/host2.sh").read_text()
    for step in ("1.config_br0.sh", "2.sw5-config.sh", "3.sw5-containers.sh",
                 "4.connect_containers.sh"):
        assert step in text


@pytest.mark.parametrize("name", ["host1", "host2"])
def test_env_is_generated_before_compose(name):
    text = Path(f"deploy/{name}.sh").read_text()
    assert text.index("generate_env") < text.index("compose -f docker-compose")


@pytest.mark.parametrize("name", ["host1", "host2"])
def test_script_requires_root_and_the_home_variable(name):
    text = Path(f"deploy/{name}.sh").read_text()
    assert "require_root" in text
    assert "require_home" in text


def test_start_wrapper_points_at_the_deploy_scripts():
    text = Path("utils/start.sh").read_text()
    assert "deploy/host1.sh" in text
    assert "deploy/host2.sh" in text
