from datetime import datetime, timedelta, timezone

from ddos_ryu.blocking import BlockDecision, BlockTable, build_block_flow, decide
from ddos_ryu.config import BlockerConfig

NOW = datetime(2026, 9, 27, 15, 30, 0, tzinfo=timezone.utc)
CFG = BlockerConfig.from_env({})


def alert(**over):
    base = {"layer": "top", "source_ip": "10.0.1.50", "max_probability": 0.99}
    return {**base, **over}


def test_decides_to_block_an_ordinary_source():
    assert decide(alert(), CFG) == BlockDecision(dpid=1, source_ip="10.0.1.50", layer="top")


def test_layer_selects_the_datapath():
    assert decide(alert(layer="inter", source_ip="10.0.2.50"), CFG).dpid == 2
    assert decide(alert(layer="bottom", source_ip="10.0.3.50"), CFG).dpid == 3


def test_refuses_a_whitelisted_source():
    assert decide(alert(source_ip="10.0.1.1"), CFG) is None


def test_refuses_an_unmapped_layer():
    assert decide(alert(layer="sideways"), CFG) is None


def test_refuses_a_missing_layer():
    assert decide({"source_ip": "10.0.1.50"}, CFG) is None


def test_refuses_a_missing_source_ip():
    assert decide({"layer": "top"}, CFG) is None


def test_refuses_a_non_address():
    assert decide(alert(source_ip="10.0.1.999"), CFG) is None


def test_refuses_a_non_dict():
    assert decide("not a dict", CFG) is None


def test_first_record_is_new():
    assert BlockTable().record(1, "10.0.1.50", 300, NOW) is True


def test_repeat_record_is_a_refresh_not_a_new_entry():
    """Twenty rounds of one flood must not make twenty entries."""
    table = BlockTable()
    table.record(1, "10.0.1.50", 300, NOW)
    for i in range(1, 20):
        assert table.record(1, "10.0.1.50", 300, NOW + timedelta(seconds=30 * i)) is False
    assert len(table) == 1


def test_refresh_extends_the_expiry():
    table = BlockTable()
    table.record(1, "10.0.1.50", 300, NOW)
    first = table.active(NOW)[0]["expires_at"]
    table.record(1, "10.0.1.50", 300, NOW + timedelta(seconds=100))
    assert table.active(NOW)[0]["expires_at"] > first


def test_refresh_counts_the_hits():
    table = BlockTable()
    for i in range(5):
        table.record(1, "10.0.1.50", 300, NOW + timedelta(seconds=30 * i))
    assert table.active(NOW)[0]["hits"] == 5


def test_the_same_ip_on_two_datapaths_is_two_entries():
    table = BlockTable()
    table.record(1, "10.0.1.50", 300, NOW)
    table.record(2, "10.0.1.50", 300, NOW)
    assert len(table) == 2


def test_expired_entries_drop_out_of_active():
    table = BlockTable()
    table.record(1, "10.0.1.50", 300, NOW)
    assert table.active(NOW + timedelta(seconds=299)) != []
    assert table.active(NOW + timedelta(seconds=301)) == []


def test_a_zero_timeout_never_expires():
    table = BlockTable()
    table.record(1, "10.0.1.50", 0, NOW)
    entries = table.active(NOW + timedelta(days=30))
    assert len(entries) == 1
    assert entries[0]["expires_at"] is None


def test_active_reports_remaining_seconds():
    table = BlockTable()
    table.record(1, "10.0.1.50", 300, NOW)
    assert table.active(NOW + timedelta(seconds=60))[0]["remaining_s"] == 240


def test_forget_removes_an_entry():
    table = BlockTable()
    table.record(1, "10.0.1.50", 300, NOW)
    assert table.forget(1, "10.0.1.50") is True
    assert table.active(NOW) == []


def test_forget_an_absent_entry_reports_false():
    assert BlockTable().forget(1, "10.0.1.50") is False


class FakeOfProto:
    OFPFC_ADD = 0
    OFPIT_APPLY_ACTIONS = 4
    OFPP_ANY = 0xFFFFFFFF
    OFPG_ANY = 0xFFFFFFFF


class FakeParser:
    def OFPMatch(self, **kwargs):
        return {"match": kwargs}

    def OFPInstructionActions(self, kind, actions):
        return {"kind": kind, "actions": actions}

    def OFPFlowMod(self, **kwargs):
        return {"flowmod": kwargs}


class FakeDatapath:
    def __init__(self, dpid=1):
        self.id = dpid
        self.ofproto = FakeOfProto()
        self.ofproto_parser = FakeParser()


def flow(cfg=CFG):
    return build_block_flow(FakeDatapath(), BlockDecision(1, "10.0.1.50", "top"), cfg)


def test_flow_matches_ipv4_source():
    assert flow()["flowmod"]["match"]["match"] == {"eth_type": 0x0800, "ipv4_src": "10.0.1.50"}


def test_flow_has_no_actions_so_the_packet_is_dropped():
    assert flow()["flowmod"]["instructions"][0]["actions"] == []


def test_flow_priority_comes_from_config():
    assert flow()["flowmod"]["priority"] == 100


def test_flow_timeout_comes_from_config():
    assert flow()["flowmod"]["hard_timeout"] == 300


def test_a_zero_timeout_yields_a_permanent_rule():
    cfg = BlockerConfig.from_env({"BLOCK_HARD_TIMEOUT": "0"})
    assert flow(cfg)["flowmod"]["hard_timeout"] == 0


def test_block_priority_is_above_the_learning_switch():
    from ddos_ryu.blocking import LEARNED_PRIORITY, TABLE_MISS_PRIORITY

    assert CFG.block_priority > LEARNED_PRIORITY > TABLE_MISS_PRIORITY
