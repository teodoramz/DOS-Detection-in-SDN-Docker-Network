"""Configuration for the DDoS blocker."""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass, field
from typing import Mapping

#: Addresses that must never be dropped: the management range, the layer
#: gateways, the collectors, and the host2 services.
DEFAULT_WHITELIST = (
    "10.255.255.0/24,"
    "10.0.1.1,10.0.2.1,10.0.3.1,10.0.4.1,10.0.5.1,"
    "10.0.1.6,10.0.2.6,10.0.3.6,"
    "10.0.4.2,10.0.4.3,10.0.4.4,"
    "10.0.5.2,10.0.5.6,10.0.5.9,"
    "10.0.5.11,10.0.5.12,10.0.5.13"
)

DEFAULT_LAYER_MAP = "top:1,inter:2,bottom:3"


def parse_whitelist(raw: str) -> list:
    nets = []
    for entry in (e.strip() for e in raw.split(",")):
        if not entry:
            continue
        try:
            nets.append(ipaddress.ip_network(entry, strict=False))
        except ValueError as exc:
            raise ValueError(
                f"BLOCK_WHITELIST entry {entry!r} is not an address or CIDR"
            ) from exc
    return nets


def parse_layer_map(raw: str) -> dict[str, int]:
    mapping = {}
    for entry in (e.strip() for e in raw.split(",")):
        if not entry:
            continue
        if ":" not in entry:
            raise ValueError(f"LAYER_DATAPATH_MAP entry {entry!r} must be layer:dpid")
        layer, _, dpid = entry.partition(":")
        try:
            mapping[layer.strip()] = int(dpid, 0)
        except ValueError as exc:
            raise ValueError(
                f"LAYER_DATAPATH_MAP entry {entry!r} has a non-numeric dpid"
            ) from exc
    return mapping


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
class BlockerConfig:
    kafka_broker: str = "10.0.5.2:9092"
    alert_topic: str = "ddos-alerts"
    block_timeout: int = 300
    block_priority: int = 100
    ofp_port: int = 6633
    rest_port: int = 8080
    whitelist: list = field(default_factory=list)
    layer_dpid: dict = field(default_factory=dict)

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "BlockerConfig":
        return cls(
            kafka_broker=env.get("KAFKA_BROKER", "10.0.5.2:9092"),
            alert_topic=env.get("KAFKA_ALERT_TOPIC", "ddos-alerts"),
            block_timeout=_int(env, "BLOCK_HARD_TIMEOUT", 300, 0),
            block_priority=_int(env, "BLOCK_PRIORITY", 100, 1),
            ofp_port=_int(env, "OFP_LISTEN_PORT", 6633, 1),
            rest_port=_int(env, "REST_PORT", 8080, 1),
            whitelist=parse_whitelist(env.get("BLOCK_WHITELIST") or DEFAULT_WHITELIST),
            layer_dpid=parse_layer_map(env.get("LAYER_DATAPATH_MAP") or DEFAULT_LAYER_MAP),
        )

    def is_whitelisted(self, ip: str) -> bool:
        """True when this address must not be blocked.

        Anything that is not a parseable IPv4 address counts as whitelisted:
        refusing to act beats building a malformed match.
        """
        try:
            address = ipaddress.ip_address(str(ip).strip())
        except ValueError:
            return True
        if address.version != 4:
            return True
        return any(address in net for net in self.whitelist)

    def datapath_for(self, layer: str):
        return self.layer_dpid.get(layer)
