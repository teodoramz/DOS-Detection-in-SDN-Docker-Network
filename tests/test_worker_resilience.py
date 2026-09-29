"""A worker must never exit: a restart destroys the veth attached to it.

Each test here reproduces a review finding that ended in permanent veth loss.
"""
from pathlib import Path

import pytest

from ddos_worker.main import MessageError, parse_message


@pytest.mark.parametrize("payload", [
    '{"object": 123}',
    '{"object": ["a"]}',
    '{"object": {"a": 1}}',
    '{"filename": 7}',
    '{"object": true}',
])
def test_a_non_string_object_is_rejected(payload):
    """Truthiness alone let these through, then .replace() crashed the loop."""
    with pytest.raises(MessageError, match="object"):
        parse_message(payload)


def test_a_string_object_is_still_accepted():
    assert parse_message('{"object": "c.pcap"}')["object"] == "c.pcap"


def test_a_non_string_bucket_is_rejected():
    with pytest.raises(MessageError, match="bucket"):
        parse_message('{"object": "c.pcap", "bucket": 5}')


def test_the_consume_loop_is_wrapped_and_reconnects():
    """A clean end of iteration must not end the process."""
    source = Path("build/worker/ddos_worker/main.py").read_text()
    body = source[source.index("def main("):]
    assert "while True:" in body, "the consume loop is not restarted"
    assert body.count("except Exception") >= 2, "no boundary around the consumer"


def test_the_window_path_is_built_inside_the_error_boundary():
    source = Path("build/worker/ddos_worker/main.py").read_text()
    body = source[source.index("def handle_record("):source.index("def main(")]
    assert body.index("try:") < body.index('.replace("/", "_")')


def test_handling_one_record_never_raises():
    """Whatever a single window does, the consume loop must survive it."""
    import ddos_worker.main as mod

    class Record:
        value = b'{"object": "c.pcap", "bucket": "b"}'

    class ExplodingStore:
        def fget_object(self, *a, **k):
            raise RuntimeError("minio is gone")

    cfg = mod.WorkerConfig.from_env({"WORKER_LAYER": "top", "WORK_DIR": "/tmp/ddos-test"})
    mod.handle_record(Record(), cfg, detector=None, store=ExplodingStore(), producer=None)


def test_a_record_whose_processing_explodes_is_swallowed(tmp_path):
    import ddos_worker.main as mod

    class Record:
        value = b'{"object": "c.pcap", "bucket": "b"}'

    class Store:
        def fget_object(self, bucket, obj, dest):
            Path(dest).write_bytes(b"x")

    cfg = mod.WorkerConfig.from_env({"WORKER_LAYER": "top", "WORK_DIR": str(tmp_path)})

    class Detector:
        name = "x"

        def score(self, df):
            raise RuntimeError("model blew up")

    mod.handle_record(Record(), cfg, detector=Detector(), store=Store(), producer=None)
    assert not list(tmp_path.iterdir()), "the window directory must be cleaned up"
