from datetime import datetime, timedelta, timezone

from ddos_ryu.blocking import (
    BlockDecision, BlockTable, build_block_flow, build_clear_flows, build_forget_flow,
    decide, learn_mac,
)
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
    OFPFC_DELETE = 3
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


def test_a_mac_seen_for_the_first_time_has_not_moved():
    table = {}
    assert learn_mac(table, 1, "aa:bb:cc:dd:ee:ff", 3) is None
    assert table[1]["aa:bb:cc:dd:ee:ff"] == 3


def test_a_mac_seen_again_on_the_same_port_has_not_moved():
    table = {}
    learn_mac(table, 1, "aa:bb:cc:dd:ee:ff", 3)
    assert learn_mac(table, 1, "aa:bb:cc:dd:ee:ff", 3) is None


def test_a_mac_that_changes_port_reports_where_it_was():
    """A container keeps its MAC when it is recreated but lands on a new veth,
    and the flows pointing at the old port survive their idle timeout because
    traffic keeps refreshing them. They have to be retracted."""
    table = {}
    learn_mac(table, 1, "aa:bb:cc:dd:ee:ff", 7)
    assert learn_mac(table, 1, "aa:bb:cc:dd:ee:ff", 10) == 7
    assert table[1]["aa:bb:cc:dd:ee:ff"] == 10


def test_each_switch_learns_independently():
    table = {}
    learn_mac(table, 1, "aa:bb:cc:dd:ee:ff", 7)
    assert learn_mac(table, 2, "aa:bb:cc:dd:ee:ff", 9) is None


def test_forget_flow_deletes_by_destination_only():
    """Matching on the destination alone catches every learned rule that sends
    this MAC anywhere; a drop rule matches on ipv4_src and is left alone."""
    mod = build_forget_flow(FakeDatapath(), "aa:bb:cc:dd:ee:ff")["flowmod"]
    assert mod["command"] == FakeOfProto.OFPFC_DELETE
    assert mod["match"] == {"match": {"eth_dst": "aa:bb:cc:dd:ee:ff"}}
    assert mod["out_port"] == FakeOfProto.OFPP_ANY
    assert mod["out_group"] == FakeOfProto.OFPG_ANY
    assert mod.get("table_id", 0) == 0


def test_clearing_a_switch_removes_everything_in_the_table():
    """A controller restart leaves its own tables empty while the switch keeps
    rules pointing at ports that may no longer exist, and traffic matching them
    refreshes their timeout forever. The two can only agree from a clean slate."""
    mod = build_clear_flows(FakeDatapath())["flowmod"]
    assert mod["command"] == FakeOfProto.OFPFC_DELETE
    assert mod["match"] == {"match": {}}, "the match must be a wildcard"
    assert mod["out_port"] == FakeOfProto.OFPP_ANY
    assert mod["out_group"] == FakeOfProto.OFPG_ANY
    assert mod.get("table_id", 0) == 0


# --- persistence -----------------------------------------------------------

import json  # noqa: E402

import pytest  # noqa: E402

from ddos_ryu.blocking import (  # noqa: E402
    load_blocks, parse_blocks, remaining_timeout, save_blocks, serialise_blocks,
)


def table_with(*blocks):
    table = BlockTable()
    for dpid, ip, timeout in blocks:
        table.record(dpid, ip, timeout, now=NOW)
    return table


def test_remaining_timeout_rounds_up_with_a_floor_of_one_second():
    assert remaining_timeout(NOW + timedelta(seconds=10.2), NOW) == 11
    assert remaining_timeout(NOW + timedelta(seconds=0.1), NOW) == 1
    assert remaining_timeout(NOW + timedelta(seconds=30), NOW) == 30


def test_remaining_timeout_is_zero_for_a_permanent_block():
    assert remaining_timeout(None, NOW) == 0


def test_remaining_timeout_is_none_once_expired():
    assert remaining_timeout(NOW, NOW) is None
    assert remaining_timeout(NOW - timedelta(seconds=1), NOW) is None


