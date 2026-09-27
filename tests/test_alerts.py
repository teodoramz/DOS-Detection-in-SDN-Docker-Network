import json

import numpy as np
import pandas as pd
import pytest

from ddos_worker.alerts import aggregate

WINDOW = ("2026-09-27T15:30:00Z", "2026-09-27T15:30:30Z")


def run(df, probs, threshold=0.5, min_flows=10):
    return aggregate(
        df,
        np.asarray(probs, dtype=float),
        layer="top",
        detector="xgboost-top-v1",
        threshold=threshold,
        min_flows=min_flows,
        window_start=WINDOW[0],
        window_end=WINDOW[1],
    )


def frame(ips):
    return pd.DataFrame({"Source IP": ips})


def test_no_alert_below_the_minimum_flow_count():
    assert run(frame(["10.0.1.9"] * 9), [0.99] * 9) == []


def test_alert_at_exactly_the_minimum_flow_count():
    alerts = run(frame(["10.0.1.9"] * 10), [0.99] * 10)
    assert len(alerts) == 1
    assert alerts[0].source_ip == "10.0.1.9"
    assert alerts[0].flows_malicious == 10


def test_probability_exactly_at_the_threshold_counts_as_malicious():
    assert len(run(frame(["10.0.1.9"] * 10), [0.5] * 10)) == 1


def test_probability_just_below_the_threshold_does_not_count():
    assert run(frame(["10.0.1.9"] * 10), [0.4999] * 10) == []


def test_counts_are_per_source_not_global():
    df = frame(["10.0.1.9"] * 6 + ["10.0.1.8"] * 6)
    assert run(df, [0.99] * 12) == []


def test_only_the_offending_source_is_reported():
    df = frame(["10.0.1.9"] * 10 + ["10.0.1.8"] * 10)
    alerts = run(df, [0.99] * 10 + [0.01] * 10)
    assert [a.source_ip for a in alerts] == ["10.0.1.9"]


def test_totals_count_all_flows_from_the_source():
    alerts = run(frame(["10.0.1.9"] * 15), [0.99] * 10 + [0.01] * 5)
    assert alerts[0].flows_total == 15
    assert alerts[0].flows_malicious == 10


def test_max_probability_is_the_source_maximum():
    alerts = run(frame(["10.0.1.9"] * 10), [0.6] * 9 + [0.97])
    assert alerts[0].max_probability == 0.97


def test_empty_flow_table_produces_no_alert():
    """Review Focus 1: an idle capture yields a header-only CSV."""
    assert run(frame([]), []) == []


def test_missing_source_ip_column_produces_no_alert():
    assert run(pd.DataFrame({"Protocol": [6] * 10}), [0.99] * 10) == []


def test_rows_without_a_source_ip_are_ignored():
    assert run(frame([None] * 10), [0.99] * 10) == []


def test_alerts_are_ordered_by_severity():
    df = frame(["10.0.1.8"] * 10 + ["10.0.1.9"] * 10)
    alerts = run(df, [0.6] * 10 + [0.99] * 10)
    assert [a.source_ip for a in alerts] == ["10.0.1.9", "10.0.1.8"]


def test_to_dict_is_the_documented_wire_format():
    alert = run(frame(["10.0.1.9"] * 10), [0.99] * 10)[0]
    assert alert.to_dict() == {
        "layer": "top",
        "source_ip": "10.0.1.9",
        "flows_total": 10,
        "flows_malicious": 10,
        "max_probability": 0.99,
        "threshold": 0.5,
        "detector": "xgboost-top-v1",
        "window_start": WINDOW[0],
        "window_end": WINDOW[1],
    }


def test_wire_format_values_are_plain_json_types():
    alert = run(frame(["10.0.1.9"] * 10), [0.99] * 10)[0]
    assert json.loads(json.dumps(alert.to_dict())) == alert.to_dict()


def test_mismatched_probability_length_is_rejected():
    with pytest.raises(ValueError, match="rows"):
        run(frame(["10.0.1.9"] * 3), [0.9, 0.9])
