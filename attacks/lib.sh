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

trap 'stop_all' INT TERM
