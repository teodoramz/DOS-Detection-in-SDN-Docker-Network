# sw1
ip link add veth-c0-sw1 type veth peer name veth-sw1-c0
ip link set veth-c0-sw1 up
ip addr add 172.16.0.1/30 dev veth-c0-sw1    # host-side

ip link set veth-sw1-c0 netns $(docker inspect -f '{{.State.Pid}}' sw1)
docker exec sw1 ip link set veth-sw1-c0 name eth_mgmt
docker exec sw1 ip addr add 172.16.0.2/30 dev eth_mgmt
docker exec sw1 ip link set eth_mgmt up

# sw2
ip link add veth-c0-sw2 type veth peer name veth-sw2-c0
ip link set veth-c0-sw2 up
ip addr add 172.16.0.5/30 dev veth-c0-sw2

ip link set veth-sw2-c0 netns $(docker inspect -f '{{.State.Pid}}' sw2)
docker exec sw2 ip link set veth-sw2-c0 name eth_mgmt
docker exec sw2 ip addr add 172.16.0.6/30 dev eth_mgmt
docker exec sw2 ip link set eth_mgmt up

# sw3
ip link add veth-c0-sw3 type veth peer name veth-sw3-c0
ip link set veth-c0-sw3 up
ip addr add 172.16.0.9/30 dev veth-c0-sw3

ip link set veth-sw3-c0 netns $(docker inspect -f '{{.State.Pid}}' sw3)
docker exec sw3 ip link set veth-sw3-c0 name eth_mgmt
docker exec sw3 ip addr add 172.16.0.10/30 dev eth_mgmt
docker exec sw3 ip link set eth_mgmt up
