"""Detector backed by a trained model saved as models.joblib.

Any fitted estimator works: tree ensembles, boosting, linear models, SVMs,
neural networks, or a full pipeline that preprocesses internally.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

from ..features import FeatureSpec, build_matrix
from .base import Detector

log = logging.getLogger(__name__)

MODEL_FILENAME = "models.joblib"
FEATURE_ORDER_FILENAME = "top_features.npy"


def _final_estimator(estimator):
    steps = getattr(estimator, "steps", None)
    if steps:
        return steps[-1][1]
    return estimator


def _algorithm_of(estimator) -> str:
    return type(_final_estimator(estimator)).__name__


def _probabilities(estimator, X) -> np.ndarray:
    """One probability of attack per row, whatever interface the model offers."""
    if hasattr(estimator, "predict_proba"):
        proba = np.asarray(estimator.predict_proba(X), dtype=float)
        scores = proba[:, 1] if proba.ndim == 2 and proba.shape[1] > 1 else proba.ravel()
    elif hasattr(estimator, "decision_function"):
        margins = np.asarray(estimator.decision_function(X), dtype=float).ravel()
        scores = 1.0 / (1.0 + np.exp(-margins))
    else:
        scores = np.asarray(estimator.predict(X), dtype=float).ravel()
    return np.clip(scores, 0.0, 1.0)


class ModelDetector(Detector):
    """Scores flows with a trained model.

    Two preprocessing modes, chosen by what sits next to the model:

    ``matrix``
        The directory holds the feature order and scaler vectors, so the model
        is a bare estimator and this class imputes, orders and scales for it.
    ``frame``
        No vectors, so the model is assumed self-contained and receives the
        renamed flow records as a DataFrame.
    """

    def __init__(self, model_dir, name: str | None = None, layer: str | None = None,
                 estimator=None):
        self.model_dir = Path(model_dir)

        has_vectors = (self.model_dir / FEATURE_ORDER_FILENAME).is_file()
        self.spec = FeatureSpec.load(self.model_dir) if has_vectors else None
        self.preprocessing = "matrix" if has_vectors else "frame"

        if estimator is None:
            # joblib.load unpickles: the project's own model file, not
            # untrusted input.
            import joblib

            estimator = joblib.load(self.model_dir / MODEL_FILENAME)
        self.estimator = estimator

        self.algorithm = _algorithm_of(estimator)
        self.name = name or f"{layer or 'model'}-{self.algorithm.lower()}"

    def _align(self, df: pd.DataFrame) -> pd.DataFrame:
        """Give a self-contained model exactly the columns it was fitted on."""
        declared = getattr(self.estimator, "feature_names_in_", None)
        if declared is None:
            return df
        names = [str(c) for c in declared]
        missing = [name for name in names if name not in df.columns]
        if missing:
            log.warning(
                "%d of %d declared columns absent from the capture: %s",
                len(missing), len(names), ", ".join(missing[:10]),
            )
        return df.reindex(columns=names)

    def score(self, df: pd.DataFrame) -> np.ndarray:
        if len(df) == 0:
            return np.empty(0, dtype=float)

        if self.spec is None:
            return _probabilities(self.estimator, self._align(df))

        X, missing = build_matrix(df, self.spec)
        if missing:
            log.warning(
                "%d of %d features absent from the capture, imputed from medians: %s",
                len(missing), len(self.spec.order), ", ".join(missing),
            )
        if X.shape[0] == 0:
            return np.empty(0, dtype=float)
        return _probabilities(self.estimator, X)
