"""A capture over the packet bound is trimmed before conversion, never refused."""
import logging
import struct
import subprocess
from pathlib import Path

import pytest

from ddos_worker.capture import count_packets, trim_capture

MAGICS = {"le": ("<", 0xA1B2C3D4), "be": (">", 0xA1B2C3D4), "nano": ("<", 0xA1B23C4D)}


def write_pcap(path: Path, packets: int, order="le", payload=60) -> Path:
    end, magic = MAGICS[order]
    with open(path, "wb") as fh:
        fh.write(struct.pack(end + "IHHiIII", magic, 2, 4, 0, 0, 65535, 1))
        for i in range(packets):
            fh.write(struct.pack(end + "IIII", 1, i, payload, payload))
            fh.write(b"\x00" * payload)
    return path


@pytest.mark.parametrize("order", ["le", "be", "nano"])
def test_counts_packets_in_either_byte_order(tmp_path, order):
    assert count_packets(write_pcap(tmp_path / "a.pcap", 25, order), limit=1000) == 25


def test_counting_stops_one_past_the_limit(tmp_path):
    assert count_packets(write_pcap(tmp_path / "a.pcap", 500), limit=100) == 101


def test_a_truncated_last_record_is_not_counted(tmp_path):
    p = write_pcap(tmp_path / "a.pcap", 10)
    p.write_bytes(p.read_bytes()[:-5])
    assert count_packets(p, limit=100) == 9


def test_an_unrecognised_file_has_no_count(tmp_path):
    p = tmp_path / "a.pcap"
    p.write_bytes(b"not a pcap at all, just text")
    assert count_packets(p, limit=100) is None


def test_a_capture_within_the_bound_is_left_alone(tmp_path):
    p = write_pcap(tmp_path / "a.pcap", 50)
    calls = []
    assert trim_capture(p, 50, runner=lambda *a, **k: calls.append(a)) is False
    assert calls == []


def test_a_zero_bound_never_trims(tmp_path):
    p = write_pcap(tmp_path / "a.pcap", 50)
    calls = []
    assert trim_capture(p, 0, runner=lambda *a, **k: calls.append(a)) is False
    assert calls == []


def test_an_oversized_capture_is_cut_to_the_first_packets(tmp_path, caplog):
    p = write_pcap(tmp_path / "a.pcap", 200)

    def runner(cmd, **kw):
        assert cmd[0] == "tcpdump" and cmd[cmd.index("-c") + 1] == "80"
        assert cmd[cmd.index("-r") + 1] == str(p)
        write_pcap(Path(cmd[cmd.index("-w") + 1]), 80)
        return subprocess.CompletedProcess(cmd, 0, b"", b"")

    with caplog.at_level(logging.WARNING):
        assert trim_capture(p, 80, runner=runner) is True
    assert count_packets(p, limit=1000) == 80
    assert [r for r in caplog.records if r.levelno == logging.WARNING]
    assert "trimmed" in caplog.text and "80" in caplog.text
    assert [f.name for f in tmp_path.iterdir()] == ["a.pcap"]


def test_a_failed_trim_keeps_the_original_and_does_not_raise(tmp_path):
    p = write_pcap(tmp_path / "a.pcap", 200)

    def runner(cmd, **kw):
        return subprocess.CompletedProcess(cmd, 1, b"", b"boom")

    assert trim_capture(p, 80, runner=runner) is False
    assert count_packets(p, limit=1000) == 200
    assert [f.name for f in tmp_path.iterdir()] == ["a.pcap"]


def test_a_missing_tcpdump_does_not_raise(tmp_path):
    p = write_pcap(tmp_path / "a.pcap", 200)

    def runner(cmd, **kw):
        raise FileNotFoundError("tcpdump")

    assert trim_capture(p, 80, runner=runner) is False


def test_process_capture_trims_before_converting(tmp_path, monkeypatch):
    import ddos_worker.main as mod

    order = []

    def convert(*a, **k):
        order.append(("convert",))
        raise mod.FlowMeterError("stop")

    monkeypatch.setattr(mod, "trim_capture", lambda p, n, **k: order.append(("trim", n)))
    monkeypatch.setattr(mod, "pcap_to_csv", convert)
    cfg = mod.WorkerConfig.from_env({"WORKER_LAYER": "top", "WORKER_MAX_PACKETS": "123"})
    with pytest.raises(mod.FlowMeterError):
        mod.process_capture(tmp_path / "c.pcap", cfg, None, "s", "e")
    assert order == [("trim", 123), ("convert",)]
