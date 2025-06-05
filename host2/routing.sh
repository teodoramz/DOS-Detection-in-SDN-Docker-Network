# sw5 gateway
docker exec sw5 ovs-vsctl \
  --may-exist add-port br-sw5 gw5 \
  -- set interface gw5 type=internal
docker exec sw5 ip addr add 10.0.5.1/24 dev gw5
docker exec sw5 ip link set gw5 up
docker exec sw5 sysctl -w net.ipv4.ip_forward=1

# sw5 - sw1/sw2 static link via mgmt
docker exec sw5 ip route add 10.0.1.0/24 via 10.255.255.1
docker exec sw5 ip route add 10.0.2.0/24 via 10.255.255.2
docker exec sw5 ip route add 10.0.3.0/24 via 10.255.255.3
docker exec sw5 ip route add 10.0.4.0/24 via 10.255.255.4