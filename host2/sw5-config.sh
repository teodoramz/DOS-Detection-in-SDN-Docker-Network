# sw5
ip link add veth-sw5-br type veth peer name veth-br-sw5
sudo ovs-vsctl add-port br0 veth-br-sw5
ip link set veth-br-sw5 up

pid=$(docker inspect -f '{{.State.Pid}}' sw5)
ip link set veth-sw5-br netns $pid
docker exec sw5 ip link set veth-sw5-br name eth_br0
docker exec sw5 ip link set eth_br0 up

docker exec sw5 ovs-vsctl add-br br-sw5
docker exec sw5 ovs-vsctl add-port br-sw5 eth_br0
docker exec sw5 ip addr add 10.255.255.5/24 dev br-sw5 #mgmt
docker exec sw5 ip link set br-sw5 up