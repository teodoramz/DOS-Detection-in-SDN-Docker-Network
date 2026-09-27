#!/bin/sh
set -e

IF="${CAPTURE_INTERFACE:-eth0}"

if [ -n "${WAIT_FOR_IP}" ]; then
  echo "Waiting for ${IF} to have ${WAIT_FOR_IP}..."
  while ! ip -o addr show "${IF}" | grep -q "${WAIT_FOR_IP}/"; do
    sleep 0.2
  done
fi

echo "starting collector for layer ${LAYER}"
exec python -u /app/collector.py
