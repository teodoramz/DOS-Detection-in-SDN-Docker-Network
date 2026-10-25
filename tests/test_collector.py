import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path("build/collector")))

import collector
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


class FakeObject:
    def __init__(self, name, age_hours):
        self.object_name = name
        self.last_modified = datetime.now(timezone.utc) - timedelta(hours=age_hours)


class FakeStore:
    def __init__(self, objects):
        self._objects = objects
        self.removed = []

    def list_objects(self, bucket, recursive=False):
        assert recursive
        return list(self._objects)

    def remove_object(self, bucket, name):
        self.removed.append(name)


def test_retention_removes_only_captures_past_the_window():
    cfg = collector.CollectorConfig.from_env(
        {"LAYER": "top", "CAPTURE_RETENTION_HOURS": "24"}
    )
    store = FakeStore([FakeObject("old.pcap", 30), FakeObject("fresh.pcap", 1)])
    assert collector.prune_old_captures(cfg, store) == 1
    assert store.removed == ["old.pcap"]


def test_retention_of_zero_keeps_everything():
    cfg = collector.CollectorConfig.from_env(
        {"LAYER": "top", "CAPTURE_RETENTION_HOURS": "0"}
    )
    store = FakeStore([FakeObject("ancient.pcap", 1000)])
    assert collector.prune_old_captures(cfg, store) == 0
    assert store.removed == []


def test_retention_failure_never_stops_the_capture_loop():
    """A broken object store must not take the collector down with it."""
    cfg = collector.CollectorConfig.from_env({"LAYER": "top"})

    class Broken:
        def list_objects(self, *a, **k):
            raise RuntimeError("object store unreachable")

    assert collector.prune_old_captures(cfg, Broken()) == 0


def test_retention_defaults_to_a_day():
    cfg = collector.CollectorConfig.from_env({"LAYER": "top"})
    assert cfg.retention_hours == 24


class BucketlessStore:
    """Loses its buckets, the way a redeployed object store with a fresh
    volume does, and reports it the way MinIO does."""

    def __init__(self, *, exists=False):
        self.buckets = {"inter-layer"} if exists else set()
        self.uploaded = []
        self.made = []

    def bucket_exists(self, bucket):
        return bucket in self.buckets

    def make_bucket(self, bucket):
        self.buckets.add(bucket)
        self.made.append(bucket)

    def fput_object(self, bucket, name, path):
        if bucket not in self.buckets:
            raise RuntimeError(
                "S3 operation failed; code: NoSuchBucket, message: The specified "
                f"bucket does not exist, bucket_name: {bucket}"
            )
        self.uploaded.append((bucket, name))


def test_a_lost_bucket_is_recreated_and_the_window_still_lands(tmp_path):
    cfg = collector.CollectorConfig.from_env({"LAYER": "inter"})
    store = BucketlessStore(exists=False)
    pcap = tmp_path / "capture.pcap"
    pcap.write_bytes(b"x")
    assert collector.upload_capture(store, cfg, pcap=pcap, filename="capture.pcap")
    assert store.made == ["inter-layer"], "the bucket was not recreated"
    assert store.uploaded == [("inter-layer", "capture.pcap")]


def test_an_existing_bucket_is_not_recreated(tmp_path):
    cfg = collector.CollectorConfig.from_env({"LAYER": "inter"})
    store = BucketlessStore(exists=True)
    pcap = tmp_path / "capture.pcap"
    pcap.write_bytes(b"x")
    assert collector.upload_capture(store, cfg, pcap=pcap, filename="capture.pcap")
    assert store.made == []


def test_an_unrelated_upload_failure_is_not_retried(tmp_path):
    cfg = collector.CollectorConfig.from_env({"LAYER": "inter"})

    class Broken(BucketlessStore):
        def __init__(self):
            super().__init__(exists=True)
            self.calls = 0

        def fput_object(self, bucket, name, path):
            self.calls += 1
            raise RuntimeError("connection reset by peer")

    store = Broken()
    pcap = tmp_path / "capture.pcap"
    pcap.write_bytes(b"x")
    with pytest.raises(RuntimeError):
        collector.upload_capture(store, cfg, pcap=pcap, filename="capture.pcap")
    assert store.calls == 1, "a transport error must not trigger a bucket rebuild"
    assert store.made == []
