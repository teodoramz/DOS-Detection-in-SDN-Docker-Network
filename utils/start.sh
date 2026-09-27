#!/bin/bash
# Superseded by the per-host deployment scripts.

set -euo pipefail

echo "utils/start.sh is superseded by deploy/host1.sh and deploy/host2.sh."
echo "Run the one for this host:"
echo "  sudo DDOS_DETECTION_HOME=\$PWD ./deploy/host1.sh"
echo "  sudo DDOS_DETECTION_HOME=\$PWD ./deploy/host2.sh"
exit 1
