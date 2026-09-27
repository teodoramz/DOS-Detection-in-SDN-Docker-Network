#!/bin/bash
# Watch the pipeline react: alerts, blocks and installed flow rules.
set -uo pipefail

RYU_URL="${RYU_URL:-http://127.0.0.1:8080}"

while true; do
  clear
  echo "=== ryu status ==="
  curl -sf "${RYU_URL}/ddos/status" || echo "controller not answering"
  echo
  echo "=== active blocks ==="
  curl -sf "${RYU_URL}/ddos/blocks" || true
  echo
  for n in 1 2 3; do
    echo "=== br-sw${n} drop rules ==="
    sudo docker exec "sw${n}" ovs-ofctl -O OpenFlow13 dump-flows "br-sw${n}" 2>/dev/null \
      | grep -E 'priority=100' || echo "  none"
  done
  sleep 5
done
