#!/bin/sh
set -e
IF=eth0
IP=10.0.5.9

echo "Waiting for $IF to have an IP..."
while ! ip -o addr show "$IF"; do
  sleep 0.2
done
echo "starting service"

minio server /data --console-address ":9001"
