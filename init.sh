#sudo apt update
#sudo apt install -y openvswitch-switch iproute2 docker.io
#sudo modprobe openvswitch
sudo ovs-vsctl add-br br0

# tunel GRE spre host-ul 2
#sudo ovs-vsctl add-port br0 gre-to-h2 \
#      -- set interface gre-to-h2 type=gre \
#      options:remote_ip=192.168.35.36 options:local_ip=192.168.35.35

# adresă „management /24” pe br0
#sudo ip addr add 10.255.255.254/24 dev br0
#sudo ip link set br0 up

# permit forward-ul L2/L3 prin br0
#sudo sysctl -w net.ipv4.ip_forward=1
#sudo iptables -I FORWARD -i br0 -j ACCEPT
#sudo iptables -I FORWARD -o br0 -j ACCEPT
