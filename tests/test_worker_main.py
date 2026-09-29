from datetime import datetime, timedelta, timezone

import pytest

from ddos_worker.main import MessageError, is_stale, parse_message

NOW = datetime(2026, 9, 27, 15, 30, 30, tzinfo=timezone.utc)


def test_parses_a_well_formed_message():
    msg = parse_message(
        '{"bucket":"top-layer","object":"c.pcap","captured_at":"2026-09-27T15:30:00Z"}'
    )
    assert msg["bucket"] == "top-layer"
    assert msg["object"] == "c.pcap"


def test_accepts_bytes():
    assert parse_message(b'{"bucket":"b","object":"o"}')["object"] == "o"


def test_falls_back_to_filename_when_object_is_absent():
    """Messages from the pre-existing collectors carry only filename."""
    assert parse_message('{"filename":"c.pcap","download_url":"http://x"}')["object"] == "c.pcap"


def test_rejects_non_json():
    """Review Focus 2."""
    with pytest.raises(MessageError, match="JSON"):
        parse_message("not json at all")


def test_rejects_a_json_scalar():
    with pytest.raises(MessageError, match="object"):
        parse_message("42")


def test_rejects_a_message_with_no_object_or_filename():
    with pytest.raises(MessageError, match="object"):
        parse_message('{"bucket":"top-layer"}')


def test_fresh_capture_is_not_stale():
    assert is_stale("2026-09-27T15:30:00Z", NOW, 120) is False


def test_old_capture_is_stale():
    old = (NOW - timedelta(seconds=300)).isoformat().replace("+00:00", "Z")
    assert is_stale(old, NOW, 120) is True


def test_a_zero_budget_disables_the_staleness_check():
    old = (NOW - timedelta(days=5)).isoformat().replace("+00:00", "Z")
    assert is_stale(old, NOW, 0) is False


def test_missing_timestamp_is_never_stale():
    assert is_stale(None, NOW, 120) is False


def test_unparseable_timestamp_is_never_stale():
    assert is_stale("last tuesday", NOW, 120) is False


def test_window_end_is_the_start_plus_the_duration():
    from ddos_worker.main import window_end_for

    assert window_end_for("2026-09-28T15:30:00Z", 30) == "2026-09-28T15:30:30Z"


def test_window_end_without_a_timestamp_is_the_present():
    from ddos_worker.main import window_end_for

    assert window_end_for(None, 30).endswith("Z")


def test_window_end_tolerates_a_missing_duration():
    from ddos_worker.main import window_end_for

    assert window_end_for("2026-09-28T15:30:00Z", 0) == "2026-09-28T15:30:00Z"
