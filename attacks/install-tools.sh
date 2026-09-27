#!/bin/bash
set -euo pipefail
sudo apt-get update -qq
sudo apt-get install -y --no-install-recommends \
  hping3 dnsutils dnsperf slowhttptest apache2-utils python3-scapy
echo "tools installed"
