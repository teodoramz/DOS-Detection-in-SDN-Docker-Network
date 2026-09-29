#!/bin/bash
# Re-runnable: every operation either replaces what is there or is skipped when
# it already exists.

link_absent() { ! ip link show "$1" >/dev/null 2>&1; }

# sw1
link_absent veth-sw1-br && ip link add veth-sw1-br type veth peer name veth-br-sw1 || true
sudo ovs-vsctl --may-exist add-port br0 veth-br-sw1
ip link set veth-br-sw1 up

pid=$(docker inspect -f '{{.State.Pid}}' sw1)
ip link set veth-sw1-br netns $pid
docker exec sw1 ip link set veth-sw1-br name eth_br0
docker exec sw1 ip link set eth_br0 up
docker exec sw1 ip link set eth_br0  mtu 1400 

docker exec sw1 ovs-vsctl --may-exist add-br br-sw1
docker exec sw1 ovs-vsctl --may-exist add-port br-sw1 eth_br0
docker exec sw1 ip addr replace 10.255.255.1/24 dev br-sw1 #mgmt
docker exec sw1 ip link set br-sw1 up
docker exec sw1 ip link set br-sw1  mtu 1400 

# sw4
link_absent veth-sw4-br && ip link add veth-sw4-br type veth peer name veth-br-sw4 || true
sudo ovs-vsctl --may-exist add-port br0 veth-br-sw4
ip link set veth-br-sw4 up

pid=$(docker inspect -f '{{.State.Pid}}' sw4)
ip link set veth-sw4-br netns $pid
docker exec sw4 ip link set veth-sw4-br name eth_br0
docker exec sw4 ip link set eth_br0 up
docker exec sw4 ip link set eth_br0   mtu 1400 

docker exec sw4 ovs-vsctl --may-exist add-br br-sw4
docker exec sw4 ovs-vsctl --may-exist add-port br-sw4 eth_br0
docker exec sw4 ip addr replace 10.255.255.4/24 dev br-sw4 #mgmt
docker exec sw4 ip link set br-sw4  up
docker exec sw4 ip link set br-sw4  mtu 1400