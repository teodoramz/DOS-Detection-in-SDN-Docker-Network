#!/bin/bash
# Intermediate layer: volumetric L3/L4 floods against the reverse proxy.
set -euo pipefail
source "$(dirname "$0")/lib.sh"

TARGET="${TARGET:-10.0.2.2}"
# The host's own address is whitelisted, so set SPOOF_SOURCE to an address that
# is not, to see a block installed.
SPOOF_SOURCE="${SPOOF_SOURCE:-}"
spoof=""
[ -n "${SPOOF_SOURCE}" ] && spoof="-a ${SPOOF_SOURCE}"

need hping3
echo "attacking proxy ${TARGET} for ${DURATION}s"

launch "hping3 SYN flood" hping3 ${spoof} -S --flood -p 80 "${TARGET}"
launch "hping3 UDP flood" hping3 ${spoof} -2 --flood -p 80 "${TARGET}"

finish
