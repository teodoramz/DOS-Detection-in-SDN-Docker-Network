"""Every feature the model needs must be reachable from real converter output.

The header fixture is the literal first line CICFlowMeter-4.0 wrote for a
capture taken on the testbed. If the converter is changed or upgraded and its
names drift, this fails instead of silently imputing medians.
"""
from pathlib import Path

import pandas as pd
import pytest

from ddos_worker.features import (
    FeatureSpec,
    ensure_duplicate_header_column,
    rename_columns,
)

MODEL_DIRS = {
    layer: Path(f"build/worker/models/{layer}")
    for layer in ("top", "inter", "bottom")
}
HEADER = Path("tests/fixtures/cicflowmeter4_header.csv")


def converter_frame():
    names = [c.strip() for c in HEADER.read_text().strip().split(",")]
    return pd.DataFrame({name: [0] for name in names})


def test_the_fixture_looks_like_converter_output():
    names = [c.strip() for c in HEADER.read_text().strip().split(",")]
    assert len(names) > 80
    assert "Src IP" in names


@pytest.mark.parametrize("layer", sorted(MODEL_DIRS))
def test_every_model_feature_is_produced_by_the_converter(layer):
    spec = FeatureSpec.load(MODEL_DIRS[layer])
    available = set(ensure_duplicate_header_column(rename_columns(converter_frame())).columns)
    missing = [name for name in spec.order if name not in available]
    assert not missing, (
        f"{len(missing)} of {len(spec.order)} model features are absent from "
        f"converter output and would be imputed: {missing}"
    )


def test_the_source_address_survives_renaming():
    assert "Source IP" in rename_columns(converter_frame()).columns


def test_the_heuristic_inputs_are_produced_too():
    available = set(rename_columns(converter_frame()).columns)
    for name in ("SYN Flag Count", "Total Fwd Packets", "Flow Packets/s",
                 "Average Packet Size", "Flow Duration", "Flow Bytes/s", "Fwd PSH Flags"):
        assert name in available, f"heuristics need {name}"


@pytest.mark.parametrize("layer", sorted(MODEL_DIRS))
def test_every_layer_ships_a_trained_model(layer):
    """A missing artifact silently downgrades that layer to the placeholder."""
    for name in ("models.joblib", "top_features.npy", "medians25.npy",
                 "scaler_mean25.npy", "scaler_std25.npy"):
        assert (MODEL_DIRS[layer] / name).is_file(), f"{layer} is missing {name}"
