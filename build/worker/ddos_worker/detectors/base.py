"""The contract every layer's detector satisfies."""

from __future__ import annotations

import abc

import numpy as np
import pandas as pd


class Detector(abc.ABC):
    """Scores flow records. One probability of attack per row, in [0, 1]."""

    name: str = "detector"

    @abc.abstractmethod
    def score(self, df: pd.DataFrame) -> np.ndarray:
        """Return one probability per row of ``df``.

        ``df`` carries CIC-DDoS2019 column names and raw, unscaled values.
        """
