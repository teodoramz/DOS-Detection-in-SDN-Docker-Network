# attach containers to sw4

# dns-colector to sw4
ip link add veth-dcol2-sw4 type veth peer name veth-sw4-dcol2
ip link set veth-dcol2-sw4 netns $(docker inspect -f '{{.State.Pid}}' dns_collector)
ip link set veth-sw4-dcol2 netns $(docker inspect -f '{{.State.Pid}}' sw4)

docker exec dns_collector ip link set veth-dcol2-sw4 name eth1
docker exec dns_collector ip addr add 10.0.4.2/24 dev eth1
docker exec dns_collector ip link set eth1 up
docker exec dns_collector ip route add default via 10.0.4.1

docker exec sw4 ip link set veth-sw4-dcol2 name eth_dcol2
docker exec sw4 ovs-vsctl add-port br-sw4 eth_dcol2
docker exec sw4 ip link set eth_dcol2 up


# proxy-collector to sw4
ip link add veth-proxy-col2 type veth peer name veth-sw4-pcol2
ip link set veth-proxy-col2 netns $(docker inspect -f '{{.State.Pid}}' proxy_collector)
ip link set veth-sw4-pcol2 netns $(docker inspect -f '{{.State.Pid}}' sw4)

docker exec proxy_collector ip link set veth-proxy-col2 name eth1
docker exec proxy_collector ip addr add 10.0.4.3/24 dev eth1
docker exec proxy_collector ip link set eth1 up
docker exec proxy_collector ip route add default via 10.0.4.1

docker exec sw4 ip link set veth-sw4-pcol2 name eth_pcol2
docker exec sw4 ovs-vsctl add-port br-sw4 eth_pcol2
docker exec sw4 ip link set eth_pcol2 up

# services-collector to sw4
ip link add veth-serv-col2 type veth peer name veth-sw4-scol2
ip link set veth-serv-col2 netns $(docker inspect -f '{{.State.Pid}}' web_collector)
ip link set veth-sw4-scol2 netns $(docker inspect -f '{{.State.Pid}}' sw4)

docker exec web_collector ip link set veth-serv-col2 name eth1
docker exec web_collector ip addr add 10.0.4.4/24 dev eth1
docker exec web_collector ip link set eth1 up
docker exec web_collector ip route add default via 10.0.4.1

docker exec sw4 ip link set veth-sw4-scol2 name eth_scol2
docker exec sw4 ovs-vsctl add-port br-sw4 eth_scol2
docker exec sw4 ip link set eth_scol2 up