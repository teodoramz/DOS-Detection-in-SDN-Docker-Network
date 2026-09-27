import pytest

from ddos_worker.config import LAYER_BUCKETS, LAYER_TOPICS, WorkerConfig

BASE = {"WORKER_LAYER": "top"}


def test_layer_selects_topic_bucket_and_model_dir():
    cfg = WorkerConfig.from_env(BASE)
    assert cfg.capture_topic == "top-layer"
    assert cfg.minio_bucket == "top-layer"
    assert cfg.model_dir.name == "top"


@pytest.mark.parametrize(
    "layer,topic",
    [("top", "top-layer"), ("inter", "inter-layer"), ("bottom", "bot-layer")],
)
def test_every_layer_maps_to_its_thesis_topic(layer, topic):
    assert LAYER_TOPICS[layer] == topic
    assert LAYER_BUCKETS[layer] == topic


def test_unknown_layer_is_rejected():
    with pytest.raises(ValueError, match="WORKER_LAYER"):
        WorkerConfig.from_env({"WORKER_LAYER": "sideways"})


def test_missing_layer_is_rejected():
    with pytest.raises(ValueError, match="WORKER_LAYER"):
        WorkerConfig.from_env({})


def test_defaults_match_the_thesis():
    cfg = WorkerConfig.from_env(BASE)
    assert cfg.alert_topic == "ddos-alerts"
    assert cfg.threshold == 0.5
    assert cfg.min_flows == 10
    assert cfg.max_lag_seconds == 120


def test_overrides_are_honoured():
    cfg = WorkerConfig.from_env({**BASE, "ALERT_THRESHOLD": "0.8", "ALERT_MIN_FLOWS": "1"})
    assert cfg.threshold == 0.8
    assert cfg.min_flows == 1


def test_min_flows_of_one_is_allowed_for_thesis_literal_behaviour():
    assert WorkerConfig.from_env({**BASE, "ALERT_MIN_FLOWS": "1"}).min_flows == 1


def test_threshold_outside_zero_to_one_is_rejected():
    with pytest.raises(ValueError, match="ALERT_THRESHOLD"):
        WorkerConfig.from_env({**BASE, "ALERT_THRESHOLD": "1.5"})


def test_non_numeric_threshold_is_rejected():
    with pytest.raises(ValueError, match="ALERT_THRESHOLD"):
        WorkerConfig.from_env({**BASE, "ALERT_THRESHOLD": "high"})


def test_min_flows_below_one_is_rejected():
    with pytest.raises(ValueError, match="ALERT_MIN_FLOWS"):
        WorkerConfig.from_env({**BASE, "ALERT_MIN_FLOWS": "0"})
