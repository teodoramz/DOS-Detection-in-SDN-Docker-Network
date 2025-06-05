#!/bin/bash

./config_br0_up.sh
./sw1-sw4.sh
./sw1-sw2-sw3.sh

./sw1-dns.sh
./sw2-proxy.sh
./sw3-services.sh
./sw4-containers.sh

./routing.sh


./ryu-sw.sh