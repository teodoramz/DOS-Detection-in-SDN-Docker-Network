#!/bin/bash
# Re-runnable: every operation either replaces what is there or is skipped when
# it already exists.

link_absent() { ! ip link show "$1" >/dev/null 2>&1; }

# sw5
link_absent veth-sw5-br && ip link add veth-sw5-br type veth peer name veth-br-sw5 || true
sudo ovs-vsctl --may-exist add-port br0 veth-br-sw5
ip link set veth-br-sw5 up

pid=$(docker inspect -f '{{.State.Pid}}' sw5)
ip link set veth-sw5-br netns $pid
docker exec sw5 ip link set veth-sw5-br name eth_br0
docker exec sw5 ip link set eth_br0 up
docker exec sw5 ip link set eth_br0  mtu 1400 

docker exec sw5 ovs-vsctl --may-exist add-br br-sw5
docker exec sw5 ovs-vsctl --may-exist add-port br-sw5 eth_br0
docker exec sw5 ip addr replace 10.255.255.5/24 dev br-sw5 #mgmt
docker exec sw5 ip link set br-sw5 up
docker exec sw5 ip link set br-sw5  mtu 1400 
docker exec sw5 ovs-vsctl set bridge br-sw5 other-config:datapath-id=0000000000000005
