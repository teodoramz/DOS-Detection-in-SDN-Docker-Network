#!/bin/bash
# Shared helpers for the deployment scripts.

# Compose names a project after the directory it is run from, so a renamed or
# moved checkout would fight its own containers for their names. Pin it.
export COMPOSE_PROJECT_NAME="ddos"

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

# Sets CLEAN, REWIRE and INSTALL_UNIT from the deploy script's arguments.
# The calling script defines usage().
parse_deploy_args() {
  CLEAN=""
  REWIRE=""
  INSTALL_UNIT="${DDOS_BOOT_UNIT:-1}"
  while [ $# -gt 0 ]; do
    case "$1" in
      --clean) CLEAN=1 ;;
      --rewire) REWIRE=1 ;;
      --no-boot-unit) INSTALL_UNIT=0 ;;
      --help|-h) usage; exit 0 ;;
      *) usage >&2; die "unknown argument: $1" ;;
    esac
    shift
  done
  if [ -n "$CLEAN" ] && [ -n "$REWIRE" ]; then
    die "--clean and --rewire do not go together: one rebuilds, the other keeps"
  fi
}

# Installs and enables the unit that rewires this host on boot. Repeating it is
# safe: an unchanged unit is left alone. DDOS_BOOT_UNIT=0 or --no-boot-unit skips
# it.
install_boot_unit() {
  local host=$1 unit=/etc/systemd/system/ddos-testbed.service tmp
  local template="$DDOS_DETECTION_HOME/deploy/systemd/ddos-testbed.service.in"
  if [ "${INSTALL_UNIT:-1}" = 0 ]; then
    warn "not installing the boot unit; this host will not rewire itself after a reboot"
    return 0
  fi
  command -v systemctl >/dev/null || { warn "no systemd here, skipping the boot unit"; return 0; }
  say "Installing the boot unit"
  tmp=$(mktemp)
  sed -e "s|@DDOS_HOME@|$DDOS_DETECTION_HOME|g" -e "s|@HOST@|$host|g" "$template" > "$tmp"
  if ! cmp -s "$tmp" "$unit"; then
    install -m 644 "$tmp" "$unit"
    systemctl daemon-reload
  fi
  rm -f "$tmp"
  systemctl enable ddos-testbed.service
}

generate_env() {
  say "Generating .env from the CSV inventory"
  python3 "$DDOS_DETECTION_HOME/startup/scripts/update_env.py"
  python3 "$DDOS_DETECTION_HOME/startup/scripts/generate_markdown.py"
  [ -f "$DDOS_DETECTION_HOME/.env" ] || die ".env was not produced"
}

wait_for_container() {
  local name=$1 tries=${2:-40} stable=0
  for _ in $(seq "$tries"); do
    case "$(docker inspect -f '{{.State.Status}}' "$name" 2>/dev/null)" in
      running)
        # Require two consecutive checks, so a crash-looping container is not
        # mistaken for a healthy one during the moment it is up.
        stable=$((stable + 1))
        [ "$stable" -ge 2 ] && return 0
        ;;
      restarting)
        stable=0
        ;;
      exited|dead)
        die "container $name exited: $(docker logs --tail 3 "$name" 2>&1 | tail -1)"
        ;;
    esac
    sleep 1
  done
  die "container $name never stayed up: $(docker logs --tail 3 "$name" 2>&1 | tail -1)"
}

# A switch container is "running" a moment before its OVS database answers.
wait_for_ovs() {
  for name in "$@"; do
    for _ in $(seq 30); do
      docker exec "$name" ovs-vsctl --timeout=2 show >/dev/null 2>&1 && continue 2
      sleep 1
    done
    die "openvswitch in $name never answered"
  done
}

remove_stale_containers() {
  for name in "$@"; do
    docker rm -f "$name" >/dev/null 2>&1 || true
  done
}

# The management addresses are internal to the testbed and are referenced by
# every topology script and by the block whitelist, so only the two host
# addresses move when the testbed does.
render_hosts_csv() {
  local host1_ip=$1 host2_ip=$2 out=$3
  local pattern='^[0-9]{1,3}(\.[0-9]{1,3}){3}$'
  [[ $host1_ip =~ $pattern ]] || die "host1 address is not an IPv4 address: $host1_ip"
  [[ $host2_ip =~ $pattern ]] || die "host2 address is not an IPv4 address: $host2_ip"
  mkdir -p "$(dirname "$out")"
  cat > "$out" <<CSV
Name,Ip address default interface,Mgmt IP
host1,${host1_ip},10.255.255.254/24
host2,${host2_ip},10.255.255.253/24
CSV
}
