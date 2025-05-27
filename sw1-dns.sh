# DNS-SRV (container-test1)
ip link add veth-dns-srv type veth peer name veth-sw1-dns
ip link set veth-dns-srv netns $(docker inspect -f '{{.State.Pid}}' container-test1)
ip link set veth-sw1-dns netns $(docker inspect -f '{{.State.Pid}}' sw1)

docker exec container-test1 ip link set veth-dns-srv name eth0
docker exec container-test1 ip addr add 10.0.1.2/30 dev eth0
docker exec container-test1 ip addr add 10.255.255.11/24 dev eth0
docker exec container-test1 ip link set eth0 up
docker exec container-test1 ip route add default via 10.0.1.1

docker exec sw1 ip link set veth-sw1-dns name eth_dns
docker exec sw1 ip link set eth_dns up
docker exec sw1 ovs-vsctl add-port br-sw1 eth_dns
docker exec sw1 ip addr add 10.0.1.1/30 dev eth_dns


# DNS-COL (container-test2)
ip link add veth-dns-col type veth peer name veth-sw1-dcol
ip link set veth-dns-col netns $(docker inspect -f '{{.State.Pid}}' container-test2)
ip link set veth-sw1-dcol netns $(docker inspect -f '{{.State.Pid}}' sw1)

docker exec container-test2 ip link set veth-dns-col name eth0
docker exec container-test2 ip addr add 10.0.1.6/30 dev eth0
docker exec container-test2 ip addr add 10.255.255.12/24 dev eth0 
docker exec container-test2 ip link set eth0 up
docker exec container-test2 ip route add default via 10.0.1.5

docker exec sw1 ip link set veth-sw1-dcol name eth_dcol
docker exec sw1 ip link set eth_dcol up
docker exec sw1 ovs-vsctl add-port br-sw1 eth_dcol
docker exec sw1 ip addr add 10.0.1.5/30 dev eth_dcol
