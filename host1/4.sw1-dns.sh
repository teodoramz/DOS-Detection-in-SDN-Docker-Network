#!/bin/bash
# Re-runnable: every operation either replaces what is there or is skipped when
# it already exists.

link_absent() { ! ip link show "$1" >/dev/null 2>&1; }

# DNS-SRV (dns container)
link_absent veth-dns-srv && ip link add veth-dns-srv type veth peer name veth-sw1-dns || true
ip link set veth-dns-srv netns $(docker inspect -f '{{.State.Pid}}' dns)
ip link set veth-sw1-dns netns $(docker inspect -f '{{.State.Pid}}' sw1)

docker exec dns ip link set veth-dns-srv name eth0
docker exec dns ip addr replace 10.0.1.2/24 dev eth0
docker exec dns ip addr replace 10.255.255.11/24 dev eth0
docker exec dns ip link set eth0 up
docker exec dns ip link set eth0 mtu 1400 
docker exec dns ip route replace default via 10.0.1.1

docker exec sw1 ip link set veth-sw1-dns name eth_dns
docker exec sw1 ovs-vsctl --may-exist add-port br-sw1 eth_dns
docker exec sw1 ip link set eth_dns up
docker exec sw1 ip link set eth_dns mtu 1400 

# DNS-COL (dns collector container)
link_absent veth-dns-col && ip link add veth-dns-col type veth peer name veth-sw1-dcol || true
ip link set veth-dns-col netns $(docker inspect -f '{{.State.Pid}}' dns_collector)
ip link set veth-sw1-dcol netns $(docker inspect -f '{{.State.Pid}}' sw1)

docker exec dns_collector ip link set veth-dns-col name eth0
docker exec dns_collector ip addr replace 10.0.1.6/24 dev eth0
docker exec dns_collector ip addr replace 10.255.255.12/24 dev eth0 
docker exec dns_collector ip link set eth0 up
docker exec dns_collector ip link set eth0 mtu 1400 
#docker exec dns_collector ip route replace default via 10.0.1.1


docker exec sw1 ip link set veth-sw1-dcol name eth_dcol
docker exec sw1 ovs-vsctl --may-exist add-port br-sw1 eth_dcol
docker exec sw1 ip link set eth_dcol up
docker exec sw1 ip link set eth_dcol mtu 1400 

docker exec sw1 ovs-vsctl \
  -- --id=@MON get Port eth_dns       \
  -- --id=@AN  get Port eth_dcol      \
  -- --id=@m   create Mirror name=m_dns_to_dnscol \
       select-src-port=@MON select-dst-port=@MON \
       output-port=@AN \
  -- set Bridge br-sw1 mirrors=@m

docker exec dns_collector ip link set eth0 promisc on
