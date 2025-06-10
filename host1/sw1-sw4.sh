# sw1
ip link add veth-sw1-br type veth peer name veth-br-sw1
sudo ovs-vsctl add-port br0 veth-br-sw1
ip link set veth-br-sw1 up

pid=$(docker inspect -f '{{.State.Pid}}' sw1)
ip link set veth-sw1-br netns $pid
docker exec sw1 ip link set veth-sw1-br name eth_br0
docker exec sw1 ip link set eth_br0 up
docker exec sw1 ip link set eth_br0  mtu 1400 

docker exec sw1 ovs-vsctl add-br br-sw1
docker exec sw1 ovs-vsctl add-port br-sw1 eth_br0
docker exec sw1 ip addr add 10.255.255.1/24 dev br-sw1 #mgmt
docker exec sw1 ip link set br-sw1 up
docker exec sw1 ip link set br-sw1  mtu 1400 
#docker exec sw1 sh -c "echo 1 > /proc/sys/net/ipv4/ip_forward"
#docker exec sw1 iptables -I FORWARD -j ACCEPT
# docker exec sw1 sed -i '/^#*net.ipv4.ip_forward=/c\net.ipv4.ip_forward=1' /etc/sysctl.conf


# sw4
ip link add veth-sw4-br type veth peer name veth-br-sw4
sudo ovs-vsctl add-port br0 veth-br-sw4
ip link set veth-br-sw4 up

pid=$(docker inspect -f '{{.State.Pid}}' sw4)
ip link set veth-sw4-br netns $pid
docker exec sw4 ip link set veth-sw4-br name eth_br0
docker exec sw4 ip link set eth_br0 up
docker exec sw4 ip link set eth_br0   mtu 1400 

docker exec sw4 ovs-vsctl add-br br-sw4
docker exec sw4 ovs-vsctl add-port br-sw4 eth_br0
docker exec sw4 ip addr add 10.255.255.4/24 dev br-sw4 #mgmt
docker exec sw4 ip link set br-sw4  up
docker exec sw4 ip link set br-sw4  mtu 1400 
#docker exec sw4 sh -c "echo 1 > /proc/sys/net/ipv4/ip_forward"
#docker exec sw4 iptables -I FORWARD -j ACCEPT
# docker exec sw4 sed -i '/^#*net.ipv4.ip_forward=/c\net.ipv4.ip_forward=1' /etc/sysctl.conf
