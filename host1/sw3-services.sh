# SERVICES-SRV (services container)
ip link add veth-proxy3-srv type veth peer name veth-sw3-psrv
ip link set veth-proxy3-srv netns $(docker inspect -f '{{.State.Pid}}' webserver)
ip link set veth-sw3-psrv  netns $(docker inspect -f '{{.State.Pid}}' sw3)

docker exec webserver ip link set veth-proxy3-srv name eth0
docker exec webserver ip addr add 10.0.3.2/24 dev eth0
docker exec webserver ip addr add 10.255.255.31/24  dev eth0  # mgmt
docker exec webserver ip link set eth0 up
docker exec webserver ip route add default via 10.0.3.1

docker exec sw3 ip link set veth-sw3-psrv name eth_psrv
docker exec sw3 ovs-vsctl add-port br-sw3 eth_psrv
docker exec sw3 ip link set eth_psrv up


# SERVICES-COL (webserver collector container)
ip link add veth-proxy3-col type veth peer name veth-sw3-pcol
ip link set veth-proxy3-col netns $(docker inspect -f '{{.State.Pid}}' web_collector)
ip link set veth-sw3-pcol  netns $(docker inspect -f '{{.State.Pid}}' sw3)

docker exec web_collector ip link set veth-proxy3-col name eth0
docker exec web_collector ip addr add 10.0.3.6/24 dev eth0
docker exec web_collector ip addr add 10.255.255.32/24 dev eth0  # mgmt
docker exec web_collector ip link set eth0 up
#docker exec web_collector ip route add default via 10.0.3.1

docker exec sw3 ip link set veth-sw3-pcol name eth_pcol
docker exec sw3 ovs-vsctl add-port br-sw3 eth_pcol
docker exec sw3 ip link set eth_pcol up

docker exec sw3 ovs-vsctl \
  -- --id=@MON get Port eth_psrv       \
  -- --id=@AN  get Port eth_pcol      \
  -- --id=@m   create Mirror name=m_srvs_to_srvscol \
       select-src-port=@MON select-dst-port=@MON \
       output-port=@AN \
  -- set Bridge br-sw3 mirrors=@m

docker exec web_collector ip link set eth0 promisc on