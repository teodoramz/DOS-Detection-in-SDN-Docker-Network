# sw1 gateway
docker exec sw1 ovs-vsctl \
  --may-exist add-port br-sw1 gw1 \
  -- set interface gw1 type=internal
docker exec sw1 ip addr add 10.0.1.1/24 dev gw1
docker exec sw1 ip link set gw1 up
docker exec sw1 sysctl -w net.ipv4.ip_forward=1

# sw2 gateway
docker exec sw2 ovs-vsctl \
  --may-exist add-port br-sw2 gw2 \
  -- set interface gw2 type=internal
docker exec sw2 ip addr add 10.0.2.1/24 dev gw2
docker exec sw2 ip link set gw2 up
docker exec sw2 sysctl -w net.ipv4.ip_forward=1

# sw3 gateway
docker exec sw3 ovs-vsctl \
  --may-exist add-port br-sw3 gw3 \
  -- set interface gw3 type=internal
docker exec sw3 ip addr add 10.0.3.1/24 dev gw3
docker exec sw3 ip link set gw3 up
docker exec sw3 sysctl -w net.ipv4.ip_forward=1



# sw1 - sw2/sw3 static link via mgmt
docker exec sw1 ip route add 10.0.2.0/24 via 10.255.255.2
docker exec sw1 ip route add 10.0.3.0/24 via 10.255.255.3

# sw2 - sw1/sw3 static link via mgmt
docker exec sw2 ip route add 10.0.1.0/24 via 10.255.255.1
docker exec sw2 ip route add 10.0.3.0/24 via 10.255.255.3

# sw3 - sw1/sw2 static link via mgmt
docker exec sw3 ip route add 10.0.1.0/24 via 10.255.255.1
docker exec sw3 ip route add 10.0.2.0/24 via 10.255.255.2
