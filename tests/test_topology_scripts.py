"""The blocker resolves a layer to a datapath id, so the bridges must set one."""
import re
from pathlib import Path

RYU_SW = Path("host1/9.ryu-sw.sh").read_text()
CLEANUP = Path("utils/cleanup.sh").read_text()


def test_host1_bridges_get_an_explicit_datapath_id():
    assert "other-config:datapath-id=000000000000000${n}" in RYU_SW


def test_the_datapath_id_loop_covers_all_four_switches():
    assert re.search(r"for n in 1 2 3 4", RYU_SW)


def test_the_datapath_id_is_set_before_the_controller_is_attached():
    assert RYU_SW.index("datapath-id") < RYU_SW.index("set-controller")


def test_datapath_ids_match_the_default_layer_map():
    from ddos_ryu.config import BlockerConfig

    cfg = BlockerConfig.from_env({})
    assert (cfg.datapath_for("top"), cfg.datapath_for("inter"),
            cfg.datapath_for("bottom")) == (1, 2, 3)


def test_bridges_still_point_at_the_controller():
    assert "set-controller" in RYU_SW
    assert "${HOST1_MGMT_IP}" in RYU_SW and "${SDN_PORT}" in RYU_SW


def test_bridges_keep_openflow13_and_fail_secure():
    assert "OpenFlow13" in RYU_SW
    assert "fail-mode=secure" in RYU_SW


def test_sw5_sets_its_datapath_id():
    assert "datapath-id=0000000000000005" in Path("host2/2.sw5-config.sh").read_text()


def test_cleanup_covers_every_switch():
    for n in (1, 2, 3, 4, 5):
        assert f"sw{n}" in CLEANUP


def test_cleanup_removes_the_gre_port_and_the_bridge():
    assert "gre-to-vm" in CLEANUP
    assert "del-br" in CLEANUP


def test_cleanup_handles_bridges_whose_name_carries_stray_whitespace():
    assert "list-br" in CLEANUP
