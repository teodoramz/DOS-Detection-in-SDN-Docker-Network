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


def test_the_notebook_scores_with_the_worker_s_own_probability_rule(source):
    """predict_proba / decision_function / predict is a three-way fallback;
    a second copy of it in the notebook can disagree with the deployed one."""
    assert "probabilities" in source
    assert "from ddos_worker.detectors.model import probabilities" in source
    assert "def probabilities(" not in source, "the notebook must not define its own"


def _config(source, name):
    import re
    m = re.search(rf"^{name}\s*=\s*(.+?)\s*(#.*)?$", source, re.M)
    assert m, f"{name} missing from the config"
    return ast.literal_eval(m.group(1))


def test_local_training_csvs_default_to_empty(source):
    assert _config(source, "LOCAL_TRAIN_CSVS") == []


def test_false_alerts_are_refused_by_default(source):
    assert _config(source, "ALLOW_FALSE_ALERTS") is False


def test_the_gate_counts_benign_sources_that_alert(source):
    assert "benign_sources_alerted" in source


def test_the_export_refuses_without_an_eligible_model(source):
    assert "select_export" in source
    assert "ALLOW_FALSE_ALERTS" in source


def test_local_rows_are_normalised_like_the_gate_and_reported(source):
    assert "LOCAL_TRAIN_CSVS" in source
    assert "local_rows" in source


def test_the_gate_set_cannot_leak_into_training(source):
    assert "assert_no_gate_overlap" in source
    assert "from gate_policy import" in source


@pytest.fixture(scope="module")
def policy():
    import importlib.util
    spec = importlib.util.spec_from_file_location("gate_policy", "training/gate_policy.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _flows(rows):
    import pandas as pd
    return pd.DataFrame(rows, columns=["src", "p", "y"])


def test_benign_sources_alerted_counts_only_benign_sources(policy):
    rows = ([("b1", 0.99, 0)] * 10 + [("b2", 0.99, 0)] * 9 + [("b3", 0.1, 0)] * 20
            + [("a1", 0.99, 1)] * 30)
    f = _flows(rows)
    n = policy.benign_sources_alerted(f.src, f.p, f.y, threshold=0.5, min_flows=10)
    assert n == 1


def test_select_export_skips_models_that_block_benign_sources(policy):
    import pandas as pd
    gate = pd.DataFrame([
        dict(model="A", alert_f1=1.0, attack_pmax=1.0, would_fire=True, benign_sources_alerted=2),
        dict(model="B", alert_f1=0.8, attack_pmax=0.9, would_fire=True, benign_sources_alerted=0),
        dict(model="C", alert_f1=0.0, attack_pmax=0.1, would_fire=False, benign_sources_alerted=0),
    ]).sort_values(["alert_f1", "attack_pmax"], ascending=False)
    assert policy.select_export(gate, allow_false_alerts=False) == ("B", False)


def test_select_export_raises_when_none_is_eligible(policy):
    import pandas as pd
    gate = pd.DataFrame([
        dict(model="A", alert_f1=1.0, attack_pmax=1.0, would_fire=True, benign_sources_alerted=3),
    ])
    with pytest.raises(RuntimeError, match="benign"):
        policy.select_export(gate, allow_false_alerts=False)
    assert policy.select_export(gate, allow_false_alerts=True) == ("A", True)


def test_select_export_raises_when_nothing_fires_even_if_allowed(policy):
    import pandas as pd
    gate = pd.DataFrame([
        dict(model="C", alert_f1=0.0, attack_pmax=0.1, would_fire=False, benign_sources_alerted=0),
    ])
    with pytest.raises(RuntimeError):
        policy.select_export(gate, allow_false_alerts=True)


def test_leak_guard_rejects_shared_rows_and_accepts_disjoint(policy):
    import pandas as pd
    gate = pd.DataFrame({"a": [1.0, 2.0], "b": [3.0, 4.0], "y": [0, 1]})
    same_row = pd.DataFrame({"a": [2.0, 9.0], "b": [4.0, 9.0], "y": [1, 0]})
    other = pd.DataFrame({"a": [7.0], "b": [8.0], "y": [0]})
    with pytest.raises(RuntimeError, match="gate"):
        policy.assert_no_gate_overlap(same_row, gate, ["a", "b"], name="x.csv")
    policy.assert_no_gate_overlap(other, gate, ["a", "b"], name="y.csv")
    flipped = pd.DataFrame({"a": [2.0], "b": [4.0], "y": [0]})
    policy.assert_no_gate_overlap(flipped, gate, ["a", "b"], name="z.csv")


GENERATOR = Path("training/generate_benign_dns.sh")


def test_the_generator_is_a_runnable_script():
    import os, stat, subprocess
    assert GENERATOR.is_file()
    assert subprocess.run(["bash", "-n", str(GENERATOR)]).returncode == 0
    assert os.stat(GENERATOR).st_mode & stat.S_IXUSR


def test_the_generator_is_configured_by_rate_and_duration_and_never_floods():
    text = GENERATOR.read_text()
    for knob in ("PER_WINDOW", "RATES", "DURATION", "ZONE", "TARGET"):
        assert knob in text
    assert "cyberstuff.local" in text and "10.0.1.2" in text
    assert "--flood" not in text
    assert "dig" in text


def test_the_notebook_documents_collecting_a_benign_set(notebook):
    md = "\n".join("".join(c["source"]) for c in notebook["cells"] if c["cell_type"] == "markdown")
    assert "generate_benign_dns.sh" in md and "--label 0" in md
