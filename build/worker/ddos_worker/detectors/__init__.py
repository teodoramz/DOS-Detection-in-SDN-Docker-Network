"""Detector selection. A model if one is present, otherwise the heuristic."""

from __future__ import annotations

import logging
from pathlib import Path

from .base import Detector
from .heuristic import HeuristicDetector
from .model import MODEL_FILENAME, ModelDetector

log = logging.getLogger(__name__)

MODEL_NAMES = {
    "top": "xgboost-top-v1",
    "inter": "xgboost-inter-v1",
    "bottom": "xgboost-bottom-v1",
}

__all__ = ["Detector", "HeuristicDetector", "ModelDetector", "build_detector"]


def build_detector(layer: str, model_dir, mode: str = "auto") -> Detector:
    """Pick a detector for ``layer``.

    ``mode`` is "auto" (model if its artifacts exist, else heuristic), "model"
    (require one) or "heuristic" (force the placeholder).
    """
    model_dir = Path(model_dir)
    has_model = (model_dir / MODEL_FILENAME).is_file()

    if mode == "heuristic" or (mode == "auto" and not has_model):
        log.warning(
            "layer %s is running the rule-based placeholder, not a trained model", layer
        )
        return HeuristicDetector(layer)

    if mode == "model" and not has_model:
        raise FileNotFoundError(f"no {MODEL_FILENAME} in {model_dir}")

    return ModelDetector(model_dir, name=MODEL_NAMES.get(layer, f"{layer}-model"))
