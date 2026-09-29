import pytest

from ddos_ryu.config import BlockerConfig, parse_layer_map, parse_whitelist


def cfg(**over):
    return BlockerConfig.from_env(over)


def test_defaults_match_the_spec():
    c = cfg()
    assert c.alert_topic == "ddos-alerts"
    assert c.block_timeout == 300
    assert c.block_priority == 100
    assert c.ofp_port == 6633
    assert c.rest_port == 8080


def test_layer_map_defaults_to_the_three_layers():
    c = cfg()
    assert c.datapath_for("top") == 1
    assert c.datapath_for("inter") == 2
    assert c.datapath_for("bottom") == 3


def test_unknown_layer_has_no_datapath():
    assert cfg().datapath_for("sideways") is None


def test_layer_map_is_overridable():
    assert cfg(LAYER_DATAPATH_MAP="top:9,inter:8,bottom:7").datapath_for("top") == 9


def test_malformed_layer_map_is_rejected():
    with pytest.raises(ValueError, match="LAYER_DATAPATH_MAP"):
        parse_layer_map("top=1")


def test_non_numeric_datapath_is_rejected():
    with pytest.raises(ValueError, match="LAYER_DATAPATH_MAP"):
        parse_layer_map("top:one")


def test_permanent_block_is_allowed():
    assert cfg(BLOCK_HARD_TIMEOUT="0").block_timeout == 0


def test_negative_timeout_is_rejected():
    with pytest.raises(ValueError, match="BLOCK_HARD_TIMEOUT"):
        cfg(BLOCK_HARD_TIMEOUT="-1")


@pytest.mark.parametrize("ip", [
    "10.255.255.1", "10.255.255.254",
    "10.0.1.1", "10.0.2.1", "10.0.3.1", "10.0.4.1", "10.0.5.1",
    "10.0.1.6", "10.0.2.6", "10.0.3.6",
    "10.0.5.2", "10.0.5.6", "10.0.5.9",
])
def test_infrastructure_addresses_are_never_blocked(ip):
    """Blocking a gateway or a collector partitions the testbed."""
    assert cfg().is_whitelisted(ip) is True


@pytest.mark.parametrize("ip", ["10.0.1.50", "10.0.2.77", "192.168.241.10"])
def test_ordinary_sources_are_blockable(ip):
    assert cfg().is_whitelisted(ip) is False


def test_a_non_address_is_treated_as_whitelisted():
    assert cfg().is_whitelisted("not-an-ip") is True
    assert cfg().is_whitelisted("") is True


def test_ipv6_is_treated_as_whitelisted():
    assert cfg().is_whitelisted("::1") is True


def test_whitelist_accepts_cidr_and_bare_addresses():
    assert len(parse_whitelist("10.9.0.0/16, 10.8.8.8")) == 2


def test_custom_whitelist_replaces_the_default():
    c = cfg(BLOCK_WHITELIST="10.9.0.0/16")
    assert c.is_whitelisted("10.9.1.1") is True
    assert c.is_whitelisted("10.0.1.1") is False


def test_empty_whitelist_entries_are_skipped():
    assert len(parse_whitelist("10.1.1.1,, ,10.2.2.2")) == 2


def test_malformed_whitelist_entry_is_rejected():
    with pytest.raises(ValueError, match="BLOCK_WHITELIST"):
        parse_whitelist("10.0.0.0/99")


@pytest.mark.parametrize("ip,service", [
    ("10.0.1.2", "the DNS resolver"),
    ("10.0.2.2", "the reverse proxy"),
    ("10.0.3.2", "the web server"),
])
def test_the_protected_services_are_never_blocked(ip, service):
    """An amplification attack makes the victim a high-volume source, so the
    naive rule would drop the service it is meant to protect."""
    assert cfg().is_whitelisted(ip) is True, f"{service} would be blocked"


def test_a_client_on_a_service_subnet_is_still_blockable():
    for ip in ("10.0.1.50", "10.0.2.50", "10.0.3.50"):
        assert cfg().is_whitelisted(ip) is False


def test_the_deployed_whitelist_matches_the_code_default():
    """compose passes BLOCK_WHITELIST from .env, so that copy is what runs.
    Editing config.py alone would change nothing on the testbed."""
    from pathlib import Path

    from ddos_ryu.config import DEFAULT_WHITELIST

    line = next(
        l for l in Path("startup/templates/env.j2").read_text().splitlines()
        if l.startswith("BLOCK_WHITELIST=")
    )
    rendered = line.split("=", 1)[1].strip()
    assert set(rendered.split(",")) == set(DEFAULT_WHITELIST.split(",")), (
        "env.j2 and config.py disagree; the .env copy is the one that runs"
    )
