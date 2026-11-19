"""Selection and leakage logic shared by the training notebook and its tests."""
from __future__ import annotations

import numpy as np
import pandas as pd


def benign_sources_alerted(sources, probs, truth, threshold, min_flows):
    """Sources with no attack flow at all on which the deployed rule would fire."""
    frame = pd.DataFrame({
        "src": np.asarray(sources), "p": np.asarray(probs, dtype=float),
        "y": np.asarray(truth),
    })
    per_source = frame.groupby("src").agg(
        hits=("p", lambda s: int((s >= threshold).sum())),
        attack=("y", "max"),
    )
    benign = per_source[per_source.attack == 0]
    return int((benign.hits >= min_flows).sum())


def select_export(gate, allow_false_alerts=False):
    """Return (model, has_false_alerts) from a gate table already in preference order.

    Eligible means the rule fires on the attacker and on no benign source.
    """
    firing = gate[gate.would_fire]
    eligible = firing[firing.benign_sources_alerted == 0]
    if len(eligible):
        return str(eligible.iloc[0].model), False
    if not len(firing):
        raise RuntimeError(
            "no model would raise an alert on the testbed attack traffic; "
            "fix the features or add testbed flows to the training data")
    if allow_false_alerts:
        print("!! WARNING: exporting a model that alerts on benign sources; "
              "it will block legitimate clients")
        return str(firing.iloc[0].model), True
    worst = firing[["model", "benign_sources_alerted"]].to_string(index=False)
    raise RuntimeError(
        "every model that fires on the attack also alerts on benign sources "
        "(false blocks):\n" + worst +
        "\nAdd benign testbed flows via LOCAL_TRAIN_CSVS and retrain, or set "
        "ALLOW_FALSE_ALERTS = True to export anyway.")


def row_fingerprints(frame, columns):
    """One hash per row over the feature columns and the label."""
    cols = [c for c in columns if c in frame.columns] + ["y"]
    return set(pd.util.hash_pandas_object(
        frame[cols].astype(float).round(9), index=False).tolist())


def assert_no_gate_overlap(local, gate, columns, name="local file"):
    """Stop when a training file is, or shares rows with, the held-out gate set."""
    shared = columns and (row_fingerprints(local, columns) & row_fingerprints(gate, columns))
    if shared:
        raise RuntimeError(
            f"{name} shares {len(shared)} rows with the gate set; the gate must "
            "stay held out. Collect a separate set for training.")
