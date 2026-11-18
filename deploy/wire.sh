#!/bin/bash
# Helpers for the numbered topology scripts, so each one can be re-run on a host
# that is already wired, half wired, or just rebooted.

# Does the container have an interface called $2? Goes through the container's
# PID rather than docker exec, because minio ships no shell and no ip.
has_if() {
  local pid
  pid=$(docker inspect -f '{{.State.Pid}}' "$1" 2>/dev/null) || return 1
  [ -n "$pid" ] && [ "$pid" != 0 ] || return 1
  nsenter -t "$pid" -n ip link show "$2" >/dev/null 2>&1
}

# Are both ends of a veth already inside their containers?
# The host never keeps the container-side name, so it cannot tell.
wired() { has_if "$1" "$2" && has_if "$3" "$4"; }

# Delete OVS ports whose device is gone, such as the ports left in a database
# that outlived a reboot. Tunnel and other virtual ports have no device by
# design and are left alone. The arguments after the bridge run a command in
# the right namespace: sudo, or docker exec swN.
prune_dead_ports() {
  local bridge=$1 port type
  shift
  for port in $("$@" ovs-vsctl list-ports "$bridge" 2>/dev/null); do
    type=$("$@" ovs-vsctl get Interface "$port" type | tr -d '"') || continue
    case "$type" in
      ""|internal) ;;
      *) continue ;;
    esac
    "$@" ip link show "$port" >/dev/null 2>&1 \
      || "$@" ovs-vsctl --if-exists del-port "$bridge" "$port"
  done
}

# iptables_ensure -A|-I CHAIN RULE...: add the rule only if it is not there.
iptables_ensure() {
  local op=$1
  shift
  sudo iptables -C "$@" 2>/dev/null || sudo iptables "$op" "$@"
}
