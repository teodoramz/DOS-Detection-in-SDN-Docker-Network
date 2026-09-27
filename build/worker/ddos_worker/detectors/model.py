"""Detector backed by the trained classifier saved as models.joblib."""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

from ..features import FeatureSpec, build_matrix
from .base import Detector

log = logging.getLogger(__name__)

MODEL_FILENAME = "models.joblib"


class ModelDetector(Detector):
    def __init__(self, model_dir, name: str = "model", estimator=None):
        self.model_dir = Path(model_dir)
        self.name = name
        self.spec = FeatureSpec.load(self.model_dir)
        if estimator is None:
            # joblib.load unpickles. The file is this project's own trained
            # model, committed to this repository, not untrusted input.
            import joblib

            estimator = joblib.load(self.model_dir / MODEL_FILENAME)
        self.estimator = estimator

    def score(self, df: pd.DataFrame) -> np.ndarray:
        X, missing = build_matrix(df, self.spec)
        if missing:
            log.warning(
                "%d of %d features absent from the capture, imputed from medians: %s",
                len(missing), len(self.spec.order), ", ".join(missing),
            )
        if X.shape[0] == 0:
            return np.empty(0, dtype=float)
        return np.asarray(self.estimator.predict_proba(X))[:, 1].astype(float)
