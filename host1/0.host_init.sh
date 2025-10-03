#!/bin/bash

echo "Configuring openvswitch br0 and host1 network interfaces and iptables rules..."
./1.config_br0.sh

echo "Configuring OpenvSwitch 1, 2, 3 and 4 and their network interfaces..."
./2.sw1-sw4.sh
./3.sw1-sw2-sw3.sh

echo "Configuring DNS and DNS collector containers and their network interfaces..."
./4.sw1-dns.sh

echo "Configuring Proxy and Proxy collector container and their network interfaces..."
./5.sw2-proxy.sh

./6.sw3-services.sh

./7.sw4-containers.sh

./8.routing.sh


./9.ryu-sw.sh