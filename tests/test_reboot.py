"""After a host reboot the testbed must come back without a manual step.

Docker restarts most containers on its own, but the switches have no restart
policy and every veth is gone, so nothing works until the wiring is redone.
A systemd unit runs a rewire path (no build, no new .env) on boot.
"""
import re
import subprocess
from pathlib import Path

import pytest

HOSTS = ["host1", "host2"]
UNIT = Path("deploy/systemd/ddos-testbed.service.in")
LIB = Path("deploy/lib.sh")
WIRE = Path("deploy/wire.sh")
WIRING = sorted(str(p) for p in [*Path("host1").glob("[2-7].*.sh"), *Path("host2").glob("[23].*.sh")])
BRIDGE_SETUP = ["host1/1.config_br0.sh", "host2/1.config_br0.sh"]


def unit_text():
    return UNIT.read_text()


def test_the_unit_template_exists():
    assert UNIT.is_file()


def test_the_unit_orders_after_docker_and_openvswitch_and_the_network():
    text = unit_text()
    after = re.search(r"^After=(.*)$", text, re.M).group(1)
    wants = re.search(r"^Wants=(.*)$", text, re.M).group(1)
    for dep in ("docker.service", "openvswitch-switch.service", "network-online.target"):
        assert dep in after, f"not ordered after {dep}"
        assert dep in wants, f"does not pull in {dep}"


def test_the_unit_is_a_oneshot_that_stays_active():
    text = unit_text()
    assert re.search(r"^Type=oneshot$", text, re.M)
    assert re.search(r"^RemainAfterExit=yes$", text, re.M)
    assert re.search(r"^WantedBy=multi-user.target$", text, re.M)


def test_the_unit_runs_the_rewire_path_for_its_own_host():
    text = unit_text()
    exec_start = re.search(r"^ExecStart=(.*)$", text, re.M).group(1)
    assert "@HOST@.sh" in exec_start
    assert "--rewire" in exec_start
    assert "--clean" not in exec_start
    assert "DDOS_DETECTION_HOME=@DDOS_HOME@" in text


def test_the_unit_carries_no_hardcoded_path_or_address():
    text = unit_text()
    assert "/home/" not in text
    assert not re.search(r"\d+\.\d+\.\d+\.\d+", text)


def test_the_unit_does_nothing_on_a_machine_that_was_never_deployed():
    assert "ConditionPathExists=@DDOS_HOME@/.env" in unit_text()


def test_the_unit_gives_up_instead_of_retrying_forever():
    text = unit_text()
    assert re.search(r"^Restart=on-failure$", text, re.M)
    assert "StartLimitBurst=" in text


@pytest.mark.parametrize("name", HOSTS)
def test_deploy_installs_and_enables_the_unit(name):
    text = Path(f"deploy/{name}.sh").read_text()
    assert f"install_boot_unit {name}" in text
    lib = LIB.read_text()
    assert "install_boot_unit()" in lib
    assert "systemctl daemon-reload" in lib
    assert re.search(r"systemctl enable [^\n]*ddos-testbed", lib)
    assert "ddos-testbed.service.in" in lib


def test_installing_the_unit_is_idempotent_and_can_be_skipped():
    lib = LIB.read_text()
    body = lib.split("install_boot_unit()", 1)[1].split("\n}\n", 1)[0]
    assert "cmp -s" in body, "an unchanged unit must not be rewritten"
    assert "DDOS_BOOT_UNIT" in lib
    for name in HOSTS:
        assert "--no-boot-unit" in Path(f"deploy/{name}.sh").read_text()
    assert "--no-boot-unit" in Path("deploy/remote.sh").read_text()


@pytest.mark.parametrize("name", HOSTS)
def test_the_unit_is_installed_with_the_project_path_filled_in(name):
    body = LIB.read_text().split("install_boot_unit()", 1)[1].split("\n}\n", 1)[0]
    assert "@DDOS_HOME@" in body and "@HOST@" in body
    assert "DDOS_DETECTION_HOME" in body


@pytest.mark.parametrize("name", HOSTS)
def test_rewire_is_a_flag_on_the_deploy_script(name):
    text = Path(f"deploy/{name}.sh").read_text()
    assert "--rewire" in text
    assert subprocess.run(["bash", "-n", f"deploy/{name}.sh"]).returncode == 0


@pytest.mark.parametrize("name", HOSTS)
def test_rewire_starts_existing_containers_without_building(name):
    text = Path(f"deploy/{name}.sh").read_text()
    compose = [l for l in text.splitlines() if "compose -f docker-compose" in l and " up " in l]
    assert any("--no-build" in l for l in compose), "rewire must not build images"
    assert any("--build" in re.sub(r"--no-build", "", l) for l in compose), \
        "a normal deploy still builds"


