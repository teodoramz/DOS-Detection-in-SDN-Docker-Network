"""The committed testbed flows are what stops an unservable model shipping.

They were captured on the running testbed: benign windows while only
legitimate traffic flowed, attack windows during each layer's own scenario.
"""
import sys
from pathlib import Path

import pytest

pd = pytest.importorskip("pandas")

sys.path.insert(0, str(Path("build/worker")))
from ddos_worker.features import (  # noqa: E402
    FeatureSpec, ensure_duplicate_header_column, rename_columns,
)

LAYERS = ("top", "inter", "bottom")


def dataset(layer):
    path = Path(f"training/data/testbed_{layer}.csv.gz")
    assert path.is_file(), f"{path} is missing"
    return pd.read_csv(path, low_memory=False)


@pytest.mark.parametrize("layer", LAYERS)
def test_every_layer_has_a_gate_set(layer):
    assert Path(f"training/data/testbed_{layer}.csv.gz").is_file()


@pytest.mark.parametrize("layer", LAYERS)
def test_both_classes_are_present(layer):
    data = dataset(layer)
    assert set(data.y.unique()) == {0, 1}, "a gate needs both classes"
    assert (data.y == 1).sum() >= 100
    assert (data.y == 0).sum() >= 40


@pytest.mark.parametrize("layer", LAYERS)
def test_the_source_address_survived(layer):
    """The alert rule groups by source, so the gate cannot simulate it without."""
    assert "Source IP" in dataset(layer).columns


@pytest.mark.parametrize("layer", LAYERS)
def test_every_model_feature_resolves_from_the_gate_set(layer):
    spec = FeatureSpec.load(f"build/worker/models/{layer}")
    columns = set(ensure_duplicate_header_column(rename_columns(dataset(layer))).columns)
    missing = [name for name in spec.order if name not in columns]
    assert not missing, f"{layer}: {missing}"


@pytest.mark.parametrize("layer", LAYERS)
def test_the_columns_are_already_dataset_named(layer):
    """collect_testbed_flows.py writes through read_flows, so the converter's
    own names are gone by the time the file is written."""
    columns = dataset(layer).columns
    assert "Source IP" in columns and "Src IP" not in columns
