"""Host addresses come from the CSV inventory, never from literals in scripts."""
import re
from pathlib import Path

import pytest

SCRIPTS = ["host1/1.config_br0.sh", "host2/1.config_br0.sh"]
LITERAL_IP = re.compile(r"\b192\.168\.\d+\.\d+\b")


@pytest.mark.parametrize("path", SCRIPTS)
def test_no_hardcoded_host_address(path):
    found = LITERAL_IP.findall(Path(path).read_text())
    assert not found, f"{path} hardcodes {found}; take it from the inventory"


@pytest.mark.parametrize("path", SCRIPTS)
def test_script_loads_the_generated_environment(path):
    text = Path(path).read_text()
    assert ".env" in text, f"{path} does not load .env"


@pytest.mark.parametrize("path,local,remote", [
    ("host1/1.config_br0.sh", "HOST1_IP", "HOST2_IP"),
    ("host2/1.config_br0.sh", "HOST2_IP", "HOST1_IP"),
])
def test_gre_tunnel_uses_the_variables_the_right_way_round(path, local, remote):
    text = Path(path).read_text()
    assert re.search(rf'local_ip="?\$\{{{local}\}}"?', text), f"{path} local_ip"
    assert re.search(rf'remote_ip="?\$\{{{remote}\}}"?', text), f"{path} remote_ip"


@pytest.mark.parametrize("path,var", [
    ("host1/1.config_br0.sh", "HOST1_MGMT_IP"),
    ("host2/1.config_br0.sh", "HOST2_MGMT_IP"),
])
def test_management_address_comes_from_a_variable(path, var):
    assert var in Path(path).read_text()


def test_readme_does_not_pin_the_host_addresses():
    assert not LITERAL_IP.findall(Path("README.md").read_text())


def test_the_inventory_still_holds_the_addresses():
    """The CSV is the one place they are written down."""
    hosts = Path("startup/files/input/hosts.csv").read_text()
    assert LITERAL_IP.findall(hosts)


@pytest.mark.parametrize("path,iface", [
    ("host1/1.config_br0.sh", "gre-to-vm2"),
    ("host2/1.config_br0.sh", "gre-to-vm1"),
])
def test_tunnel_mtu_is_set_through_ovs_not_iproute(path, iface):
    """An OVS tunnel port has no kernel netdev, so 'ip link set' cannot find it."""
    text = Path(path).read_text()
    assert f"ip link set {iface} mtu" not in text
    assert f"set interface {iface} mtu_request=1400" in text
