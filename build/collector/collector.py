#!/usr/bin/env python3
"""Capture one layer's mirrored traffic in rolling windows.

Each window is written by tcpdump, uploaded to MinIO, and announced on Kafka
as a reference to the stored object.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Mapping

LAYERS = ("top", "inter", "bottom")
LAYER_TOPICS = {"top": "top-layer", "inter": "inter-layer", "bottom": "bot-layer"}

log = logging.getLogger("collector")


def connect_with_retry(factory, *, what: str, attempts: int = 0, delay: int = 5,
                       sleeper=time.sleep):
    """Call ``factory`` until it succeeds.

    A collector starts before the topology scripts attach its interface and
    before the host2 services are reachable. ``attempts=0`` retries forever.
    """
    tries = 0
    while True:
        try:
            return factory()
        except Exception as exc:
            tries += 1
            if attempts and tries >= attempts:
                raise
            log.warning("%s not reachable yet (%s), retrying in %ss", what, exc, delay)
            sleeper(delay)


@dataclass(frozen=True)
class CollectorConfig:
    layer: str
    interface: str
    duration: int
    tmp_dir: Path
    minio_endpoint: str
    minio_access_key: str
    minio_secret_key: str
    minio_bucket: str
    minio_secure: bool
    kafka_broker: str
    kafka_topic: str

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "CollectorConfig":
        layer = env.get("LAYER", "").strip()
        if layer not in LAYERS:
            raise ValueError(f"LAYER must be one of {LAYERS}, got {layer!r}")

        raw = env.get("CAPTURE_DURATION") or "30"
        try:
            duration = int(raw)
        except ValueError as exc:
            raise ValueError(f"CAPTURE_DURATION must be an integer, got {raw!r}") from exc
        if duration < 1:
            raise ValueError(f"CAPTURE_DURATION must be at least 1, got {duration}")

        return cls(
            layer=layer,
            interface=env.get("CAPTURE_INTERFACE", "eth0"),
            duration=duration,
            tmp_dir=Path(env.get("TMP_DIR", "/tmp")),
            minio_endpoint=env.get("MINIO_ENDPOINT", "10.0.5.9:9000"),
            minio_access_key=env.get("MINIO_ACCESS_KEY", "minioadmin"),
            minio_secret_key=env.get("MINIO_SECRET_KEY", "minioadmin"),
            minio_bucket=env.get("MINIO_BUCKET") or LAYER_TOPICS[layer],
            minio_secure=env.get("MINIO_SECURE", "false").lower() == "true",
            kafka_broker=env.get("KAFKA_BROKER", "10.0.5.2:9092"),
            kafka_topic=env.get("KAFKA_TOPIC") or LAYER_TOPICS[layer],
        )


def build_message(*, filename, bucket, layer, captured_at, duration, interface,
                  download_url) -> dict:
    return {
        "filename": filename,
        "download_url": download_url,
        "object": filename,
        "bucket": bucket,
        "layer": layer,
        "captured_at": captured_at,
        "duration_s": duration,
        "interface": interface,
    }


def publish_window(cfg: "CollectorConfig", *, pcap: Path, filename: str,
                   started_iso: str, publish) -> bool:
    """Upload and announce one window. False when it failed.

    A failure here is logged and swallowed: exiting would restart the container,
    which recreates its network namespace and destroys the interface the
    topology scripts attached.
    """
    try:
        publish(cfg, pcap=pcap, filename=filename, started_iso=started_iso)
        return True
    except Exception as exc:
        log.error("window %s not published (%s); continuing", filename, exc)
        return False
    finally:
        Path(pcap).unlink(missing_ok=True)


def backoff_after_failed_capture(cfg: "CollectorConfig", sleeper=time.sleep) -> None:
    """Pause before retrying a capture that produced nothing.

    tcpdump exits immediately when the interface is missing, so looping without
    a pause is a fork storm and a log flood.
    """
    sleeper(min(cfg.duration, 5))


def capture(cfg: CollectorConfig, filepath: Path) -> None:
    proc = subprocess.Popen(
        ["tcpdump", "-i", cfg.interface, "-s", "0", "-w", str(filepath)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        proc.wait(timeout=cfg.duration)
    except subprocess.TimeoutExpired:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


def main() -> int:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="[%(asctime)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S",
    )
    cfg = CollectorConfig.from_env(os.environ)
    log.info("layer=%s iface=%s window=%ds bucket=%s topic=%s",
             cfg.layer, cfg.interface, cfg.duration, cfg.minio_bucket, cfg.kafka_topic)

    from kafka import KafkaProducer
    from minio import Minio

    store = Minio(cfg.minio_endpoint, access_key=cfg.minio_access_key,
                  secret_key=cfg.minio_secret_key, secure=cfg.minio_secure)

    def ensure_bucket():
        if not store.bucket_exists(cfg.minio_bucket):
            store.make_bucket(cfg.minio_bucket)
            log.info("created bucket %s", cfg.minio_bucket)
        return store

    connect_with_retry(ensure_bucket, what=f"minio at {cfg.minio_endpoint}")

    producer = connect_with_retry(
        lambda: KafkaProducer(
            bootstrap_servers=[cfg.kafka_broker],
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        ),
        what=f"kafka at {cfg.kafka_broker}",
    )

    while True:
        started = datetime.now(timezone.utc)
        filename = f"capture-{started.strftime('%Y%m%d%H%M%S')}.pcap"
        filepath = cfg.tmp_dir / filename

        log.info("capturing %s for %ds", filename, cfg.duration)
        capture(cfg, filepath)

        if not filepath.exists() or filepath.stat().st_size == 0:
            log.warning("%s is empty; is %s present?", filename, cfg.interface)
            filepath.unlink(missing_ok=True)
            backoff_after_failed_capture(cfg)
            continue

        def publish(cfg, *, pcap, filename, started_iso):
            store.fput_object(cfg.minio_bucket, filename, str(pcap))
            url = store.presigned_get_object(
                cfg.minio_bucket, filename, expires=timedelta(days=7)
            )
            producer.send(cfg.kafka_topic, build_message(
                filename=filename, bucket=cfg.minio_bucket, layer=cfg.layer,
                captured_at=started_iso, duration=cfg.duration,
                interface=cfg.interface, download_url=url,
            ))
            producer.flush()
            log.info("published %s to %s", filename, cfg.kafka_topic)

        publish_window(
            cfg, pcap=filepath, filename=filename,
            started_iso=started.isoformat().replace("+00:00", "Z"),
            publish=publish,
        )


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(0)
