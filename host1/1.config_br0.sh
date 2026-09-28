#!/bin/bash
# Host bridge, GRE tunnel to the other host, and the forwarding rules the
# overlay needs. Addresses come from the generated .env.

set -euo pipefail

HOME_DIR="${DDOS_DETECTION_HOME:-$(cd "$(dirname "$0")/.." && pwd)}"
set -a
# shellcheck disable=SC1091
source "${HOME_DIR}/.env"
set +a

sudo modprobe openvswitch

sudo ovs-vsctl --may-exist add-br br0
sudo ip addr replace "${HOST1_MGMT_IP}/24" dev br0
sudo ip link set br0 up

sudo ovs-vsctl --may-exist add-port br0 gre-to-vm2 \
     -- set interface gre-to-vm2 type=gre \
     options:local_ip="${HOST1_IP}" \
     options:remote_ip="${HOST2_IP}"

sudo ip link set gre-to-vm2 mtu 1400
sudo ip link set br0 mtu 1400

sudo iptables -A INPUT  -p gre -j ACCEPT
sudo iptables -A OUTPUT -p gre -j ACCEPT
sudo iptables -I FORWARD -i gre-to-vm2 -j ACCEPT
sudo iptables -I FORWARD -o gre-to-vm2 -j ACCEPT

sudo sysctl -w net.ipv4.ip_forward=1
sudo iptables -I FORWARD -i br0 -j ACCEPT
sudo iptables -I FORWARD -o br0 -j ACCEPT

sudo ip route replace 10.0.0.0/16 dev br0

sudo sysctl -w net.ipv4.conf.all.rp_filter=0
sudo sysctl -w net.ipv4.conf.default.rp_filter=0
