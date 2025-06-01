# PROXY-SRV (container-test3)
ip link add veth-proxy-srv type veth peer name veth-sw2-psrv
ip link set veth-proxy-srv netns $(docker inspect -f '{{.State.Pid}}' container-test3)
ip link set veth-sw2-psrv netns $(docker inspect -f '{{.State.Pid}}' sw2)

docker exec container-test3 ip link set veth-proxy-srv name eth0
docker exec container-test3 ip addr add 10.0.2.2/24 dev eth0
docker exec container-test3 ip addr add 10.255.255.21/24 dev eth0
docker exec container-test3 ip link set eth0 up
docker exec container-test3 ip route add default via 10.0.2.1

docker exec sw2 ip link set veth-sw2-psrv name eth_proxy
docker exec sw2 ovs-vsctl add-port br-sw2 eth_proxy
docker exec sw2 ip link set eth_proxy up

# PROXY-COL (container-test4)
ip link add veth-proxy-col type veth peer name veth-sw2-pcol
ip link set veth-proxy-col netns $(docker inspect -f '{{.State.Pid}}' container-test4)
ip link set veth-sw2-pcol netns $(docker inspect -f '{{.State.Pid}}' sw2)

docker exec container-test4 ip link set veth-proxy-col name eth0
docker exec container-test4 ip addr add 10.0.2.6/24 dev eth0
docker exec container-test4 ip addr add 10.255.255.22/24 dev eth0
docker exec container-test4 ip link set eth0 up
docker exec container-test4 ip route add default via 10.0.2.1

docker exec sw2 ip link set veth-sw2-pcol name eth_pcol
docker exec sw2 ovs-vsctl add-port br-sw2 eth_pcol
docker exec sw2 ip link set eth_pcol up