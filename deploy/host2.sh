#!/bin/bash
# Bring up host2: Kafka, Kafdrop, MinIO, the three ML workers and sw5.
#
#   sudo DDOS_DETECTION_HOME=$PWD ./deploy/host2.sh [--clean | --rewire] [--no-boot-unit]

set -euo pipefail

source "$(dirname "$0")/lib.sh"

usage() {
  cat <<USAGE
Usage: sudo DDOS_DETECTION_HOME=\$PWD $0 [options]

  --clean          tear down containers and OVS state first
  --rewire         start the existing containers and redo the wiring only: no
                   build, no new .env or certificates. This is what the boot
                   unit runs, and what to run by hand after a reboot.
  --no-boot-unit   do not install the systemd unit that runs --rewire at boot
                   (DDOS_BOOT_UNIT=0 does the same)
  --help           this text
USAGE
}

parse_deploy_args "$@"

require_root
require_home
require_tools

cd "$DDOS_DETECTION_HOME"

if [ -n "$REWIRE" ]; then
  [ -f .env ] || die ".env is missing; deploy once without --rewire first"
else
  generate_env

  if [ -n "$CLEAN" ]; then
    say "Tearing down"
    docker compose -f docker-compose-host2.yml down --remove-orphans || true
    remove_stale_containers kafka kafdrop minio worker1 worker2 worker3 sw5
    ./utils/cleanup.sh || true
  fi
fi

mkdir -p volumes/kafka-kraft/data volumes/minio/data
chown -R 65532:65532 volumes/minio/data || true

if [ -n "$REWIRE" ]; then
  say "Starting the existing containers"
  docker compose -f docker-compose-host2.yml up -d --no-build
else
  say "Building and starting containers"
  docker compose -f docker-compose-host2.yml up -d --build
fi

for c in sw5 kafka kafdrop minio worker1 worker2 worker3; do
  wait_for_container "$c"
done

wait_for_ovs sw5

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

[ -n "$REWIRE" ] || install_boot_unit host2

say "host2 is up"
