#!/bin/bash
# Point every bridge at the Ryu controller.
#
# The datapath id is set explicitly so the controller can resolve a layer to a
# switch; otherwise OVS derives one from a MAC address and LAYER_DATAPATH_MAP
# would not hold.

set -euo pipefail

HOME_DIR="${DDOS_DETECTION_HOME:-$(cd "$(dirname "$0")/.." && pwd)}"
set -a
# shellcheck disable=SC1091
source "${HOME_DIR}/.env"
set +a

CONTROLLER="tcp:${HOST1_MGMT_IP}:${SDN_PORT}"

for n in 1 2 3 4; do
  docker exec "sw${n}" ovs-vsctl \
    set bridge "br-sw${n}" "other-config:datapath-id=000000000000000${n}"

  docker exec "sw${n}" ovs-vsctl set-controller "br-sw${n}" "${CONTROLLER}" \
    -- set Bridge "br-sw${n}" protocols=OpenFlow13 fail-mode=secure

  echo "sw${n}: datapath 000000000000000${n} -> ${CONTROLLER}"
done
