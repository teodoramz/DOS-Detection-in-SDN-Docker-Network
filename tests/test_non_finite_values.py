"""CICFlowMeter writes Infinity for zero-duration flows, which single-packet
floods produce constantly. Every estimator except XGBoost rejects it."""
import numpy as np
import pandas as pd

from ddos_worker.features import FeatureSpec, build_matrix
from ddos_worker.flowmeter import read_flows


def spec(n=2):
    return FeatureSpec(
        order=["a", "b"][:n],
        medians=np.array([5.0, 7.0])[:n],
        mean=np.zeros(n),
        std=np.ones(n),
    )


def test_positive_infinity_is_imputed_not_passed_through():
    X, _ = build_matrix(pd.DataFrame({"a": ["Infinity"], "b": [1.0]}), spec())
    assert np.isfinite(X).all()
    assert X[0][0] == 5.0


def test_negative_infinity_is_imputed():
    X, _ = build_matrix(pd.DataFrame({"a": [-np.inf], "b": [1.0]}), spec())
    assert np.isfinite(X).all()
    assert X[0][0] == 5.0


def test_a_real_value_alongside_infinity_is_untouched():
    X, _ = build_matrix(pd.DataFrame({"a": [np.inf, 2.0], "b": [1.0, 1.0]}), spec())
    assert X[1][0] == 2.0


def test_read_flows_strips_infinities_for_self_contained_pipelines(tmp_path):
    """frame mode hands these columns straight to the model."""
    csv = tmp_path / "f.csv"
    csv.write_text("Src IP,Flow Byts/s,Flow Pkts/s\n10.0.0.1,Infinity,Infinity\n")
    df = read_flows(csv)
    values = df[["Flow Bytes/s", "Flow Packets/s"]].to_numpy(dtype=float)
    assert not np.isinf(values).any()


def test_read_flows_keeps_ordinary_values(tmp_path):
    csv = tmp_path / "f.csv"
    csv.write_text("Src IP,Flow Byts/s\n10.0.0.1,1234.5\n")
    assert read_flows(csv)["Flow Bytes/s"].tolist() == [1234.5]


def test_a_sklearn_style_estimator_accepts_the_matrix():
    """sklearn raises ValueError on infinity; the matrix must never contain one."""
    X, _ = build_matrix(
        pd.DataFrame({"a": ["Infinity", "-Infinity", "3"], "b": [1.0, 2.0, 3.0]}), spec()
    )
    assert np.isfinite(X).all()
