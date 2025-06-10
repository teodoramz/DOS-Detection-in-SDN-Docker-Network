# Kafka
ip link add veth-kafka-srv type veth peer name veth-sw5-kafka
ip link set veth-kafka-srv netns $(docker inspect -f '{{.State.Pid}}' kafka)
ip link set veth-sw5-kafka netns $(docker inspect -f '{{.State.Pid}}' sw5)

docker exec kafka ip link set veth-kafka-srv name eth0
docker exec kafka ip addr add 10.0.5.2/24 dev eth0
docker exec kafka ip addr add 10.255.255.99/24 dev eth0
docker exec kafka ip link set eth0 up
docker exec kafka ip link set eth0  mtu 1400 
docker exec kafka ip route add default via 10.0.5.1

docker exec sw5 ip link set veth-sw5-kafka name eth_kafka
docker exec sw5 ovs-vsctl add-port br-sw5 eth_kafka
docker exec sw5 ip link set eth_kafka up
docker exec sw5 ip link set eth_kafka  mtu 1400 

# Kafdrop
ip link add veth-kfp-srv type veth peer name veth-sw5-kfp
ip link set veth-kfp-srv netns $(docker inspect -f '{{.State.Pid}}' kafdrop)
ip link set veth-sw5-kfp netns $(docker inspect -f '{{.State.Pid}}' sw5)

docker exec kafdrop ip link set veth-kfp-srv name eth0
docker exec kafdrop ip addr add 10.0.5.6/24 dev eth0
docker exec kafdrop ip addr add 10.255.255.100/24 dev eth0
docker exec kafdrop ip link set eth0 up
docker exec kafdrop ip link set eth0  mtu 1400 
docker exec kafdrop ip route add default via 10.0.5.1

docker exec sw5 ip link set veth-sw5-kfp name eth_kfp
docker exec sw5 ovs-vsctl add-port br-sw5 eth_kfp
docker exec sw5 ip link set eth_kfp up
docker exec sw5 ip link set eth_kfp  mtu 1400 

# minio
ip link add veth-s3-srv type veth peer name veth-sw5-s3
ip link set veth-s3-srv netns $(docker inspect -f '{{.State.Pid}}' minio)
ip link set veth-sw5-s3 netns $(docker inspect -f '{{.State.Pid}}' sw5)

docker exec minio ip link set veth-s3-srv name eth0
docker exec minio ip addr add 10.0.5.9/24 dev eth0
docker exec minio ip addr add 10.255.255.101/24 dev eth0
docker exec minio ip link set eth0 up
docker exec minio ip link set eth0  mtu 1400 
docker exec minio ip route add default via 10.0.5.1

docker exec sw5 ip link set veth-sw5-s3 name eth_s3
docker exec sw5 ovs-vsctl add-port br-sw5 eth_s3
docker exec sw5 ip link set eth_s3 up
docker exec sw5 ip link set eth_s3  mtu 1400 

# worker1
ip link add veth-w1-srv type veth peer name veth-sw5-w1
ip link set veth-w1-srv netns $(docker inspect -f '{{.State.Pid}}' worker1)
ip link set veth-sw5-w1 netns $(docker inspect -f '{{.State.Pid}}' sw5)

docker exec worker1 ip link set veth-w1-srv name eth0
docker exec worker1 ip addr add 10.0.5.11/24 dev eth0
docker exec worker1 ip addr add 10.255.255.51/24 dev eth0
docker exec worker1 ip link set eth0 up
docker exec worker1 ip link set eth0  mtu 1400 
docker exec worker1 ip route add default via 10.0.5.1

docker exec sw5 ip link set veth-sw5-w1 name eth_w1
docker exec sw5 ovs-vsctl add-port br-sw5 eth_w1
docker exec sw5 ip link set eth_w1 up
docker exec sw5 ip link set eth_w1  mtu 1400

# worker2
ip link add veth-w2-srv type veth peer name veth-sw5-w2
ip link set veth-w2-srv netns $(docker inspect -f '{{.State.Pid}}' worker2)
ip link set veth-sw5-w2 netns $(docker inspect -f '{{.State.Pid}}' sw5)

docker exec worker2 ip link set veth-w2-srv name eth0
docker exec worker2 ip addr add 10.0.5.12/24 dev eth0
docker exec worker2 ip addr add 10.255.255.52/24 dev eth0
docker exec worker2 ip link set eth0 up
docker exec worker2 ip link set eth0  mtu 1400
docker exec worker2 ip route add default via 10.0.5.1

docker exec sw5 ip link set veth-sw5-w2 name eth_w2
docker exec sw5 ovs-vsctl add-port br-sw5 eth_w2
docker exec sw5 ip link set eth_w2 up
docker exec sw5 ip link set eth_w2  mtu 1400

# worker3
ip link add veth-w3-srv type veth peer name veth-sw5-w3
ip link set veth-w3-srv netns $(docker inspect -f '{{.State.Pid}}' worker3)
ip link set veth-sw5-w3 netns $(docker inspect -f '{{.State.Pid}}' sw5)

docker exec worker3 ip link set veth-w3-srv name eth0
docker exec worker3 ip addr add 10.0.5.13/24 dev eth0
docker exec worker3 ip addr add 10.255.255.53/24 dev eth0
docker exec worker3 ip link set eth0 up
docker exec worker3 ip link set eth0  mtu 1400
docker exec worker3 ip route add default via 10.0.5.1

docker exec sw5 ip link set veth-sw5-w3 name eth_w3
docker exec sw5 ovs-vsctl add-port br-sw5 eth_w3
docker exec sw5 ip link set eth_w3 up
docker exec sw5 ip link set eth_w3  mtu 1400