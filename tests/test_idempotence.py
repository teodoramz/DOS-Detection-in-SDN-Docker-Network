"""deploy/*.sh promise to be re-runnable, and they run under set -euo pipefail.

A second run must not abort partway: on host1 that leaves 9.ryu-sw.sh unrun,
so no bridge has a controller and fail-mode=secure forwards nothing.
"""
import re
from pathlib import Path

import pytest

ROUTING = ["host1/8.routing.sh", "host2/4.connect_containers.sh"]
WIRING = ["host1/2.sw1-sw4.sh", "host1/3.sw1-sw2-sw3.sh", "host1/4.sw1-dns.sh",
          "host1/5.sw2-proxy.sh", "host1/6.sw3-services.sh", "host1/7.sw4-collectors.sh",
          "host2/2.sw5-config.sh", "host2/3.sw5-containers.sh"]


@pytest.mark.parametrize("path", ROUTING + WIRING)
def test_no_bare_route_add(path):
    """'ip route add' fails with EEXIST on a second run."""
    for n, line in enumerate(Path(path).read_text().splitlines(), 1):
        assert not re.search(r"\bip route add\b", line), f"{path}:{n} {line.strip()}"


@pytest.mark.parametrize("path", ROUTING + WIRING)
def test_no_bare_addr_add(path):
    """'ip addr add' fails with EEXIST on a second run."""
    for n, line in enumerate(Path(path).read_text().splitlines(), 1):
        assert not re.search(r"\bip addr add\b", line), f"{path}:{n} {line.strip()}"


@pytest.mark.parametrize("path", ROUTING + WIRING + ["host1/9.ryu-sw.sh"])
def test_script_declares_a_shell(path):
    assert Path(path).read_text().startswith("#!"), f"{path} has no shebang"


@pytest.mark.parametrize("path", ROUTING + ["host1/9.ryu-sw.sh"])
def test_routing_scripts_fail_fast(path):
    """These have no tolerated failures once the operations are idempotent."""
    assert "set -e" in Path(path).read_text(), f"{path} does not fail fast"


@pytest.mark.parametrize("path", WIRING)
def test_wiring_creates_links_and_ports_idempotently(path):
    text = Path(path).read_text()
    for n, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("ip link add "):
            assert "||" in stripped or "link_absent" in text, f"{path}:{n} {stripped}"
        if "ovs-vsctl add-port" in stripped:
            assert "--may-exist" in stripped, f"{path}:{n} {stripped}"


def test_the_controller_endpoint_comes_from_the_environment():
    text = Path("host1/9.ryu-sw.sh").read_text()
    assert ".env" in text, "9.ryu-sw.sh does not load the generated environment"
    assert "10.255.255.254" not in text, "controller address is hardcoded"
    assert "6633" not in text or "SDN_PORT" in text, "controller port is hardcoded"
