#!/bin/bash

./config_br0_up.sh
./sw5-config.sh
./sw5-containers.sh

./routing.sh
