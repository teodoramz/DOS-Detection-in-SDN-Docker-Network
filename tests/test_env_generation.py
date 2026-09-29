"""The rendered .env must define every variable the compose files reference."""
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("jinja2")
pytest.importorskip("pandas")

COMPOSE = ["docker-compose-host1.yml", "docker-compose-host2.yml"]


@pytest.fixture(scope="module")
def rendered(tmp_path_factory):
    """Render into a throwaway copy: this suite may run on a deployed host,
    where rewriting the repo-root .env would touch the live deployment."""
    import shutil

    home = tmp_path_factory.mktemp("ddos_home")
    shutil.copytree("startup", home / "startup")
    subprocess.run(
        [sys.executable, str(Path("startup/scripts/update_env.py").resolve())],
        env={**os.environ, "DDOS_DETECTION_HOME": str(home)},
        check=True, capture_output=True,
    )
    text = (home / ".env").read_text()
    return {
        m.group(1): m.group(2)
        for m in (re.match(r"^([A-Za-z0-9_]+)=(.*)$", line) for line in text.splitlines())
        if m
    }


def referenced_variables():
    names = set()
    for path in COMPOSE:
        names |= set(re.findall(r"\$\{([A-Za-z0-9_]+)\}", Path(path).read_text()))
    return names


def test_every_referenced_variable_is_defined(rendered):
    missing = sorted(referenced_variables() - set(rendered))
    assert not missing, f"compose references undefined variables: {missing}"


def test_no_variable_renders_empty(rendered):
    empty = sorted(k for k in referenced_variables() if rendered.get(k, "") == "")
    assert not empty, f"these render empty: {empty}"


def test_no_unrendered_jinja_placeholder_survives(rendered):
    leftovers = [k for k, v in rendered.items() if "{{" in v or "}}" in v]
    assert not leftovers, f"unrendered placeholders: {leftovers}"


def test_worker_addresses_come_from_the_inventory(rendered):
    assert rendered["WORKER1_SW5_IP"] == "10.0.5.11"
    assert rendered["WORKER2_SW5_IP"] == "10.0.5.12"
    assert rendered["WORKER3_SW5_IP"] == "10.0.5.13"


def test_collector_addresses_come_from_the_inventory(rendered):
    assert rendered["DNS_COL_SW1_IP"] == "10.0.1.6"
    assert rendered["PROXY_COL_SW2_IP"] == "10.0.2.6"
    assert rendered["SERVICE_COL_SW3_IP"] == "10.0.3.6"


def test_no_value_with_a_space_is_left_unquoted(rendered):
    """The topology scripts source .env, so an unquoted space runs as a command."""
    bad = [k for k, v in rendered.items()
           if " " in v and not (v.startswith(('"', "'")) and v.endswith(('"', "'")))]
    assert not bad, f"these would break 'source .env': {bad}"


def test_the_env_file_can_be_sourced_by_a_shell(tmp_path_factory):
    import shutil

    home = tmp_path_factory.mktemp("ddos_source")
    shutil.copytree("startup", home / "startup")
    subprocess.run(
        [sys.executable, str(Path("startup/scripts/update_env.py").resolve())],
        env={**os.environ, "DDOS_DETECTION_HOME": str(home)},
        check=True, capture_output=True,
    )
    result = subprocess.run(
        ["bash", "-c", f"set -euo pipefail; set -a; source {home}/.env; set +a; echo OK"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr[-400:]
    assert "OK" in result.stdout