@pytest.mark.parametrize("name", HOSTS)
def test_rewire_does_not_regenerate_env_certs_or_tear_down(name):
    text = Path(f"deploy/{name}.sh").read_text()
    for needle in ("generate_env", "generate-certs"):
        for n, line in enumerate(text.splitlines(), 1):
            if needle in line and not line.lstrip().startswith("#"):
                # every use must sit inside a branch guarded by REWIRE
                before = "\n".join(text.splitlines()[:n])
                assert re.search(r'REWIRE|rewire', before), f"{name}.sh:{n} {line.strip()}"
    assert re.search(r'\[ -f "?\.env"? \]|\.env', text)


@pytest.mark.parametrize("name", HOSTS)
def test_rewire_wires_and_checks_health_like_a_deploy(name):
    """One wiring and health section serves both paths."""
    text = Path(f"deploy/{name}.sh").read_text()
    assert text.count("Wiring the network") == 1
    assert text.count("Health check") == 1


def test_rewire_does_not_depend_on_the_other_host():
    for name in HOSTS:
        text = Path(f"deploy/{name}.sh").read_text()
        assert "ssh " not in text


@pytest.mark.parametrize("path", BRIDGE_SETUP)
def test_iptables_rules_are_not_duplicated_on_a_rerun(path):
    for n, line in enumerate(Path(path).read_text().splitlines(), 1):
        assert not re.search(r"iptables -[AI] ", line), f"{path}:{n} {line.strip()}"
    assert "iptables_ensure" in Path(path).read_text()


def test_the_iptables_helper_checks_before_adding():
    assert re.search(r"iptables -C", WIRE.read_text())


@pytest.mark.parametrize("path", BRIDGE_SETUP)
def test_stale_host_bridge_ports_are_pruned(path):
    assert "prune_dead_ports br0" in Path(path).read_text()


def test_the_prune_helper_spares_tunnel_ports():
    body = WIRE.read_text().split("prune_dead_ports()", 1)[1].split("\n}\n", 1)[0]
    assert "del-port" in body and "--if-exists" in body
    assert "gre" not in body or "type" in body
    assert "get Interface" in body and "type" in body


@pytest.mark.parametrize("path", WIRING)
def test_wiring_sources_the_shared_helpers(path):
    assert "wire.sh" in Path(path).read_text()


@pytest.mark.parametrize("path", WIRING)
def test_wiring_skips_a_veth_whose_ends_are_already_in_place(path):
    """The host never holds the container-side name, so 'does the link exist
    here' cannot tell whether a pair was made; ask the namespaces instead."""
    text = Path(path).read_text()
    assert "link_absent" not in text
    creations = re.findall(r"^\s*ip link add ", text, re.M)
    guards = re.findall(r"^if ! (?:wired|has_if) ", text, re.M)
    assert len(creations) == len(guards) >= 1


def test_the_namespace_helpers_do_not_depend_on_a_shell_in_the_container():
    """minio is distroless, so the check goes through its PID."""
    text = WIRE.read_text()
    assert "has_if()" in text and "wired()" in text
    assert "nsenter" in text.split("has_if()", 1)[1].split("\n}\n", 1)[0]


@pytest.mark.parametrize("path", ["host1/2.sw1-sw4.sh", "host2/2.sw5-config.sh"])
def test_a_stale_host_end_of_a_switch_uplink_is_dropped_before_recreating(path):
    text = Path(path).read_text()
    assert re.search(r"del-port br0 veth-br-sw\d", text)


@pytest.mark.parametrize("path", ["host1/2.sw1-sw4.sh", "host2/2.sw5-config.sh"])
def test_dead_switch_ports_are_pruned_before_wiring(path):
    assert "prune_dead_ports br-sw" in Path(path).read_text()


def test_switches_have_no_restart_policy():
    """A switch that restarts alone is empty: its veths died with its namespace.
    Leaving it Exited makes the fault visible, and the unit's `up -d` starts it
    before the wiring runs."""
    yaml = pytest.importorskip("yaml")
    for f in ("docker-compose-host1.yml", "docker-compose-host2.yml"):
        services = yaml.safe_load(Path(f).read_text())["services"]
        for name, svc in services.items():
            if re.fullmatch(r"sw\d", name):
                assert "restart" not in svc


@pytest.mark.parametrize("name", HOSTS)
def test_the_readme_and_help_describe_the_reboot_path(name):
    readme = Path("README.md").read_text()
    assert "--rewire" in readme and "ddos-testbed" in readme
    assert "--rewire" in Path(f"deploy/{name}.sh").read_text()
    assert "--no-boot-unit" in subprocess.run(
        ["bash", "deploy/remote.sh", "--help"], capture_output=True, text=True).stdout
