"""Turn per-flow probabilities into at most one alert per source IP.

The thesis triggers on a single flow over the threshold. This aggregates
instead, because section 5.3 records benign proxy and application flows
scoring 0.7-0.9; ``min_flows=1`` restores the literal behaviour.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

SOURCE_IP_COLUMN = "Source IP"


@dataclass(frozen=True)
class Alert:
    layer: str
    source_ip: str
    flows_total: int
    flows_malicious: int
    max_probability: float
    threshold: float
    detector: str
    window_start: str
    window_end: str

    def to_dict(self) -> dict:
        return asdict(self)


def aggregate(
    df: pd.DataFrame,
    probs: np.ndarray,
    *,
    layer: str,
    detector: str,
    threshold: float,
    min_flows: int,
    window_start: str,
    window_end: str,
) -> list[Alert]:
    """One alert per source IP with at least ``min_flows`` flows at or above
    ``threshold``, most severe first."""
    if len(df) != len(probs):
        raise ValueError(f"{len(probs)} probabilities for {len(df)} rows")
    if len(df) == 0 or SOURCE_IP_COLUMN not in df.columns:
        return []

    work = pd.DataFrame({
        "source_ip": df[SOURCE_IP_COLUMN].astype("object"),
        "probability": np.asarray(probs, dtype=float),
    }).dropna(subset=["source_ip"])
    work = work[work["source_ip"].astype(str).str.len() > 0]
    if work.empty:
        return []

    alerts = []
    for source_ip, rows in work.groupby("source_ip", sort=False):
        malicious = int((rows["probability"] >= threshold).sum())
        if malicious < min_flows:
            continue
        alerts.append(
            Alert(
                layer=layer,
                source_ip=str(source_ip),
                flows_total=int(len(rows)),
                flows_malicious=malicious,
                max_probability=round(float(rows["probability"].max()), 6),
                threshold=float(threshold),
                detector=detector,
                window_start=window_start,
                window_end=window_end,
            )
        )

    alerts.sort(key=lambda a: (a.max_probability, a.flows_malicious), reverse=True)
    return alerts
