#!/bin/bash

sudo apt update && sudo apt install -y openvswitch-switch openvswitch-common

sudo wget -O /usr/bin/ovs-docker https://raw.githubusercontent.com/openvswitch/ovs/master/utilities/ovs-docker&#8203;:contentReference[oaicite:3]{index=3}
sudo chmod +x /usr/bin/ovs-docker

#sudo ovs-vsctl add-br br0
#sudo ip addr add 172.16.100.1/24 dev br0
#sudo ip link set br0 up


#sudo ovs-vsctl add-port br0 eth0

#sudo ovs-vsctl set-fail-mode br0 secure
