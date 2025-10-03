sudo iptables -F
sudo iptables -X
sudo iptables -P INPUT  ACCEPT
sudo iptables -P FORWARD ACCEPT
sudo iptables -P OUTPUT ACCEPT

ip link set br0 down