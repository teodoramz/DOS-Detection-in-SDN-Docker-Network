#!/bin/bash
# Host bridge, GRE tunnel to the other host, and the forwarding rules the
# overlay needs. Addresses come from the generated .env.

set -euo pipefail

HOME_DIR="${DDOS_DETECTION_HOME:-$(cd "$(dirname "$0")/.." && pwd)}"
set -a
# shellcheck disable=SC1091
source "${HOME_DIR}/.env"
set +a

source "$(dirname "$0")/../deploy/wire.sh"

sudo modprobe openvswitch

sudo ovs-vsctl --may-exist add-br br0
prune_dead_ports br0 sudo
sudo ip addr replace "${HOST1_MGMT_IP}/24" dev br0
sudo ip link set br0 up

sudo ovs-vsctl --may-exist add-port br0 gre-to-vm2 \
     -- set interface gre-to-vm2 type=gre \
     options:local_ip="${HOST1_IP}" \
     options:remote_ip="${HOST2_IP}"

sudo ovs-vsctl set interface gre-to-vm2 mtu_request=1400
sudo ip link set br0 mtu 1400

iptables_ensure -A INPUT  -p gre -j ACCEPT
iptables_ensure -A OUTPUT -p gre -j ACCEPT
iptables_ensure -I FORWARD -i gre-to-vm2 -j ACCEPT
iptables_ensure -I FORWARD -o gre-to-vm2 -j ACCEPT

sudo sysctl -w net.ipv4.ip_forward=1
iptables_ensure -I FORWARD -i br0 -j ACCEPT
iptables_ensure -I FORWARD -o br0 -j ACCEPT

sudo ip route replace 10.0.0.0/16 dev br0

sudo sysctl -w net.ipv4.conf.all.rp_filter=0
sudo sysctl -w net.ipv4.conf.default.rp_filter=0
