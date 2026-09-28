#!/bin/sh
set -e

IF="${CAPTURE_INTERFACE:-eth0}"

if [ -n "${WAIT_FOR_IP}" ]; then
  echo "Waiting for ${IF} to have ${WAIT_FOR_IP}..."
  while ! ip -o addr show "${IF}" 2>/dev/null | grep -q "${WAIT_FOR_IP}/"; do
    sleep 0.5
  done
fi

echo "starting worker for layer ${WORKER_LAYER}"
exec python -m ddos_worker.main
