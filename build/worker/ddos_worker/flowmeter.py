"""Run CICFlowMeter-V3 over a pcap and read the flow records it writes."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

import pandas as pd

from .features import ensure_duplicate_header_column, rename_columns

log = logging.getLogger(__name__)

CICFLOWMETER_JAR = "CICFlowMeterV3.jar"


class FlowMeterError(RuntimeError):
    """The converter failed, timed out, or produced nothing."""


def pcap_to_csv(
    pcap: Path,
    out_dir: Path,
    *,
    cfm_home: Path,
    timeout: int = 300,
    java_opts: str = "",
    runner=subprocess.run,
) -> Path:
    """Convert one pcap and return the CSV of flow records.

    The jar is invoked directly rather than through the upstream shell wrapper,
    which deletes the pcap and whose V3 code path is commented out.
    """
    pcap, out_dir, cfm_home = Path(pcap), Path(out_dir), Path(cfm_home)
    if not pcap.is_file():
        raise FlowMeterError(f"pcap not found: {pcap}")
    out_dir.mkdir(parents=True, exist_ok=True)

    before = {p: p.stat().st_mtime for p in out_dir.glob("*.csv")}
    cmd = ["java", f"-Djava.library.path={cfm_home}"]
    cmd += [opt for opt in java_opts.split() if opt]
    cmd += ["-jar", str(cfm_home / CICFLOWMETER_JAR), str(pcap), f"{out_dir}/"]

    try:
        result = runner(cmd, cwd=str(cfm_home), capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise FlowMeterError(f"CICFlowMeter timed out after {timeout}s on {pcap.name}") from exc

    if result.returncode != 0:
        stderr = (result.stderr or b"").decode(errors="replace")[-2000:]
        raise FlowMeterError(f"CICFlowMeter exit {result.returncode} on {pcap.name}: {stderr}")

    produced = [
        p for p in out_dir.glob("*.csv")
        if p not in before or p.stat().st_mtime > before[p]
    ]
    if not produced:
        raise FlowMeterError(f"CICFlowMeter produced no CSV for {pcap.name}")

    return max(produced, key=lambda p: p.stat().st_mtime)


def read_flows(csv_path: Path) -> pd.DataFrame:
    """Read a converter CSV into dataset-named columns."""
    csv_path = Path(csv_path)
    if not csv_path.is_file():
        raise FlowMeterError(f"flow CSV not found: {csv_path}")
    try:
        df = pd.read_csv(csv_path, low_memory=False)
    except pd.errors.EmptyDataError as exc:
        raise FlowMeterError(f"flow CSV is empty: {csv_path}") from exc
    return ensure_duplicate_header_column(rename_columns(df))
