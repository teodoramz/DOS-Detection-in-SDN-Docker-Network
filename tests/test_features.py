import numpy as np
import pandas as pd
import pytest

from ddos_worker.features import (
    COLUMN_MAPPING,
    FeatureSpec,
    build_matrix,
    ensure_duplicate_header_column,
    rename_columns,
)

MODEL_DIR = "build/worker/models/top"


def test_rename_maps_v4_names_to_dataset_names():
    df = pd.DataFrame({"Src IP": ["10.0.0.1"], "Fwd Pkt Len Min": [0], "Flow Byts/s": [1.0]})
    out = rename_columns(df)
    assert list(out.columns) == ["Source IP", "Fwd Packet Length Min", "Flow Bytes/s"]


def test_rename_leaves_unknown_columns_alone():
    df = pd.DataFrame({"Source IP": ["10.0.0.1"], "Nonsense": [1]})
    assert list(rename_columns(df).columns) == ["Source IP", "Nonsense"]


def test_duplicate_header_column_is_reconstructed():
    df = pd.DataFrame({"Fwd Header Length": [40, 60]})
    out = ensure_duplicate_header_column(df)
    assert out["Fwd Header Length.1"].tolist() == [40, 60]


def test_duplicate_header_column_left_alone_when_present():
    df = pd.DataFrame({"Fwd Header Length": [40], "Fwd Header Length.1": [99]})
    assert ensure_duplicate_header_column(df)["Fwd Header Length.1"].tolist() == [99]


def test_feature_spec_loads_consistent_vectors():
    spec = FeatureSpec.load(MODEL_DIR)
    assert len(spec.order) == 25
    assert spec.medians.shape == spec.mean.shape == spec.std.shape == (25,)


def test_feature_order_is_pinned_to_the_artifact():
    """Regression guard for D7. This order comes from top_features.npy, not a literal."""
    spec = FeatureSpec.load(MODEL_DIR)
    assert spec.order[:5] == [
        "Down/Up Ratio",
        "URG Flag Count",
        "Protocol",
        "min_seg_size_forward",
        "Bwd Packet Length Min",
    ]
    assert spec.order[-1] == "Min Packet Length"


def test_feature_spec_rejects_length_mismatch(tmp_path):
    np.save(tmp_path / "top_features.npy", np.array(["a", "b"]))
    for name in ("medians25.npy", "scaler_mean25.npy", "scaler_std25.npy"):
        np.save(tmp_path / name, np.zeros(3))
    with pytest.raises(ValueError, match="length"):
        FeatureSpec.load(tmp_path)


def test_build_matrix_orders_columns_by_spec():
    spec = FeatureSpec(
        order=["b", "a"],
        medians=np.array([0.0, 0.0]),
        mean=np.array([0.0, 0.0]),
        std=np.array([1.0, 1.0]),
    )
    df = pd.DataFrame({"a": [1.0], "b": [2.0]})
    X, missing = build_matrix(df, spec)
    assert X.tolist() == [[2.0, 1.0]]
    assert missing == []


def test_build_matrix_imputes_missing_column_with_median():
    spec = FeatureSpec(
        order=["a", "b"],
        medians=np.array([0.0, 7.0]),
        mean=np.array([0.0, 0.0]),
        std=np.array([1.0, 1.0]),
    )
    X, missing = build_matrix(pd.DataFrame({"a": [1.0]}), spec)
    assert X.tolist() == [[1.0, 7.0]]
    assert missing == ["b"]


def test_build_matrix_imputes_nan_and_non_numeric_per_column():
    spec = FeatureSpec(
        order=["a", "b"],
        medians=np.array([5.0, 7.0]),
        mean=np.array([0.0, 0.0]),
        std=np.array([1.0, 1.0]),
    )
    df = pd.DataFrame({"a": [np.nan, 1.0], "b": ["oops", 2.0]})
    X, _ = build_matrix(df, spec)
    assert X.tolist() == [[5.0, 7.0], [1.0, 2.0]]


def test_build_matrix_standardises():
    spec = FeatureSpec(
        order=["a"],
        medians=np.array([0.0]),
        mean=np.array([10.0]),
        std=np.array([2.0]),
    )
    X, _ = build_matrix(pd.DataFrame({"a": [14.0]}), spec)
    assert X.tolist() == [[2.0]]


def test_zero_variance_does_not_divide_by_zero():
    spec = FeatureSpec(
        order=["a"],
        medians=np.array([0.0]),
        mean=np.array([3.0]),
        std=np.array([0.0]),
    )
    X, _ = build_matrix(pd.DataFrame({"a": [5.0]}), spec)
    assert np.isfinite(X).all()
    assert X.tolist() == [[2.0]]


def test_build_matrix_on_empty_frame_returns_empty_matrix():
    spec = FeatureSpec(
        order=["a"],
        medians=np.array([0.0]),
        mean=np.array([0.0]),
        std=np.array([1.0]),
    )
    X, _ = build_matrix(pd.DataFrame({"a": []}), spec)
    assert X.shape == (0, 1)


def test_mapping_covers_the_renames_the_artifact_needs():
    assert COLUMN_MAPPING["Src IP"] == "Source IP"
    assert COLUMN_MAPPING["Fwd Seg Size Min"] == "min_seg_size_forward"
