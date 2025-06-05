# Kafka
ip link add veth-kafka-srv type veth peer name veth-sw5-kafka
ip link set veth-kafka-srv netns $(docker inspect -f '{{.State.Pid}}' kafka)
ip link set veth-sw5-kafka netns $(docker inspect -f '{{.State.Pid}}' sw5)

docker exec kafka ip link set veth-kafka-srv name eth0
docker exec kafka ip addr add 10.0.5.2/24 dev eth0
docker exec kafka ip addr add 10.255.255.99/24 dev eth0
docker exec kafka ip link set eth0 up
docker exec kafka ip route add default via 10.0.5.1

docker exec sw5 ip link set veth-sw5-kafka name eth_kafka
docker exec sw5 ovs-vsctl add-port br-sw5 eth_kafka
docker exec sw5 ip link set eth_kafka up

# Kafdrop
ip link add veth-kafdrop-srv type veth peer name veth-sw5-kafdrop
ip link set veth-kafdrop-srv netns $(docker inspect -f '{{.State.Pid}}' kafdrop)
ip link set veth-sw5-kafdrop netns $(docker inspect -f '{{.State.Pid}}' sw5)

docker exec kafdrop ip link set veth-kafdrop-srv name eth0
docker exec kafdrop ip addr add 10.0.5.6/24 dev eth0
docker exec kafdrop ip addr add 10.255.255.100/24 dev eth0
docker exec kafdrop ip link set eth0 up
docker exec kafdrop ip route add default via 10.0.5.1

docker exec sw5 ip link set veth-sw5-kafdrop name eth_kafdrop
docker exec sw5 ovs-vsctl add-port br-sw5 eth_kafdrop
docker exec sw5 ip link set eth_kafdrop up

# worker1
ip link add veth-worker1-srv type veth peer name veth-sw5-worker1
ip link set veth-worker1-srv netns $(docker inspect -f '{{.State.Pid}}' worker1)
ip link set veth-sw5-worker1 netns $(docker inspect -f '{{.State.Pid}}' sw5)

docker exec worker1 ip link set veth-worker1-srv name eth0
docker exec worker1 ip addr add 10.0.5.11/24 dev eth0
docker exec worker1 ip addr add 10.255.255.51/24 dev eth0
docker exec worker1 ip link set eth0 up
docker exec worker1 ip route add default via 10.0.5.1

docker exec sw5 ip link set veth-sw5-worker1 name eth_worker1
docker exec sw5 ovs-vsctl add-port br-sw5 eth_worker1
docker exec sw5 ip link set eth_worker1 up

# worker2
ip link add veth-worker2-srv type veth peer name veth-sw5-worker2
ip link set veth-worker2-srv netns $(docker inspect -f '{{.State.Pid}}' worker2)
ip link set veth-sw5-worker2 netns $(docker inspect -f '{{.State.Pid}}' sw5)

docker exec worker2 ip link set veth-worker2-srv name eth0
docker exec worker2 ip addr add 10.0.5.12/24 dev eth0
docker exec worker2 ip addr add 10.255.255.52/24 dev eth0
docker exec worker2 ip link set eth0 up
docker exec worker2 ip route add default via 10.0.5.1

docker exec sw5 ip link set veth-sw5-worker2 name eth_worker2
docker exec sw5 ovs-vsctl add-port br-sw5 eth_worker2
docker exec sw5 ip link set eth_worker2 up

# worker3
ip link add veth-worker3-srv type veth peer name veth-sw5-worker3
ip link set veth-worker3-srv netns $(docker inspect -f '{{.State.Pid}}' worker3)
ip link set veth-sw5-worker3 netns $(docker inspect -f '{{.State.Pid}}' sw5)

docker exec worker3 ip link set veth-worker3-srv name eth0
docker exec worker3 ip addr add 10.0.5.13/24 dev eth0
docker exec worker3 ip addr add 10.255.255.53/24 dev eth0
docker exec worker3 ip link set eth0 up
docker exec worker3 ip route add default via 10.0.5.1

docker exec sw5 ip link set veth-sw5-worker3 name eth_worker3
docker exec sw5 ovs-vsctl add-port br-sw5 eth_worker3
docker exec sw5 ip link set eth_worker3 up