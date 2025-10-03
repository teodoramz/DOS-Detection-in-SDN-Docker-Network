#!/bin/bash

echo "Configuring openvswitch br0 and host2 network interfaces and iptables rules..."
./1.config_br0.sh

echo "Configuring OpenvSwitch 5 and its network interfaces..."
./2.sw5-config.sh

echo "Configuring containers network interfaces..."
./3.sw5-containers.sh

echo "Connect containers to OpenvSwitch 5..."
./4.connect_containers.sh

echo "Finnished host2 network configuration."
