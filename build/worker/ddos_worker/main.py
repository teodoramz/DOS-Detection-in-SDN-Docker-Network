"""The worker loop: consume a capture reference, score it, alert on it.

One process per layer, selected by WORKER_LAYER.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .alerts import aggregate
from .config import WorkerConfig
from .detectors import build_detector
from .flowmeter import FlowMeterError, pcap_to_csv, read_flows

log = logging.getLogger("ddos_worker")


class MessageError(ValueError):
    """The Kafka message cannot be acted on."""


def parse_message(raw) -> dict:
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8", errors="replace")
    if isinstance(raw, str):
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise MessageError(f"not JSON: {raw[:120]!r}") from exc
    else:
        payload = raw

    if not isinstance(payload, dict):
        raise MessageError(f"expected a JSON object, got {type(payload).__name__}")

    obj = payload.get("object") or payload.get("filename")
    if not obj:
        raise MessageError(f"no object or filename in {payload!r}")

    return {**payload, "object": obj}


def _parse_timestamp(value):
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def is_stale(captured_at, now: datetime, max_lag_seconds: int) -> bool:
    """True when this window is too old to be worth processing."""
    if max_lag_seconds <= 0 or not captured_at:
        return False
    stamp = _parse_timestamp(captured_at)
    if stamp is None:
        return False
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return (now - stamp) > timedelta(seconds=max_lag_seconds)


def process_capture(pcap: Path, cfg: WorkerConfig, detector, window_start: str, window_end: str):
    """pcap to alerts. Returns an empty list when nothing is worth reporting."""
    started = time.monotonic()
    csv_path = pcap_to_csv(
        pcap, pcap.parent / "csv", cfm_home=cfg.cfm_home, timeout=cfg.flowmeter_timeout
    )
    measured = time.monotonic()

    df = read_flows(csv_path)
    if len(df) == 0:
        log.info("%s produced no flows, nothing to score", pcap.name)
        return []

    probs = detector.score(df)
    scored = time.monotonic()

    alerts = aggregate(
        df, probs,
        layer=cfg.layer, detector=detector.name,
        threshold=cfg.threshold, min_flows=cfg.min_flows,
        window_start=window_start, window_end=window_end,
    )

    log.info(
        "%s: %d flows, %d alerts (flowmeter %.1fs, score %.1fs, total %.1fs)",
        pcap.name, len(df), len(alerts),
        measured - started, scored - measured, time.monotonic() - started,
    )
    return alerts


def main() -> int:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="[%(asctime)s] %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    cfg = WorkerConfig.from_env(os.environ)
    log.info("layer=%s topic=%s bucket=%s", cfg.layer, cfg.capture_topic, cfg.minio_bucket)

    detector = build_detector(cfg.layer, cfg.model_dir, cfg.detector_mode)
    log.info("detector=%s", detector.name)

    from kafka import KafkaConsumer, KafkaProducer
    from minio import Minio

    store = Minio(
        cfg.minio_endpoint,
        access_key=cfg.minio_access_key,
        secret_key=cfg.minio_secret_key,
        secure=False,
    )
    producer = KafkaProducer(
        bootstrap_servers=[cfg.kafka_broker],
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )
    consumer = KafkaConsumer(
        cfg.capture_topic,
        bootstrap_servers=[cfg.kafka_broker],
        group_id=f"ddos-worker-{cfg.layer}",
        auto_offset_reset="latest",
        enable_auto_commit=True,
    )
    log.info("consuming %s from %s", cfg.capture_topic, cfg.kafka_broker)

    cfg.work_dir.mkdir(parents=True, exist_ok=True)

    for record in consumer:
        try:
            message = parse_message(record.value)
        except MessageError as exc:
            log.warning("skipping malformed message: %s", exc)
            continue

        captured_at = message.get("captured_at")
        if is_stale(captured_at, datetime.now(timezone.utc), cfg.max_lag_seconds):
            log.warning("skipping %s, older than %ds", message["object"], cfg.max_lag_seconds)
            continue

        window = cfg.work_dir / message["object"].replace("/", "_")
        window.mkdir(parents=True, exist_ok=True)
        pcap = window / Path(message["object"]).name
        bucket = message.get("bucket") or cfg.minio_bucket

        try:
            store.fget_object(bucket, message["object"], str(pcap))
        except Exception as exc:
            log.warning("cannot fetch %s/%s: %s", bucket, message["object"], exc)
            shutil.rmtree(window, ignore_errors=True)
            continue

        try:
            window_end = captured_at or datetime.now(timezone.utc).isoformat()
            alerts = process_capture(pcap, cfg, detector, captured_at or window_end, window_end)
            for alert in alerts:
                producer.send(cfg.alert_topic, alert.to_dict())
                log.warning(
                    "ALERT %s %s p=%.3f %d/%d flows",
                    alert.layer, alert.source_ip, alert.max_probability,
                    alert.flows_malicious, alert.flows_total,
                )
            producer.flush()
        except FlowMeterError as exc:
            log.error("flow extraction failed for %s: %s", pcap.name, exc)
        except Exception:
            log.exception("unhandled error processing %s", pcap.name)
        finally:
            shutil.rmtree(window, ignore_errors=True)

    return 0


if __name__ == "__main__":
    sys.exit(main())
