"""Decide what to block, remember what is blocked, and build the flow rule.

Free of ryu imports: the datapath's parser and protocol constants come from the
object passed in.
"""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

#: The drop rule must outrank the learning switch's own entries.
TABLE_MISS_PRIORITY = 0
LEARNED_PRIORITY = 1

ETH_TYPE_IPV4 = 0x0800


@dataclass(frozen=True)
class BlockDecision:
    dpid: int
    source_ip: str
    layer: str


def decide(alert, cfg) -> BlockDecision | None:
    """Return what to block, or None when the alert must not be acted on."""
    if not isinstance(alert, dict):
        return None

    layer = alert.get("layer")
    source_ip = alert.get("source_ip")
    if not layer or not source_ip:
        return None

    dpid = cfg.datapath_for(layer)
    if dpid is None:
        return None

    try:
        address = ipaddress.ip_address(str(source_ip).strip())
    except ValueError:
        return None
    if address.version != 4 or cfg.is_whitelisted(str(address)):
        return None

    return BlockDecision(dpid=dpid, source_ip=str(address), layer=layer)


class BlockTable:
    """Which sources are currently dropped, per datapath."""

    def __init__(self) -> None:
        self._entries: dict[tuple[int, str], dict] = {}

    def __len__(self) -> int:
        return len(self._entries)

    def record(self, dpid: int, ip: str, timeout: int, now: datetime | None = None) -> bool:
        """Insert or refresh. True the first time, False on every refresh."""
        now = now or datetime.now(timezone.utc)
        key = (dpid, ip)
        is_new = key not in self._entries
        entry = self._entries.setdefault(
            key, {"dpid": dpid, "source_ip": ip, "hits": 0, "first_seen": now}
        )
        entry["hits"] += 1
        entry["last_seen"] = now
        entry["expires_at"] = None if timeout <= 0 else now + timedelta(seconds=timeout)
        return is_new

    def active(self, now: datetime | None = None) -> list[dict]:
        now = now or datetime.now(timezone.utc)
        out = []
        for key, entry in list(self._entries.items()):
            expires = entry["expires_at"]
            if expires is not None and expires <= now:
                del self._entries[key]
                continue
            out.append({
                **entry,
                "first_seen": entry["first_seen"].isoformat(),
                "last_seen": entry["last_seen"].isoformat(),
                "expires_at": expires,
                "remaining_s": None if expires is None else int((expires - now).total_seconds()),
            })
        return out

    def forget(self, dpid: int, ip: str) -> bool:
        return self._entries.pop((dpid, ip), None) is not None


def build_block_flow(datapath, decision: BlockDecision, cfg):
    """An OFPFlowMod that drops everything from this source.

    No actions means no output, which is how OpenFlow expresses a drop.
    """
    parser = datapath.ofproto_parser
    ofproto = datapath.ofproto

    match = parser.OFPMatch(eth_type=ETH_TYPE_IPV4, ipv4_src=decision.source_ip)
    instructions = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, [])]

    return parser.OFPFlowMod(
        datapath=datapath,
        priority=cfg.block_priority,
        match=match,
        instructions=instructions,
        hard_timeout=cfg.block_timeout,
        command=ofproto.OFPFC_ADD,
    )
