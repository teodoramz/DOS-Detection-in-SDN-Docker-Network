"""Bound a pcap's packet count before it reaches the flow converter."""

from __future__ import annotations

import logging
import mmap
import os
import struct
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)

# classic pcap magic numbers, microsecond and nanosecond, in file byte order
_MAGICS = {
    b"\xd4\xc3\xb2\xa1": "<", b"\xa1\xb2\xc3\xd4": ">",
    b"\x4d\x3c\xb2\xa1": "<", b"\xa1\xb2\x3c\x4d": ">",
}
_GLOBAL_HEADER = 24
_RECORD_HEADER = 16


def count_packets(pcap: Path, limit: int):
    """Packets in a classic pcap, counting no further than ``limit + 1``.

    None when the file is not a classic pcap, so the caller leaves it alone.
    """
    try:
        with open(pcap, "rb") as fh:
            if os.fstat(fh.fileno()).st_size < _GLOBAL_HEADER:
                return None
            with mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ) as data:
                order = _MAGICS.get(bytes(data[:4]))
                if order is None:
                    return None
                unpack = struct.Struct(order + "IIII").unpack_from
                count, pos, size = 0, _GLOBAL_HEADER, len(data)
                while count <= limit and pos + _RECORD_HEADER <= size:
                    end = pos + _RECORD_HEADER + unpack(data, pos)[2]
                    if end > size:
                        break
                    count += 1
                    pos = end
                return count
    except (OSError, ValueError):
        return None


def trim_capture(pcap: Path, max_packets: int, *, runner=subprocess.run) -> bool:
    """Cut ``pcap`` to its first ``max_packets`` packets. True when it was cut.

    A failure leaves the original in place: the converter may still cope, and
    if it does not that is one window lost, not a dead worker.
    """
    pcap = Path(pcap)
    if max_packets <= 0:
        return False
    total = count_packets(pcap, max_packets)
    if total is None or total <= max_packets:
        return False

    original = pcap.stat().st_size
    trimmed = pcap.with_name(pcap.name + ".trim")
    cmd = ["tcpdump", "-r", str(pcap), "-c", str(max_packets), "-w", str(trimmed)]
    try:
        result = runner(cmd, capture_output=True, timeout=300)
        if result.returncode != 0 or not trimmed.is_file():
            raise RuntimeError(f"tcpdump exit {result.returncode}")
        os.replace(trimmed, pcap)
    except Exception as exc:
        log.warning("could not trim %s (%s); converting it whole", pcap.name, exc)
        trimmed.unlink(missing_ok=True)
        return False

    log.warning(
        "trimmed %s to its first %d packets (original over %d packets, %.0f MB)",
        pcap.name, max_packets, max_packets, original / 1e6,
    )
    return True
