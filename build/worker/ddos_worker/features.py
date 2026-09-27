"""Turn a CICFlowMeter CSV into the matrix the trained model expects.

The feature order is read from ``top_features.npy`` at load time and never
hardcoded. An earlier version of this pipeline hardcoded a different 25-name
list, which silently scrambled every input; the tests pin the artifact order so
that cannot recur.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

#: CICFlowMeter output names to the CIC-DDoS2019 names the models were trained
#: on. Taken from the original ``normalize.py``.
COLUMN_MAPPING: dict[str, str] = {
    "Flow ID": "Flow ID",
    "Src IP": "Source IP",
    "Src Port": "Source Port",
    "Dst IP": "Destination IP",
    "Dst Port": "Destination Port",
    "Protocol": "Protocol",
    "Timestamp": "Timestamp",
    "Flow Duration": "Flow Duration",
    "Tot Fwd Pkts": "Total Fwd Packets",
    "Tot Bwd Pkts": "Total Backward Packets",
    "TotLen Fwd Pkts": "Total Length of Fwd Packets",
    "Total Length of Bwd Packet": "Total Length of Bwd Packets",
    "TotLen Bwd Pkts": "Total Length of Bwd Packets",
    "Fwd Pkt Len Max": "Fwd Packet Length Max",
    "Fwd Pkt Len Min": "Fwd Packet Length Min",
    "Fwd Pkt Len Mean": "Fwd Packet Length Mean",
    "Fwd Pkt Len Std": "Fwd Packet Length Std",
    "Bwd Pkt Len Max": "Bwd Packet Length Max",
    "Bwd Pkt Len Min": "Bwd Packet Length Min",
    "Bwd Pkt Len Mean": "Bwd Packet Length Mean",
    "Bwd Pkt Len Std": "Bwd Packet Length Std",
    "Flow Byts/s": "Flow Bytes/s",
    "Flow Pkts/s": "Flow Packets/s",
    "Flow IAT Mean": "Flow IAT Mean",
    "Flow IAT Std": "Flow IAT Std",
    "Flow IAT Max": "Flow IAT Max",
    "Flow IAT Min": "Flow IAT Min",
    "Fwd IAT Tot": "Fwd IAT Total",
    "Fwd IAT Mean": "Fwd IAT Mean",
    "Fwd IAT Std": "Fwd IAT Std",
    "Fwd IAT Max": "Fwd IAT Max",
    "Fwd IAT Min": "Fwd IAT Min",
    "Bwd IAT Tot": "Bwd IAT Total",
    "Bwd IAT Mean": "Bwd IAT Mean",
    "Bwd IAT Std": "Bwd IAT Std",
    "Bwd IAT Max": "Bwd IAT Max",
    "Bwd IAT Min": "Bwd IAT Min",
    "Fwd PSH Flags": "Fwd PSH Flags",
    "Bwd PSH Flags": "Bwd PSH Flags",
    "Fwd URG Flags": "Fwd URG Flags",
    "Bwd URG Flags": "Bwd URG Flags",
    "Fwd Header Len": "Fwd Header Length",
    "Bwd Header Len": "Bwd Header Length",
    "Fwd Pkts/s": "Fwd Packets/s",
    "Bwd Pkts/s": "Bwd Packets/s",
    "Packet Length Min": "Min Packet Length",
    "Pkt Len Min": "Min Packet Length",
    "Packet Length Max": "Max Packet Length",
    "Pkt Len Max": "Max Packet Length",
    "Pkt Len Mean": "Packet Length Mean",
    "Pkt Len Std": "Packet Length Std",
    "Pkt Len Var": "Packet Length Variance",
    "FIN Flag Cnt": "FIN Flag Count",
    "SYN Flag Cnt": "SYN Flag Count",
    "RST Flag Cnt": "RST Flag Count",
    "PSH Flag Cnt": "PSH Flag Count",
    "ACK Flag Cnt": "ACK Flag Count",
    "URG Flag Cnt": "URG Flag Count",
    "CWR Flag Count": "CWE Flag Count",
    "CWE Flag Count": "CWE Flag Count",
    "ECE Flag Cnt": "ECE Flag Count",
    "Down/Up Ratio": "Down/Up Ratio",
    "Pkt Size Avg": "Average Packet Size",
    "Fwd Segment Size Avg": "Avg Fwd Segment Size",
    "Bwd Segment Size Avg": "Avg Bwd Segment Size",
    "Fwd Byts/b Avg": "Fwd Avg Bytes/Bulk",
    "Fwd Pkts/b Avg": "Fwd Avg Packets/Bulk",
    "Fwd Blk Rate Avg": "Fwd Avg Bulk Rate",
    "Bwd Byts/b Avg": "Bwd Avg Bytes/Bulk",
    "Bwd Pkts/b Avg": "Bwd Avg Packets/Bulk",
    "Bwd Blk Rate Avg": "Bwd Avg Bulk Rate",
    "Subflow Fwd Pkts": "Subflow Fwd Packets",
    "Subflow Fwd Byts": "Subflow Fwd Bytes",
    "Subflow Bwd Pkts": "Subflow Bwd Packets",
    "Subflow Bwd Byts": "Subflow Bwd Bytes",
    "FWD Init Win Bytes": "Init_Win_bytes_forward",
    "Init Fwd Win Byts": "Init_Win_bytes_forward",
    "Bwd Init Win Bytes": "Init_Win_bytes_backward",
    "Init Bwd Win Byts": "Init_Win_bytes_backward",
    "Fwd Act Data Pkts": "act_data_pkt_fwd",
    "Fwd Seg Size Min": "min_seg_size_forward",
    "Active Mean": "Active Mean",
    "Active Std": "Active Std",
    "Active Max": "Active Max",
    "Active Min": "Active Min",
    "Idle Mean": "Idle Mean",
    "Idle Std": "Idle Std",
    "Idle Max": "Idle Max",
    "Idle Min": "Idle Min",
    "Label": "Label",
}

#: Present in the CIC-DDoS2019 CSVs only because the header repeats
#: "Fwd Header Length" and pandas de-duplicates it with a suffix. The trained
#: model expects the column, so a measured CSV carrying one copy gets a second.
DUPLICATE_HEADER_COLUMN = "Fwd Header Length.1"


@dataclass
class FeatureSpec:
    """The feature contract saved alongside a trained model."""

    order: list[str]
    medians: np.ndarray
    mean: np.ndarray
    std: np.ndarray

    def __post_init__(self) -> None:
        n = len(self.order)
        if not (self.medians.shape == self.mean.shape == self.std.shape == (n,)):
            raise ValueError(
                "preprocessing vectors disagree with the feature length: "
                f"{n} features, medians {self.medians.shape}, "
                f"mean {self.mean.shape}, std {self.std.shape}"
            )

    @classmethod
    def load(cls, model_dir: str | Path) -> "FeatureSpec":
        # allow_pickle is needed because numpy stores a string array as objects.
        # These artifacts are the project's own trained-model files, committed to
        # this repository, not input from anywhere untrusted.
        model_dir = Path(model_dir)
        return cls(
            order=[str(c) for c in np.load(model_dir / "top_features.npy", allow_pickle=True)],
            medians=np.load(model_dir / "medians25.npy").astype(float),
            mean=np.load(model_dir / "scaler_mean25.npy").astype(float),
            std=np.load(model_dir / "scaler_std25.npy").astype(float),
        )

    @property
    def safe_std(self) -> np.ndarray:
        """Standard deviations with zeros replaced, so scaling cannot divide by zero."""
        std = self.std.astype(float).copy()
        std[std == 0] = 1.0
        return std


def rename_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Rename only the columns present, so both V3 and V4 output are accepted."""
    present = {old: new for old, new in COLUMN_MAPPING.items() if old in df.columns}
    return df.rename(columns=present)


def ensure_duplicate_header_column(df: pd.DataFrame) -> pd.DataFrame:
    if DUPLICATE_HEADER_COLUMN in df.columns or "Fwd Header Length" not in df.columns:
        return df
    out = df.copy()
    out[DUPLICATE_HEADER_COLUMN] = out["Fwd Header Length"]
    return out


def build_matrix(df: pd.DataFrame, spec: FeatureSpec) -> tuple[np.ndarray, list[str]]:
    """Return the scaled feature matrix and the feature names that were absent."""
    missing = [name for name in spec.order if name not in df.columns]

    frame = pd.DataFrame(index=df.index)
    for name in spec.order:
        frame[name] = df[name] if name in df.columns else np.nan

    X = frame.apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)

    if X.size:
        nan = np.isnan(X)
        if nan.any():
            X[nan] = np.take(spec.medians, np.where(nan)[1])
        X = (X - spec.mean) / spec.safe_std

    return X, missing
