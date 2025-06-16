#!/bin/sh
set -e
IF=eth0
IP=10.0.1.6

echo "Waiting for $IF to have an IP..."
while ! ip -o addr show "$IF" | grep -q "$IP/"; do
  sleep 0.2
done
echo "starting service"
python -u /app/dns-collector.py

#tail -f /dev/null