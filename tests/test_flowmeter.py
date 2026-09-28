import os
import subprocess
import time
from pathlib import Path

import pytest

from ddos_worker.flowmeter import FlowMeterError, pcap_to_csv, read_flows


class FakeRunner:
    """Records the command and optionally drops a CSV where the tool would."""

    def __init__(self, out_dir=None, produce="capture_ISCX.csv", returncode=0, raises=None):
        self.out_dir = out_dir
        self.produce = produce
        self.returncode = returncode
        self.raises = raises
        self.cmd = None
        self.kwargs = {}

    def __call__(self, cmd, **kwargs):
        self.cmd = cmd
        self.kwargs = kwargs
        if self.raises:
            raise self.raises
        if self.produce and self.out_dir:
            (Path(self.out_dir) / self.produce).write_text("Src IP\n10.0.0.1\n")
        return subprocess.CompletedProcess(cmd, self.returncode, b"", b"")


@pytest.fixture
def pcap(tmp_path):
    p = tmp_path / "capture.pcap"
    p.write_bytes(b"\xd4\xc3\xb2\xa1")
    return p


@pytest.fixture
def out(tmp_path):
    d = tmp_path / "csv"
    d.mkdir()
    return d


def test_returns_the_produced_csv(out, pcap):
    result = pcap_to_csv(pcap, out, cfm_home=Path("/opt/cfm"), runner=FakeRunner(out))
    assert result.name == "capture_ISCX.csv"


def test_invokes_the_converter_with_the_pcap_and_output_dir(out, pcap):
    runner = FakeRunner(out)
    pcap_to_csv(pcap, out, cfm_home=Path("/opt/cfm"), runner=runner)
    assert str(pcap) in runner.cmd
    # V3 requires a trailing separator on the output directory.
    assert f"{out}/" in runner.cmd


def test_runs_the_v3_jar_with_its_native_library_path(out, pcap):
    """CICFlowMeter-V3 is the version the models were trained against."""
    runner = FakeRunner(out)
    pcap_to_csv(pcap, out, cfm_home=Path("/opt/cfm"), runner=runner)
    assert runner.cmd[0] == "java"
    assert "-Djava.library.path=/opt/cfm" in runner.cmd
    assert "/opt/cfm/CICFlowMeterV3.jar" in runner.cmd
    assert "-jar" in runner.cmd


def test_java_heap_is_configurable(out, pcap):
    runner = FakeRunner(out)
    pcap_to_csv(pcap, out, cfm_home=Path("/opt/cfm"), java_opts="-Xmx512m", runner=runner)
    assert "-Xmx512m" in runner.cmd


def test_the_pcap_is_not_deleted_by_the_converter(out, pcap):
    pcap_to_csv(pcap, out, cfm_home=Path("/opt/cfm"), runner=FakeRunner(out))
    assert pcap.is_file()


def test_passes_the_timeout_through(out, pcap):
    runner = FakeRunner(out)
    pcap_to_csv(pcap, out, cfm_home=Path("/opt/cfm"), timeout=42, runner=runner)
    assert runner.kwargs["timeout"] == 42


def test_nonzero_exit_raises(out, pcap):
    with pytest.raises(FlowMeterError, match="exit"):
        pcap_to_csv(pcap, out, cfm_home=Path("/opt/cfm"),
                    runner=FakeRunner(out, produce=None, returncode=1))


def test_timeout_raises(out, pcap):
    runner = FakeRunner(out, raises=subprocess.TimeoutExpired("cfm", 5))
    with pytest.raises(FlowMeterError, match="timed out"):
        pcap_to_csv(pcap, out, cfm_home=Path("/opt/cfm"), runner=runner)


def test_no_csv_produced_raises(out, pcap):
    with pytest.raises(FlowMeterError, match="no CSV"):
        pcap_to_csv(pcap, out, cfm_home=Path("/opt/cfm"), runner=FakeRunner(out, produce=None))


def test_missing_pcap_raises(tmp_path, out):
    with pytest.raises(FlowMeterError, match="not found"):
        pcap_to_csv(tmp_path / "nope.pcap", out, cfm_home=Path("/opt/cfm"),
                    runner=FakeRunner(out))


def test_newest_csv_wins_when_several_exist(out, pcap):
    stale = out / "old_ISCX.csv"
    stale.write_text("Src IP\n")
    os.utime(stale, (1, 1))
    time.sleep(0.01)
    result = pcap_to_csv(pcap, out, cfm_home=Path("/opt/cfm"), runner=FakeRunner(out))
    assert result.name == "capture_ISCX.csv"


def test_read_flows_renames_and_reconstructs(tmp_path):
    csv = tmp_path / "f.csv"
    csv.write_text("Src IP,Fwd Header Len,Fwd Pkt Len Min\n10.0.0.1,40,0\n")
    df = read_flows(csv)
    assert "Source IP" in df.columns
    assert df["Fwd Header Length.1"].tolist() == [40]


def test_read_flows_on_header_only_csv_returns_empty_frame(tmp_path):
    """Review Focus 1, at the read boundary."""
    csv = tmp_path / "f.csv"
    csv.write_text("Src IP,Protocol\n")
    df = read_flows(csv)
    assert len(df) == 0
    assert "Source IP" in df.columns


def test_read_flows_on_a_missing_file_raises(tmp_path):
    with pytest.raises(FlowMeterError):
        read_flows(tmp_path / "gone.csv")