def test_serialised_records_carry_what_a_reinstall_needs():
    text = serialise_blocks(table_with((1, "10.0.1.50", 300), (2, "10.0.2.50", 0)).records())
    by_ip = {r["source_ip"]: r for r in json.loads(text)}
    assert by_ip["10.0.1.50"]["dpid"] == 1
    assert by_ip["10.0.1.50"]["installed_at"] == NOW.timestamp()
    assert by_ip["10.0.1.50"]["expires_at"] == NOW.timestamp() + 300
    assert by_ip["10.0.2.50"]["expires_at"] is None


def test_round_trip_restores_the_same_blocks():
    original = table_with((1, "10.0.1.50", 300), (2, "10.0.2.50", 0))
    records = parse_blocks(serialise_blocks(original.records()), NOW)
    restored = BlockTable()
    restored.restore(records)
    assert {(b["dpid"], b["source_ip"], b["remaining_s"]) for b in restored.active(NOW)} == {
        (1, "10.0.1.50", 300), (2, "10.0.2.50", None),
    }


def test_parse_drops_expired_records():
    text = serialise_blocks(table_with((1, "10.0.1.50", 300), (1, "10.0.1.51", 5)).records())
    later = NOW + timedelta(seconds=10)
    assert [r["source_ip"] for r in parse_blocks(text, later)] == ["10.0.1.50"]


def test_parse_skips_malformed_records_and_keeps_the_rest():
    good = {"dpid": 1, "source_ip": "10.0.1.50",
            "installed_at": NOW.timestamp(), "expires_at": None}
    text = json.dumps([good, {"dpid": "x"}, "junk", {**good, "source_ip": "nope"}])
    assert [r["source_ip"] for r in parse_blocks(text, NOW)] == ["10.0.1.50"]


@pytest.mark.parametrize("text", ["", "{not json", '{"a": 1}'])
def test_parse_rejects_text_that_is_not_a_list(text):
    with pytest.raises(ValueError):
        parse_blocks(text, NOW)


def test_load_of_a_missing_file_is_empty(tmp_path):
    assert load_blocks(tmp_path / "absent.json", NOW) == []


def test_load_of_a_corrupt_file_is_empty_and_warns(tmp_path, caplog):
    path = tmp_path / "blocks.json"
    path.write_text("{truncated")
    assert load_blocks(path, NOW) == []
    assert "blocks.json" in caplog.text


def test_save_is_atomic_and_creates_the_directory(tmp_path):
    path = tmp_path / "state" / "blocks.json"
    save_blocks(path, table_with((1, "10.0.1.50", 300)).records())
    assert [r["source_ip"] for r in load_blocks(path, NOW)] == ["10.0.1.50"]
    assert [p.name for p in path.parent.iterdir()] == ["blocks.json"]


def test_save_failure_is_logged_not_raised(tmp_path, caplog):
    blocker = tmp_path / "file"
    blocker.write_text("x")
    save_blocks(blocker / "blocks.json", [])
    assert "blocks.json" in caplog.text


def test_table_notifies_on_record_forget_and_expiry():
    changes = []
    table = BlockTable(on_change=lambda: changes.append(1))
    table.record(1, "10.0.1.50", 5, now=NOW)
    table.forget(1, "10.0.1.50")
    table.record(1, "10.0.1.51", 5, now=NOW)
    table.active(NOW + timedelta(seconds=6))
    assert len(changes) == 4


def test_forget_of_an_unknown_block_does_not_notify():
    changes = []
    BlockTable(on_change=lambda: changes.append(1)).forget(1, "10.0.1.50")
    assert changes == []


def test_block_flow_can_override_the_timeout():
    class P:
        def OFPMatch(self, **kw): return kw
        def OFPInstructionActions(self, *a): return a
        def OFPFlowMod(self, **kw): return kw

    class O:
        OFPIT_APPLY_ACTIONS = 4
        OFPFC_ADD = 0

    class D:
        ofproto_parser, ofproto = P(), O()

    decision = BlockDecision(1, "10.0.1.50", "top")
    assert build_block_flow(D(), decision, CFG)["hard_timeout"] == 300
    assert build_block_flow(D(), decision, CFG, hard_timeout=42)["hard_timeout"] == 42
    assert build_block_flow(D(), decision, CFG, hard_timeout=0)["hard_timeout"] == 0
