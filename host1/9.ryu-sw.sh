#!/bin/bash
# The datapath id is set explicitly so the controller can resolve a layer to a
# switch; otherwise OVS derives one from a MAC address and LAYER_DATAPATH_MAP
# would not hold.

set -e

CONTROLLER="tcp:10.255.255.254:6633"

for n in 1 2 3 4; do
  docker exec "sw${n}" ovs-vsctl \
    set bridge "br-sw${n}" "other-config:datapath-id=000000000000000${n}"

  docker exec "sw${n}" ovs-vsctl set-controller "br-sw${n}" "${CONTROLLER}" \
    -- set Bridge "br-sw${n}" protocols=OpenFlow13 fail-mode=secure

  echo "sw${n}: datapath 000000000000000${n} -> ${CONTROLLER}"
done
