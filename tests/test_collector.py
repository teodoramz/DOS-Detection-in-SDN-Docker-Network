import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path("build/collector")))

from collector import CollectorConfig, build_message


def test_duration_defaults_to_thirty_seconds():
    assert CollectorConfig.from_env({"LAYER": "top"}).duration == 30


@pytest.mark.parametrize("layer", ["top", "inter", "bottom"])
def test_every_layer_defaults_to_thirty_seconds(layer):
    assert CollectorConfig.from_env({"LAYER": layer}).duration == 30


def test_duration_is_overridable():
    assert CollectorConfig.from_env({"LAYER": "top", "CAPTURE_DURATION": "60"}).duration == 60


def test_zero_duration_is_rejected():
    with pytest.raises(ValueError, match="CAPTURE_DURATION"):
        CollectorConfig.from_env({"LAYER": "top", "CAPTURE_DURATION": "0"})


def test_non_numeric_duration_is_rejected():
    with pytest.raises(ValueError, match="CAPTURE_DURATION"):
        CollectorConfig.from_env({"LAYER": "top", "CAPTURE_DURATION": "half a minute"})


def test_layer_picks_topic_and_bucket():
    cfg = CollectorConfig.from_env({"LAYER": "bottom"})
    assert cfg.kafka_topic == "bot-layer"
    assert cfg.minio_bucket == "bot-layer"


def test_unknown_layer_is_rejected():
    with pytest.raises(ValueError, match="LAYER"):
        CollectorConfig.from_env({"LAYER": "middle"})


def message():
    return build_message(
        filename="c.pcap", bucket="top-layer", layer="top",
        captured_at="2026-09-27T15:30:00Z", duration=30,
        interface="eth0", download_url="http://x",
    )


def test_message_keeps_the_legacy_fields():
    msg = message()
    assert msg["filename"] == "c.pcap"
    assert msg["download_url"] == "http://x"


def test_message_adds_the_new_fields():
    msg = message()
    assert msg["object"] == "c.pcap"
    assert msg["bucket"] == "top-layer"
    assert msg["layer"] == "top"
    assert msg["captured_at"] == "2026-09-27T15:30:00Z"
    assert msg["duration_s"] == 30
    assert msg["interface"] == "eth0"


def test_message_is_json_serialisable():
    assert json.loads(json.dumps(message())) == message()


def test_message_is_readable_by_the_worker():
    from ddos_worker.main import parse_message

    assert parse_message(json.dumps(message()))["object"] == "c.pcap"
