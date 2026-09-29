"""The detector must not assume XGBoost: any fitted estimator or pipeline works."""
import numpy as np
import pandas as pd
import pytest

from ddos_worker.detectors import build_detector
from ddos_worker.detectors.model import ModelDetector

MODEL_DIR = "build/worker/models/top"


class RandomForestClassifier:
    def predict_proba(self, X):
        p = np.full(len(X), 0.4)
        return np.column_stack([1 - p, p])


class SVC:
    """No predict_proba, as sklearn's SVC lacks it unless probability=True."""

    def __init__(self):
        self.seen = None

    def decision_function(self, X):
        self.seen = X
        return np.array([0.0] * len(X))


class KerasLike:
    """Returns probabilities straight from predict, as a Keras model does."""

    def predict(self, X, **kwargs):
        return np.full((len(X), 1), 0.8)


class Pipeline:
    """Stands in for an sklearn Pipeline that preprocesses internally."""

    def __init__(self, final):
        self.steps = [("prep", object()), ("clf", final)]
        self.seen = None

    def predict_proba(self, X):
        self.seen = X
        p = np.full(len(X), 0.6)
        return np.column_stack([1 - p, p])


def frame(n=2):
    return pd.DataFrame({"Protocol": [17] * n, "Source IP": ["10.0.1.5"] * n})


def test_name_is_derived_from_the_estimator_class():
    det = ModelDetector(MODEL_DIR, layer="inter", estimator=RandomForestClassifier())
    assert det.name == "inter-randomforestclassifier"


def test_name_of_a_pipeline_comes_from_its_final_estimator():
    det = ModelDetector(MODEL_DIR, layer="top", estimator=Pipeline(RandomForestClassifier()))
    assert det.name == "top-randomforestclassifier"


def test_an_explicit_name_still_wins():
    det = ModelDetector(MODEL_DIR, layer="top", name="custom", estimator=RandomForestClassifier())
    assert det.name == "custom"


def test_random_forest_scores_like_any_other_estimator():
    det = ModelDetector(MODEL_DIR, layer="top", estimator=RandomForestClassifier())
    assert det.score(frame()).tolist() == [0.4, 0.4]


def test_estimator_without_predict_proba_uses_decision_function():
    est = SVC()
    det = ModelDetector(MODEL_DIR, layer="inter", estimator=est)
    probs = det.score(frame())
    assert probs.tolist() == [0.5, 0.5]
    assert est.seen is not None


def test_estimator_with_only_predict_is_used_directly():
    det = ModelDetector(MODEL_DIR, layer="bottom", estimator=KerasLike())
    assert det.score(frame()).tolist() == [0.8, 0.8]


def test_probabilities_are_clipped_to_the_unit_interval():
    class OutOfRange:
        def predict(self, X):
            return np.array([-3.0, 7.0])

    det = ModelDetector(MODEL_DIR, layer="top", estimator=OutOfRange())
    assert det.score(frame()).tolist() == [0.0, 1.0]


def test_matrix_mode_when_preprocessing_vectors_are_present():
    det = ModelDetector(MODEL_DIR, layer="top", estimator=RandomForestClassifier())
    assert det.preprocessing == "matrix"
    assert det.spec is not None


def test_pipeline_without_vectors_gets_the_raw_named_frame(tmp_path):
    """A self-contained Pipeline does its own imputing and scaling."""
    est = Pipeline(RandomForestClassifier())
    det = ModelDetector(tmp_path, layer="top", estimator=est)
    assert det.preprocessing == "frame"
    assert det.spec is None
    det.score(frame())
    assert isinstance(est.seen, pd.DataFrame)
    assert "Protocol" in est.seen.columns


def test_frame_mode_on_an_empty_capture_returns_no_scores(tmp_path):
    det = ModelDetector(tmp_path, layer="top", estimator=Pipeline(RandomForestClassifier()))
    assert det.score(pd.DataFrame()).shape == (0,)


def test_build_detector_names_the_layer_and_algorithm():
    """Needs the real artifact, so it runs only where its library is installed."""
    pytest.importorskip("xgboost")
    det = build_detector("top", MODEL_DIR, mode="model")
    assert det.name == "top-xgbclassifier"


class PipelineWithDeclaredColumns:
    """A fitted sklearn pipeline advertises the columns it was fitted on."""

    def __init__(self):
        self.feature_names_in_ = np.array(["a", "b", "c"])
        self.steps = [("clf", RandomForestClassifier())]
        self.seen = None

    def predict_proba(self, X):
        self.seen = X
        p = np.full(len(X), 0.3)
        return np.column_stack([1 - p, p])


def test_frame_mode_supplies_every_column_the_model_declares(tmp_path):
    est = PipelineWithDeclaredColumns()
    det = ModelDetector(tmp_path, layer="top", estimator=est)
    det.score(pd.DataFrame({"a": [1.0], "Source IP": ["10.0.1.5"]}))
    assert list(est.seen.columns) == ["a", "b", "c"]
    assert est.seen["b"].isna().all()


def test_frame_mode_drops_columns_the_model_was_not_fitted_on(tmp_path):
    est = PipelineWithDeclaredColumns()
    det = ModelDetector(tmp_path, layer="top", estimator=est)
    det.score(pd.DataFrame({"a": [1.0], "b": [2.0], "c": [3.0], "Source IP": ["10.0.1.5"]}))
    assert "Source IP" not in est.seen.columns


def test_frame_mode_passes_the_frame_unchanged_when_nothing_is_declared(tmp_path):
    est = Pipeline(RandomForestClassifier())
    det = ModelDetector(tmp_path, layer="top", estimator=est)
    det.score(frame())
    assert "Source IP" in est.seen.columns


def test_incomplete_vectors_fall_back_to_frame_mode(tmp_path):
    """Choosing matrix mode on the order file alone crashed at startup, and the
    restart destroyed the container's veth."""
    np.save(tmp_path / "top_features.npy", np.array(["a", "b"]))
    det = ModelDetector(tmp_path, layer="top", estimator=RandomForestClassifier())
    assert det.preprocessing == "frame"
    assert det.spec is None


def test_matrix_mode_needs_all_four_vectors(tmp_path):
    np.save(tmp_path / "top_features.npy", np.array(["a"]))
    for name in ("medians25.npy", "scaler_mean25.npy", "scaler_std25.npy"):
        np.save(tmp_path / name, np.zeros(1))
    det = ModelDetector(tmp_path, layer="top", estimator=RandomForestClassifier())
    assert det.preprocessing == "matrix"
