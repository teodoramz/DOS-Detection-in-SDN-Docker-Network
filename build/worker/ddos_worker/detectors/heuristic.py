"""Rule-based placeholder for layers that have no trained model yet.

These scores are not model output, only a weighted combination of flow
statistics.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .base import Detector

LAYERS = ("inter", "bottom")


def _column(df: pd.DataFrame, name: str, default: float = 0.0) -> np.ndarray:
    if name not in df.columns:
        return np.full(len(df), default, dtype=float)
    values = pd.to_numeric(df[name], errors="coerce").to_numpy(dtype=float)
    return np.nan_to_num(values, nan=default, posinf=default, neginf=default)


def _ratio(numerator: np.ndarray, denominator: np.ndarray) -> np.ndarray:
    safe = np.where(denominator <= 0, 1.0, denominator)
    return np.clip(numerator / safe, 0.0, 1.0)


class HeuristicDetector(Detector):
    """Weighted flow-statistic rules. A stand-in, never a trained model."""

    def __init__(self, layer: str):
        if layer not in LAYERS:
            raise ValueError(f"no heuristic for layer {layer!r}; expected one of {LAYERS}")
        self.layer = layer
        self.name = f"{layer}-heuristic-v1"

    def score(self, df: pd.DataFrame) -> np.ndarray:
        if len(df) == 0:
            return np.empty(0, dtype=float)
        scorer = self._score_inter if self.layer == "inter" else self._score_bottom
        return np.clip(scorer(df), 0.0, 1.0)

    def _score_inter(self, df: pd.DataFrame) -> np.ndarray:
        """Half-open handshakes, packet rate, tiny packets."""
        syn_ratio = _ratio(_column(df, "SYN Flag Count"), _column(df, "Total Fwd Packets"))
        rate = np.clip(_column(df, "Flow Packets/s") / 1000.0, 0.0, 1.0)
        size = _column(df, "Average Packet Size", default=1500.0)
        tiny = np.clip((100.0 - size) / 100.0, 0.0, 1.0)
        return 0.45 * syn_ratio + 0.35 * rate + 0.20 * tiny

    def _score_bottom(self, df: pd.DataFrame) -> np.ndarray:
        """Slow long-lived flows, and request bursts."""
        duration_s = _column(df, "Flow Duration") / 1_000_000.0
        long_lived = np.clip(duration_s / 30.0, 0.0, 1.0)
        byte_rate = _column(df, "Flow Bytes/s", default=1e6)
        starved = np.clip((100.0 - byte_rate) / 100.0, 0.0, 1.0)
        burst = np.clip(_column(df, "Flow Packets/s") / 200.0, 0.0, 1.0)
        pushes = np.clip(_column(df, "Fwd PSH Flags"), 0.0, 1.0)
        return 0.50 * (long_lived * starved) + 0.35 * burst + 0.15 * pushes
