import numpy as np
import pandas as pd
import pytest

from ddos_worker.detectors import build_detector
from ddos_worker.detectors.base import Detector
from ddos_worker.detectors.heuristic import HeuristicDetector
from ddos_worker.detectors.model import ModelDetector

MODEL_DIR = "build/worker/models/top"


class FakeEstimator:
    """Stands in for the XGBClassifier so tests need no xgboost."""

    def __init__(self):
        self.seen = None

    def predict_proba(self, X):
        self.seen = X
        p = np.full(len(X), 0.75)
        return np.column_stack([1 - p, p])


def test_model_detector_returns_positive_class_probability():
    det = ModelDetector(MODEL_DIR, name="xgboost-top-v1", estimator=FakeEstimator())
    probs = det.score(pd.DataFrame({"Protocol": [17, 6]}))
    assert probs.tolist() == [0.75, 0.75]


def test_model_detector_feeds_the_spec_ordered_matrix():
    est = FakeEstimator()
    det = ModelDetector(MODEL_DIR, name="xgboost-top-v1", estimator=est)
    det.score(pd.DataFrame({"Protocol": [17]}))
    assert est.seen.shape == (1, 25)


def test_model_detector_on_empty_frame_returns_empty_array():
    det = ModelDetector(MODEL_DIR, name="x", estimator=FakeEstimator())
    assert det.score(pd.DataFrame({"Protocol": []})).shape == (0,)


def test_model_detector_exposes_its_name():
    det = ModelDetector(MODEL_DIR, name="xgboost-top-v1", estimator=FakeEstimator())
    assert det.name == "xgboost-top-v1"


@pytest.mark.parametrize("layer", ["inter", "bottom"])
def test_heuristic_scores_are_probabilities(layer):
    df = pd.DataFrame({
        "SYN Flag Count": [0, 1, 40],
        "Total Fwd Packets": [10, 1, 40],
        "Flow Packets/s": [1.0, 5000.0, 20000.0],
        "Average Packet Size": [800.0, 40.0, 40.0],
        "Flow Duration": [1000.0, 5e7, 1e6],
        "Flow Bytes/s": [5000.0, 3.0, 10.0],
        "Fwd PSH Flags": [0, 1, 1],
    })
    probs = HeuristicDetector(layer).score(df)
    assert probs.shape == (3,)
    assert np.all((probs >= 0.0) & (probs <= 1.0))


def test_inter_heuristic_ranks_a_syn_flood_above_a_normal_flow():
    df = pd.DataFrame({
        "SYN Flag Count": [0, 100],
        "Total Fwd Packets": [100, 100],
        "Flow Packets/s": [2.0, 30000.0],
        "Average Packet Size": [900.0, 40.0],
    })
    probs = HeuristicDetector("inter").score(df)
    assert probs[1] > probs[0]


def test_bottom_heuristic_ranks_a_slow_flow_above_a_normal_flow():
    df = pd.DataFrame({
        "Flow Duration": [50_000.0, 120_000_000.0],
        "Flow Bytes/s": [20000.0, 2.0],
        "Flow Packets/s": [5.0, 0.2],
        "Fwd PSH Flags": [0, 1],
    })
    probs = HeuristicDetector("bottom").score(df)
    assert probs[1] > probs[0]


def test_heuristic_tolerates_missing_columns():
    probs = HeuristicDetector("inter").score(pd.DataFrame({"Protocol": [6, 17]}))
    assert probs.shape == (2,)
    assert np.all(np.isfinite(probs))


def test_heuristic_on_empty_frame_returns_empty_array():
    assert HeuristicDetector("inter").score(pd.DataFrame()).shape == (0,)


def test_heuristic_rejects_an_unknown_layer():
    with pytest.raises(ValueError, match="layer"):
        HeuristicDetector("sideways")


def test_build_detector_picks_heuristic_when_no_model_present(tmp_path):
    det = build_detector("inter", tmp_path)
    assert isinstance(det, HeuristicDetector)
    assert "heuristic" in det.name


def test_build_detector_forced_to_heuristic_even_with_a_model():
    det = build_detector("bottom", MODEL_DIR, mode="heuristic")
    assert isinstance(det, HeuristicDetector)


def test_build_detector_forced_to_model_without_artifacts_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        build_detector("top", tmp_path, mode="model")


def test_detector_interface_is_abstract():
    with pytest.raises(TypeError):
        Detector()


def test_bottom_heuristic_catches_a_volumetric_flood_at_the_application_port():
    """An application tier also receives L4 floods; a burst alone scored below
    the default threshold and the attacker went unblocked in a live run."""
    df = pd.DataFrame({
        "Flow Duration": [80_000.0, 400.0],
        "Flow Bytes/s": [30000.0, 0.0],
        "Flow Packets/s": [8.0, 50000.0],
        "Fwd PSH Flags": [1, 0],
        "SYN Flag Count": [1, 1],
        "Total Fwd Packets": [12, 1],
    })
    probs = HeuristicDetector("bottom").score(df)
    assert probs[1] >= 0.5, "a SYN flood at the application port must be flagged"
    assert probs[0] < 0.5, "ordinary browsing must not be"


def test_bottom_heuristic_still_catches_slow_connections():
    df = pd.DataFrame({
        "Flow Duration": [120_000_000.0, 50_000.0],
        "Flow Bytes/s": [2.0, 20000.0],
        "Flow Packets/s": [0.2, 5.0],
        "Fwd PSH Flags": [1, 0],
        "SYN Flag Count": [0, 0],
        "Total Fwd Packets": [50, 10],
    })
    probs = HeuristicDetector("bottom").score(df)
    assert probs[0] > probs[1]
    assert probs[0] >= 0.5
