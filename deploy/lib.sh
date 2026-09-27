#!/bin/bash
# Shared helpers for the deployment scripts.

say()  { printf '\n\033[1m==> %s\033[0m\n' "$*"; }
warn() { printf '\033[33m[warn]\033[0m %s\n' "$*"; }
die()  { printf '\033[31m[fail]\033[0m %s\n' "$*" >&2; exit 1; }

require_root() {
  [ "$EUID" -eq 0 ] || die "run this with sudo"
}

require_home() {
  [ -n "${DDOS_DETECTION_HOME:-}" ] || die "set DDOS_DETECTION_HOME to the repository root"
  [ -d "$DDOS_DETECTION_HOME" ] || die "DDOS_DETECTION_HOME=$DDOS_DETECTION_HOME is not a directory"
}

require_tools() {
  for tool in docker ip python3; do
    command -v "$tool" >/dev/null || die "$tool is not installed; run utils/dependencies.sh"
  done
  docker compose version >/dev/null 2>&1 || die "docker compose v2 is not installed"
  modprobe openvswitch 2>/dev/null || warn "could not load the openvswitch module"
}

generate_env() {
  say "Generating .env from the CSV inventory"
  python3 "$DDOS_DETECTION_HOME/startup/scripts/update_env.py"
  python3 "$DDOS_DETECTION_HOME/startup/scripts/generate_markdown.py"
  [ -f "$DDOS_DETECTION_HOME/.env" ] || die ".env was not produced"
}

wait_for_container() {
  local name=$1 tries=${2:-40}
  for _ in $(seq "$tries"); do
    [ "$(docker inspect -f '{{.State.Running}}' "$name" 2>/dev/null)" = "true" ] && return 0
    sleep 1
  done
  die "container $name did not start"
}
