#!/bin/bash
# Bring up host2: Kafka, Kafdrop, MinIO, the three ML workers and sw5.
#
#   sudo DDOS_DETECTION_HOME=$PWD ./deploy/host2.sh [--clean]

set -euo pipefail

source "$(dirname "$0")/lib.sh"

require_root
require_home
require_tools

cd "$DDOS_DETECTION_HOME"

generate_env

if [ "${1:-}" = "--clean" ]; then
  say "Tearing down"
  docker compose -f docker-compose-host2.yml down --remove-orphans || true
  ./utils/cleanup.sh || true
fi

mkdir -p volumes/kafka-kraft/data volumes/minio/data
chown -R 1000:1000 volumes/minio/data || true

say "Building and starting containers"
docker compose -f docker-compose-host2.yml up -d --build

for c in sw5 kafka kafdrop minio worker1 worker2 worker3; do
  wait_for_container "$c"
done

say "Wiring the network"
cd host2
./1.config_br0.sh
./2.sw5-config.sh
./3.sw5-containers.sh
./4.connect_containers.sh
cd ..

say "Health check"
docker ps --format '  {{.Names}}\t{{.Status}}'
echo
for w in worker1 worker2 worker3; do
  printf '  %s: %s\n' "$w" "$(docker logs --tail 1 "$w" 2>&1 | tail -1)"
done

say "host2 is up"
