### ---------- sw1 <-> sw2 ----------
ip link add veth-sw1-sw2 type veth peer name veth-sw2-sw1
ip link set veth-sw1-sw2 netns $(docker inspect -f '{{.State.Pid}}' sw1)
ip link set veth-sw2-sw1 netns $(docker inspect -f '{{.State.Pid}}' sw2)

docker exec sw1 ip link set veth-sw1-sw2 name eth_sw2
docker exec sw1 ip link set eth_sw2 up
docker exec sw1 ovs-vsctl add-port br-sw1 eth_sw2
docker exec sw1 ip addr add 10.0.0.9/30 dev eth_sw2

docker exec sw2 ip link set veth-sw2-sw1 name eth_sw1
docker exec sw2 ip link set eth_sw1 up
docker exec sw2 ovs-vsctl add-br br-sw2
docker exec sw2 ovs-vsctl add-port br-sw2 eth_sw1
docker exec sw2 ip addr add 10.0.0.10/30 dev eth_sw1
docker exec sw2 ip addr add 10.255.255.2/24 dev br-sw2 #mgmt
docker exec sw2 ip link set br-sw2  up
#docker exec sw2 sh -c "echo 1 > /proc/sys/net/ipv4/ip_forward"
#docker exec sw2 iptables -I FORWARD -j ACCEPT
# docker exec sw2 sed -i '/^#*net.ipv4.ip_forward=/c\net.ipv4.ip_forward=1' /etc/sysctl.conf


### ---------- sw2 <-> sw3 ----------
ip link add veth-sw2-sw3 type veth peer name veth-sw3-sw2
ip link set veth-sw2-sw3 netns $(docker inspect -f '{{.State.Pid}}' sw2)
ip link set veth-sw3-sw2 netns $(docker inspect -f '{{.State.Pid}}' sw3)

docker exec sw2 ip link set veth-sw2-sw3 name eth_sw3
docker exec sw2 ip link set eth_sw3 up
docker exec sw2 ovs-vsctl add-port br-sw2 eth_sw3
docker exec sw2 ip addr add 10.0.0.13/30 dev eth_sw3

docker exec sw3 ip link set veth-sw3-sw2 name eth_sw2
docker exec sw3 ip link set eth_sw2 up
docker exec sw3 ovs-vsctl add-br br-sw3
docker exec sw3 ovs-vsctl add-port br-sw3 eth_sw2
docker exec sw3 ip addr add 10.0.0.14/30 dev eth_sw2
docker exec sw3 ip addr add 10.255.255.3/24 dev br-sw3  # mgmt
docker exec sw2 ip link set br-sw3 up
#docker exec sw3 sh -c "echo 1 > /proc/sys/net/ipv4/ip_forward"
#docker exec sw3 iptables -I FORWARD -j ACCEPT
# docker exec sw3 sed -i '/^#*net.ipv4.ip_forward=/c\net.ipv4.ip_forward=1' /etc/sysctl.conf
