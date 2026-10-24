"""The training notebook must agree with what the worker loads."""
import ast
import json
from pathlib import Path

import pytest

NOTEBOOK = Path("training/train_layer_model.ipynb")
COLLECTOR = Path("training/collect_testbed_flows.py")
ARTIFACTS = ("models.joblib", "top_features.npy", "medians25.npy",
             "scaler_mean25.npy", "scaler_std25.npy")


@pytest.fixture(scope="module")
def notebook():
    return json.loads(NOTEBOOK.read_text())


@pytest.fixture(scope="module")
def source(notebook):
    return "\n".join(
        "".join(cell["source"]) for cell in notebook["cells"] if cell["cell_type"] == "code"
    )


def test_the_notebook_is_valid(notebook):
    assert notebook["nbformat"] == 4
    assert [c for c in notebook["cells"] if c["cell_type"] == "code"]


def test_every_code_cell_parses(notebook):
    for i, cell in enumerate(notebook["cells"]):
        if cell["cell_type"] != "code":
            continue
        src = "".join(cell["source"])
        try:
            ast.parse(src)
        except SyntaxError as exc:
            pytest.fail(f"cell {i} does not parse: {exc}")


@pytest.mark.parametrize("name", ARTIFACTS)
def test_the_notebook_writes_every_artifact_the_worker_reads(name, source):
    assert name in source


def test_the_notebook_reuses_the_serving_code(source):
    """Reimplementing the transformation is how train and serve drift apart."""
    assert "from ddos_worker.features import" in source
    assert "build_matrix" in source
    assert "FeatureSpec" in source


def test_the_notebook_restricts_itself_to_servable_features(source):
    assert "COLUMN_MAPPING.values()" in source
    for leaky in ("Unnamed: 0", "Inbound", "Source Port", "Destination Port"):
        assert leaky in source, f"{leaky} must be named as excluded"


def test_the_notebook_checks_the_model_against_testbed_traffic(source):
    assert "TESTBED_CSV" in source
    assert "would_fire" in source


def test_the_notebook_mirrors_the_deployed_alert_rule(source):
    assert "ALERT_MIN_FLOWS" in source
    assert "ALERT_THRESHOLD" in source


def test_the_collector_parses_and_has_a_main():
    tree = ast.parse(COLLECTOR.read_text())
    names = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    assert {"main", "parse_args", "select"} <= names


def test_the_collector_labels_and_uses_the_worker_pipeline():
    text = COLLECTOR.read_text()
    assert "--label" in text
    assert "read_flows" in text and "pcap_to_csv" in text


@pytest.fixture(scope="module")
def collector_module():
    import importlib.util
    import sys

    sys.path.insert(0, "build/worker")
    spec = importlib.util.spec_from_file_location("collect_testbed_flows", COLLECTOR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Obj:
    def __init__(self, name, when):
        self.object_name = name
        self.last_modified = when


def _objects():
    from datetime import datetime, timedelta, timezone

    base = datetime(2026, 10, 24, 12, 0, tzinfo=timezone.utc)
    return [Obj(f"c{i}.pcap", base + timedelta(minutes=i)) for i in range(6)]


def test_last_n_takes_the_newest_captures(collector_module):
    args = collector_module.parse_args(["--label", "1", "--out", "/tmp/x.csv", "--last", "2"])
    chosen = collector_module.select(_objects(), args)
    assert [o.object_name for o in chosen] == ["c4.pcap", "c5.pcap"]


def test_a_time_range_wins_over_last(collector_module):
    args = collector_module.parse_args([
        "--label", "1", "--out", "/tmp/x.csv", "--last", "2",
        "--since", "2026-10-24T12:01:00Z", "--until", "2026-10-24T12:03:00Z",
    ])
    chosen = collector_module.select(_objects(), args)
    assert [o.object_name for o in chosen] == ["c1.pcap", "c2.pcap", "c3.pcap"]


def test_an_open_ended_range_is_allowed(collector_module):
    args = collector_module.parse_args([
        "--label", "0", "--out", "/tmp/x.csv", "--since", "2026-10-24T12:04:00Z",
    ])
    chosen = collector_module.select(_objects(), args)
    assert [o.object_name for o in chosen] == ["c4.pcap", "c5.pcap"]


def test_naive_timestamps_are_read_as_utc(collector_module):
    args = collector_module.parse_args([
        "--label", "0", "--out", "/tmp/x.csv", "--since", "2026-10-24 12:05:00",
    ])
    chosen = collector_module.select(_objects(), args)
    assert [o.object_name for o in chosen] == ["c5.pcap"]


def test_the_label_must_be_binary(collector_module):
    with pytest.raises(SystemExit):
        collector_module.parse_args(["--label", "7", "--out", "/tmp/x.csv"])
