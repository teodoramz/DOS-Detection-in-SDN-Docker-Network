#!/bin/bash
# Re-runnable: every operation either replaces what is there or is skipped when
# it already exists.

source "$(dirname "$0")/../deploy/wire.sh"

prune_dead_ports br-sw5 docker exec sw5

# sw5
if ! has_if sw5 eth_br0; then
  sudo ovs-vsctl --if-exists del-port br0 veth-br-sw5
  ip link del veth-br-sw5 2>/dev/null || true
  ip link add veth-sw5-br type veth peer name veth-br-sw5
  ip link set veth-sw5-br netns $(docker inspect -f '{{.State.Pid}}' sw5)
  docker exec sw5 ip link set veth-sw5-br name eth_br0
fi
sudo ovs-vsctl --may-exist add-port br0 veth-br-sw5
ip link set veth-br-sw5 up

docker exec sw5 ip link set eth_br0 up
docker exec sw5 ip link set eth_br0  mtu 1400 

docker exec sw5 ovs-vsctl --may-exist add-br br-sw5
docker exec sw5 ovs-vsctl --may-exist add-port br-sw5 eth_br0
docker exec sw5 ip addr replace 10.255.255.5/24 dev br-sw5 #mgmt
docker exec sw5 ip link set br-sw5 up
docker exec sw5 ip link set br-sw5  mtu 1400 
docker exec sw5 ovs-vsctl set bridge br-sw5 other-config:datapath-id=0000000000000005
