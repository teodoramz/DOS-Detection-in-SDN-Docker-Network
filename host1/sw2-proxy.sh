# PROXY-SRV (proxy container)
ip link add veth-proxy-srv type veth peer name veth-sw2-psrv
ip link set veth-proxy-srv netns $(docker inspect -f '{{.State.Pid}}' proxy)
ip link set veth-sw2-psrv netns $(docker inspect -f '{{.State.Pid}}' sw2)

docker exec proxy ip link set veth-proxy-srv name eth0
docker exec proxy ip addr add 10.0.2.2/24 dev eth0
docker exec proxy ip addr add 10.255.255.21/24 dev eth0
docker exec proxy ip link set eth0 up
docker exec proxy ip route add default via 10.0.2.1

docker exec sw2 ip link set veth-sw2-psrv name eth_proxy
docker exec sw2 ovs-vsctl add-port br-sw2 eth_proxy
docker exec sw2 ip link set eth_proxy up

# PROXY-COL (proxy collector container)
ip link add veth-proxy-col type veth peer name veth-sw2-pcol
ip link set veth-proxy-col netns $(docker inspect -f '{{.State.Pid}}' proxy_collector)
ip link set veth-sw2-pcol netns $(docker inspect -f '{{.State.Pid}}' sw2)

docker exec proxy_collector ip link set veth-proxy-col name eth0
docker exec proxy_collector ip addr add 10.0.2.6/24 dev eth0
docker exec proxy_collector ip addr add 10.255.255.22/24 dev eth0
docker exec proxy_collector ip link set eth0 up
#docker exec proxy_collector ip route add default via 10.0.2.1

docker exec sw2 ip link set veth-sw2-pcol name eth_pcol
docker exec sw2 ovs-vsctl add-port br-sw2 eth_pcol
docker exec sw2 ip link set eth_pcol up

docker exec sw2 ovs-vsctl \
  -- --id=@MON get Port eth_proxy       \
  -- --id=@AN  get Port eth_pcol      \
  -- --id=@m   create Mirror name=m_proxy_to_proxycol \
       select-src-port=@MON select-dst-port=@MON \
       output-port=@AN \
  -- set Bridge br-sw2 mirrors=@m

docker exec proxy_collector ip link set eth0 promisc on