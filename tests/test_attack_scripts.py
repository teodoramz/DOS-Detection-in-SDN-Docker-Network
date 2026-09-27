import os
import stat
import subprocess
from pathlib import Path

import pytest

NAMES = ["top", "inter", "bottom", "lib", "watch", "install-tools"]


@pytest.mark.parametrize("name", NAMES)
def test_script_is_valid_bash_and_executable(name):
    path = Path(f"attacks/{name}.sh")
    assert path.is_file()
    assert subprocess.run(["bash", "-n", str(path)]).returncode == 0
    assert os.stat(path).st_mode & stat.S_IXUSR


def test_top_uses_the_four_dns_tools():
    text = Path("attacks/top.sh").read_text()
    for tool in ("dnsperf", "hping3", "scapy", "dig"):
        assert tool in text


def test_inter_uses_syn_and_udp_floods():
    text = Path("attacks/inter.sh").read_text()
    assert "-S --flood" in text
    assert "-2 --flood" in text


def test_bottom_uses_slowhttptest_and_ab():
    text = Path("attacks/bottom.sh").read_text()
    assert "slowhttptest" in text
    assert "ab " in text


@pytest.mark.parametrize("layer", ["top", "inter", "bottom"])
def test_default_duration_is_ten_minutes(layer):
    assert "600" in Path("attacks/lib.sh").read_text()
    assert "DURATION" in Path(f"attacks/{layer}.sh").read_text()


@pytest.mark.parametrize("layer", ["top", "inter", "bottom"])
def test_each_layer_targets_its_own_service(layer):
    expected = {"top": "10.0.1.2", "inter": "10.0.2.2", "bottom": "10.0.3.2"}[layer]
    assert expected in Path(f"attacks/{layer}.sh").read_text()


@pytest.mark.parametrize("layer", ["top", "inter", "bottom"])
def test_each_script_stops_what_it_started(layer):
    assert "finish" in Path(f"attacks/{layer}.sh").read_text()


def test_readme_documents_the_placeholder_detectors():
    readme = Path("README.md").read_text().lower()
    assert "heuristic" in readme
    assert "placeholder" in readme


def test_readme_documents_bring_up_and_attacks():
    readme = Path("README.md").read_text()
    assert "deploy/host1.sh" in readme
    assert "deploy/host2.sh" in readme
    assert "attacks/" in readme
