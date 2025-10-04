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

echo "Configuring services containers and their network interfaces..."
./6.sw3-services.sh

echo "Configuring connection of collectors to OpenvSwitch 4..."
./7.sw4-collectors.sh

echo "Configuring the routing between switches..."
./8.routing.sh

echo "Configuring Ryu controller..."
./9.ryu-sw.sh