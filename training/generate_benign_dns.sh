#!/bin/bash
# Ordinary DNS lookups from a topology container, at a set rate per 30 s window.
#   sudo PER_WINDOW=20 DURATION=300 ./training/generate_benign_dns.sh
#   sudo RATES="5 10 20 40" WINDOWS=4 ./training/generate_benign_dns.sh
set -euo pipefail
source "$(dirname "$0")/../attacks/lib.sh"

TARGET="${TARGET:-10.0.1.2}"
ZONE="${ZONE:-cyberstuff.local}"
CONTAINER="${CONTAINER:-proxy}"
WINDOW="${WINDOW:-30}"
PER_WINDOW="${PER_WINDOW:-20}"
RATES="${RATES:-}"
WINDOWS="${WINDOWS:-2}"

need docker
docker exec "${CONTAINER}" which dig >/dev/null 2>&1 || {
  echo "container ${CONTAINER} has no dig; set CONTAINER to one that does" >&2
  exit 1
}

# Existing names first, then ones that answer NXDOMAIN, as real clients produce both.
NAMES=("${ZONE}" "www.${ZONE}" "ns1.${ZONE}" "mail.${ZONE}" "api.${ZONE}" "intranet.${ZONE}")
TYPES=(A A A AAAA NS TXT)

lookup() {
  local i=$((RANDOM % ${#NAMES[@]}))
  local t=${TYPES[$((RANDOM % ${#TYPES[@]}))]}
  docker exec "${CONTAINER}" dig "@${TARGET}" "${NAMES[$i]}" "${t}" \
      +short +tries=1 +time=2 >/dev/null 2>&1 || true
}

# Spread n lookups evenly over `seconds`.
run_rate() {
  local n=$1 seconds=$2
  local total=$(( n * seconds / WINDOW ))
  [ "${total}" -lt 1 ] && total=1
  local gap
  gap=$(awk -v s="${seconds}" -v t="${total}" 'BEGIN { printf "%.3f", s / t }')
  echo "  ${n} lookups per ${WINDOW}s window: ${total} lookups over ${seconds}s, one every ${gap}s"
  local k
  for k in $(seq "${total}"); do
    lookup
    sleep "${gap}"
  done
}

echo "benign DNS from ${CONTAINER} to ${TARGET} (${ZONE})"
if [ -n "${RATES}" ]; then
  for rate in ${RATES}; do
    run_rate "${rate}" $(( WINDOWS * WINDOW ))
  done
else
  run_rate "${PER_WINDOW}" "${DURATION}"
fi
echo "done"
