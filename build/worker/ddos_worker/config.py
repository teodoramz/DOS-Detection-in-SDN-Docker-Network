"""Worker configuration, entirely from the environment."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

LAYERS = ("top", "inter", "bottom")

LAYER_TOPICS = {"top": "top-layer", "inter": "inter-layer", "bottom": "bot-layer"}
LAYER_BUCKETS = dict(LAYER_TOPICS)


def _float(env: Mapping[str, str], key: str, default: float, low: float, high: float) -> float:
    raw = env.get(key)
    if raw is None or raw == "":
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{key} must be a number, got {raw!r}") from exc
    if not low <= value <= high:
        raise ValueError(f"{key} must be between {low} and {high}, got {value}")
    return value


def _int(env: Mapping[str, str], key: str, default: int, low: int) -> int:
    raw = env.get(key)
    if raw is None or raw == "":
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{key} must be an integer, got {raw!r}") from exc
    if value < low:
        raise ValueError(f"{key} must be at least {low}, got {value}")
    return value


@dataclass(frozen=True)
class WorkerConfig:
    layer: str
    kafka_broker: str
    capture_topic: str
    alert_topic: str
    minio_endpoint: str
    minio_access_key: str
    minio_secret_key: str
    minio_bucket: str
    model_dir: Path
    detector_mode: str
    threshold: float
    min_flows: int
    max_lag_seconds: int
    cfm_home: Path
    flowmeter_timeout: int
    java_opts: str
    work_dir: Path

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "WorkerConfig":
        layer = env.get("WORKER_LAYER", "").strip()
        if layer not in LAYERS:
            raise ValueError(f"WORKER_LAYER must be one of {LAYERS}, got {layer!r}")

        models_root = Path(env.get("MODELS_ROOT", "/app/models"))
        return cls(
            layer=layer,
            kafka_broker=env.get("KAFKA_BROKER", "10.0.5.2:9092"),
            capture_topic=env.get("KAFKA_CAPTURE_TOPIC") or LAYER_TOPICS[layer],
            alert_topic=env.get("KAFKA_ALERT_TOPIC", "ddos-alerts"),
            minio_endpoint=env.get("MINIO_ENDPOINT", "10.0.5.9:9000"),
            minio_access_key=env.get("MINIO_ACCESS_KEY", "minioadmin"),
            minio_secret_key=env.get("MINIO_SECRET_KEY", "minioadmin"),
            minio_bucket=env.get("MINIO_BUCKET") or LAYER_BUCKETS[layer],
            model_dir=Path(env.get("MODEL_DIR") or models_root / layer),
            detector_mode=env.get("DETECTOR", "auto"),
            threshold=_float(env, "ALERT_THRESHOLD", 0.5, 0.0, 1.0),
            min_flows=_int(env, "ALERT_MIN_FLOWS", 10, 1),
            max_lag_seconds=_int(env, "MAX_LAG_SECONDS", 120, 0),
            cfm_home=Path(env.get("CFM_HOME", "/opt/cicflowmeter")),
            flowmeter_timeout=_int(env, "FLOWMETER_TIMEOUT", 300, 1),
            java_opts=env.get("JAVA_OPTS", ""),
            work_dir=Path(env.get("WORK_DIR", "/tmp/ddos-worker")),
        )
