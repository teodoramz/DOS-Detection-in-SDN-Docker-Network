#!/bin/bash
# Remove everything the topology scripts create, on either host.

for n in 1 2 3 4 5; do
  docker exec "sw${n}" ovs-vsctl --if-exists del-br "br-sw${n}" 2>/dev/null || true
done

for port in veth-br-sw1 veth-br-sw2 veth-br-sw3 veth-br-sw4 veth-br-sw5 \
            gre-to-vm1 gre-to-vm2; do
  sudo ovs-vsctl --if-exists del-port br0 "$port" 2>/dev/null || true
done

for veth in veth-br-sw1 veth-br-sw2 veth-br-sw3 veth-br-sw4 veth-br-sw5; do
  sudo ip link del "$veth" 2>/dev/null || true
done

# Match on the trimmed name so a bridge created by a CRLF-damaged script, which
# OVS records as "br0\r", is removed too.
for br in $(sudo ovs-vsctl list-br 2>/dev/null); do
  case "$(printf '%s' "$br" | tr -d '\r')" in
    br0) sudo ovs-vsctl --if-exists del-br "$br" ;;
  esac
done

echo "cleanup done"
