# make sure we load openvswitch
sudo modprobe openvswitch

# ccreate br0 interface
sudo ovs-vsctl add-br br0

# management address on br0 (also I will be using it as the 'physical link'
# between switches, to act as routers too)
sudo ip addr add 10.255.255.254/24 dev br0
ip link set br0 up

# GRE tunnet toward vm2
sudo ovs-vsctl add-port br0 gre-to-vm2 \
     -- set interface gre-to-vm2 type=gre \
     options:local_ip=192.168.241.142 \
     options:remote_ip=192.168.241.143

sudo iptables -A INPUT  -p gre -j ACCEPT
sudo iptables -A OUTPUT -p gre -j ACCEPT

# allow L2/L3 traffic through br0
sudo sysctl -w net.ipv4.ip_forward=1
sudo iptables -I FORWARD -i br0 -j ACCEPT
sudo iptables -I FORWARD -o br0 -j ACCEPT

# static route to forward traffic through the infrastructure
sudo ip route add 10.0.0.0/16 dev br0 