#!/bin/bash
# Bring up host1: the three service layers, their collectors, four switches and
# the Ryu controller.
#
#   sudo DDOS_DETECTION_HOME=$PWD ./deploy/host1.sh [--clean]

set -euo pipefail

source "$(dirname "$0")/lib.sh"

require_root
require_home
require_tools

cd "$DDOS_DETECTION_HOME"

generate_env

if [ "${1:-}" = "--clean" ]; then
  say "Tearing down"
  docker compose -f docker-compose-host1.yml down --remove-orphans || true
  ./utils/cleanup.sh || true
fi

say "Generating certificates"
./build/certs/generate-certs.sh "$DDOS_DETECTION_HOME/build/certs/ssl"
install -D -m 644 build/certs/ssl/cyberstuff.crt build/proxy/certs/ssl/cyberstuff.crt
install -D -m 600 build/certs/ssl/cyberstuff.key build/proxy/certs/ssl/cyberstuff.key

say "Building and starting containers"
docker compose -f docker-compose-host1.yml up -d --build

for c in sw1 sw2 sw3 sw4 dns dns_collector proxy proxy_collector webserver web_collector; do
  wait_for_container "$c"
done

say "Wiring the network"
cd host1
./1.config_br0.sh
./2.sw1-sw4.sh
./3.sw1-sw2-sw3.sh
./4.sw1-dns.sh
./5.sw2-proxy.sh
./6.sw3-services.sh
./7.sw4-collectors.sh
./8.routing.sh
./9.ryu-sw.sh
cd ..

say "Health check"
docker ps --format '  {{.Names}}\t{{.Status}}'
echo
for n in 1 2 3 4; do
  printf '  sw%s controller: %s\n' "$n" \
    "$(docker exec "sw$n" ovs-vsctl get-controller "br-sw$n" 2>/dev/null || echo unset)"
done
printf '  ryu status: '
curl -sf "http://127.0.0.1:8080/ddos/status" || echo "not answering yet"
echo

say "host1 is up"
