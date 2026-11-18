"""Decide what to block, remember what is blocked, and build the flow rule.

Free of ryu imports: the datapath's parser and protocol constants come from the
object passed in.
"""

from __future__ import annotations

import ipaddress
import json
import logging
import math
import os
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

log = logging.getLogger(__name__)

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

    def __init__(self, on_change: Callable[[], None] | None = None) -> None:
        self._entries: dict[tuple[int, str], dict] = {}
        self._on_change = on_change

    def _changed(self) -> None:
        if self._on_change is not None:
            self._on_change()

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
        self._changed()
        return is_new

    def restore(self, records: Iterable[dict]) -> None:
        """Load records from parse_blocks. Does not notify: nothing changed."""
        for rec in records:
            installed = datetime.fromtimestamp(rec["installed_at"], timezone.utc)
            expires = rec["expires_at"]
            self._entries[(rec["dpid"], rec["source_ip"])] = {
                "dpid": rec["dpid"], "source_ip": rec["source_ip"], "hits": 1,
                "first_seen": installed, "last_seen": installed,
                "expires_at": None if expires is None
                else datetime.fromtimestamp(expires, timezone.utc),
            }

    def records(self) -> list[dict]:
        """What persistence needs to reinstall each block."""
        return [
            {
                "dpid": e["dpid"],
                "source_ip": e["source_ip"],
                "installed_at": e["first_seen"].timestamp(),
                "expires_at": None if e["expires_at"] is None else e["expires_at"].timestamp(),
            }
            for e in self._entries.values()
        ]

    def active(self, now: datetime | None = None) -> list[dict]:
        now = now or datetime.now(timezone.utc)
        out = []
        expired = False
        for key, entry in list(self._entries.items()):
            expires = entry["expires_at"]
            if expires is not None and expires <= now:
                del self._entries[key]
                expired = True
                continue
            out.append({
                **entry,
                "first_seen": entry["first_seen"].isoformat(),
                "last_seen": entry["last_seen"].isoformat(),
                "expires_at": expires,
                "remaining_s": None if expires is None else int((expires - now).total_seconds()),
            })
        if expired:
            self._changed()
        return out

    def forget(self, dpid: int, ip: str) -> bool:
        removed = self._entries.pop((dpid, ip), None) is not None
        if removed:
            self._changed()
        return removed


def remaining_timeout(expires_at: datetime | None, now: datetime) -> int | None:
    """Hard timeout for a reinstalled rule: 0 for permanent, None once expired."""
    if expires_at is None:
        return 0
    left = (expires_at - now).total_seconds()
    if left <= 0:
        return None
    return max(1, math.ceil(left))


def serialise_blocks(records: Iterable[dict]) -> str:
    return json.dumps(list(records), indent=2)


def _valid_record(rec) -> bool:
    if not isinstance(rec, dict):
        return False
    try:
        ipaddress.IPv4Address(rec["source_ip"])
    except (KeyError, ValueError):
        return False
    expires = rec.get("expires_at")
    return (
        isinstance(rec.get("dpid"), int) and not isinstance(rec["dpid"], bool)
        and isinstance(rec.get("installed_at"), (int, float))
        and (expires is None or isinstance(expires, (int, float)))
    )


def parse_blocks(text: str, now: datetime) -> list[dict]:
    """Records from a saved table, minus malformed and expired ones.

    Raises ValueError when the text is not a JSON list at all.
    """
    data = json.loads(text)
    if not isinstance(data, list):
        raise ValueError("block state must be a JSON list")
    cutoff = now.timestamp()
    return [
        rec for rec in data
        if _valid_record(rec) and (rec["expires_at"] is None or rec["expires_at"] > cutoff)
    ]


def load_blocks(path, now: datetime) -> list[dict]:
    """Saved blocks still in force. A missing or unreadable file means none."""
    path = Path(path)
    try:
        return parse_blocks(path.read_text(), now)
    except FileNotFoundError:
        return []
    except (OSError, ValueError) as exc:
        log.warning("ignoring block state %s: %s", path, exc)
        return []


def save_blocks(path, records: Iterable[dict]) -> None:
    """Write atomically so a crash never leaves a half-written file."""
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(serialise_blocks(records))
        os.replace(tmp, path)
    except OSError as exc:
        log.warning("could not save block state %s: %s", path, exc)


def build_block_flow(datapath, decision: BlockDecision, cfg, hard_timeout: int | None = None):
    """An OFPFlowMod that drops everything from this source.

    No actions means no output, which is how OpenFlow expresses a drop.
    ``hard_timeout`` overrides the configured lifetime, for reinstalled blocks.
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
        hard_timeout=cfg.block_timeout if hard_timeout is None else hard_timeout,
        command=ofproto.OFPFC_ADD,
    )


def learn_mac(table: dict, dpid, mac: str, port) -> object:
    """Record which port a MAC was seen on. Returns the port it left, or None.

    A container keeps its MAC when it is recreated but comes back on a new
    veth. The flows that send that MAC to the old port keep matching traffic,
    which refreshes their idle timeout, so they never expire and every packet
    for that host is forwarded into a port that no longer exists.
    """
    ports = table.setdefault(dpid, {})
    previous = ports.get(mac)
    ports[mac] = port
    if previous is None or previous == port:
        return None
    return previous


def build_forget_flow(datapath, mac: str):
    """A flow_mod that retracts every learned rule delivering to ``mac``.

    Matching on the destination alone is deliberate: the stale rules carry an
    in_port and a source as well, and a delete matches entries at least as
    specific as the request. Drop rules match on ipv4_src and survive.
    """
    parser = datapath.ofproto_parser
    ofproto = datapath.ofproto
    return parser.OFPFlowMod(
        datapath=datapath,
        command=ofproto.OFPFC_DELETE,
        table_id=0,
        match=parser.OFPMatch(eth_dst=mac),
        out_port=ofproto.OFPP_ANY,
        out_group=ofproto.OFPG_ANY,
    )


def build_clear_flows(datapath):
    """A flow_mod that empties table 0.

    Sent when a switch connects. The controller's MAC and block tables live in
    memory, so after a restart it knows nothing while the switch still holds
    rules from the previous run — including ones that deliver to ports that
    have since disappeared.
    """
    parser = datapath.ofproto_parser
    ofproto = datapath.ofproto
    return parser.OFPFlowMod(
        datapath=datapath,
        command=ofproto.OFPFC_DELETE,
        table_id=0,
        match=parser.OFPMatch(),
        out_port=ofproto.OFPP_ANY,
        out_group=ofproto.OFPG_ANY,
    )
