#!/bin/bash
# Re-runnable: every operation either replaces what is there or is skipped when
# it already exists.

source "$(dirname "$0")/../deploy/wire.sh"

for n in 1 2 3 4; do prune_dead_ports br-sw$n docker exec sw$n; done

# sw1
if ! has_if sw1 eth_br0; then
  sudo ovs-vsctl --if-exists del-port br0 veth-br-sw1
  ip link del veth-br-sw1 2>/dev/null || true
  ip link add veth-sw1-br type veth peer name veth-br-sw1
  ip link set veth-sw1-br netns $(docker inspect -f '{{.State.Pid}}' sw1)
  docker exec sw1 ip link set veth-sw1-br name eth_br0
fi
sudo ovs-vsctl --may-exist add-port br0 veth-br-sw1
ip link set veth-br-sw1 up

docker exec sw1 ip link set eth_br0 up
docker exec sw1 ip link set eth_br0  mtu 1400 

docker exec sw1 ovs-vsctl --may-exist add-br br-sw1
docker exec sw1 ovs-vsctl --may-exist add-port br-sw1 eth_br0
docker exec sw1 ip addr replace 10.255.255.1/24 dev br-sw1 #mgmt
docker exec sw1 ip link set br-sw1 up
docker exec sw1 ip link set br-sw1  mtu 1400 

# sw4
if ! has_if sw4 eth_br0; then
  sudo ovs-vsctl --if-exists del-port br0 veth-br-sw4
  ip link del veth-br-sw4 2>/dev/null || true
  ip link add veth-sw4-br type veth peer name veth-br-sw4
  ip link set veth-sw4-br netns $(docker inspect -f '{{.State.Pid}}' sw4)
  docker exec sw4 ip link set veth-sw4-br name eth_br0
fi
sudo ovs-vsctl --may-exist add-port br0 veth-br-sw4
ip link set veth-br-sw4 up

docker exec sw4 ip link set eth_br0 up
docker exec sw4 ip link set eth_br0   mtu 1400 

docker exec sw4 ovs-vsctl --may-exist add-br br-sw4
docker exec sw4 ovs-vsctl --may-exist add-port br-sw4 eth_br0
docker exec sw4 ip addr replace 10.255.255.4/24 dev br-sw4 #mgmt
docker exec sw4 ip link set br-sw4  up
docker exec sw4 ip link set br-sw4  mtu 1400