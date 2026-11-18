#!/bin/bash
# Re-runnable: every operation either replaces what is there or is skipped when
# it already exists.

source "$(dirname "$0")/../deploy/wire.sh"

### ---------- sw1 <-> sw2 ----------
if ! wired sw1 eth_sw2 sw2 eth_sw1; then
  ip link add veth-sw1-sw2 type veth peer name veth-sw2-sw1
  ip link set veth-sw1-sw2 netns $(docker inspect -f '{{.State.Pid}}' sw1)
  ip link set veth-sw2-sw1 netns $(docker inspect -f '{{.State.Pid}}' sw2)
  docker exec sw1 ip link set veth-sw1-sw2 name eth_sw2
  docker exec sw2 ip link set veth-sw2-sw1 name eth_sw1
fi

docker exec sw1 ip link set eth_sw2 up
docker exec sw1 ip link set eth_sw2 mtu 1400 
docker exec sw1 ovs-vsctl --may-exist add-port br-sw1 eth_sw2

docker exec sw2 ip link set eth_sw1 up
docker exec sw2 ip link set eth_sw1 mtu 1400 
docker exec sw2 ovs-vsctl --may-exist add-br br-sw2
docker exec sw2 ovs-vsctl --may-exist add-port br-sw2 eth_sw1
docker exec sw2 ip addr replace 10.255.255.2/24 dev br-sw2 #mgmt
docker exec sw2 ip link set br-sw2  up
docker exec sw2 ip link set br-sw2 mtu 1400 

### ---------- sw2 <-> sw3 ----------
if ! wired sw2 eth_sw3 sw3 eth_sw2; then
  ip link add veth-sw2-sw3 type veth peer name veth-sw3-sw2
  ip link set veth-sw2-sw3 netns $(docker inspect -f '{{.State.Pid}}' sw2)
  ip link set veth-sw3-sw2 netns $(docker inspect -f '{{.State.Pid}}' sw3)
  docker exec sw2 ip link set veth-sw2-sw3 name eth_sw3
  docker exec sw3 ip link set veth-sw3-sw2 name eth_sw2
fi

docker exec sw2 ip link set eth_sw3 up
docker exec sw2 ip link set eth_sw3 mtu 1400 
docker exec sw2 ovs-vsctl --may-exist add-port br-sw2 eth_sw3

docker exec sw3 ip link set eth_sw2 up
docker exec sw3 ip link set eth_sw2 mtu 1400 
docker exec sw3 ovs-vsctl --may-exist add-br br-sw3
docker exec sw3 ovs-vsctl --may-exist add-port br-sw3 eth_sw2
docker exec sw3 ip addr replace 10.255.255.3/24 dev br-sw3  # mgmt
docker exec sw3 ip link set br-sw3 up
docker exec sw3 ip link set br-sw3  mtu 1400 