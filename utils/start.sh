#!/bin/bash

#########
# Starting script with
# sudo DDOS_DETECTION_HOME=$DDOS_DETECTION_HOME ./utils/start.sh 
########

# run this script with sudo
if [ "$EUID" -ne 0 ]; then
    echo "You must run this script with sudo."
    exit 1
fi

# Check if DDOS_DETECTION_HOME is set
if [ -z "$DDOS_DETECTION_HOME" ]; then
    echo "DDOS_DETECTION_HOME environment variable is not set. Please set the environment variable."
    exit 1
fi

# Ensure it is exported, so it is available to any child processes.
export DDOS_DETECTION_HOME="$DDOS_DETECTION_HOME"

# Generate SSL certificates
echo "Generating SSL certificates..."
$DDOS_DETECTION_HOME/build/certs/generate-certs.sh "$DDOS_DETECTION_HOME/build/certs/ssl"

# copy the certificates to the appropriate location
sudo cp "$DDOS_DETECTION_HOME/build/certs/ssl/cyberstuff.crt" "$DDOS_DETECTION_HOME/build/proxy/certs/ssl/cyberstuff.crt"
sudo cp "$DDOS_DETECTION_HOME/build/certs/ssl/cyberstuff.key" "$DDOS_DETECTION_HOME/build/proxy/certs/ssl/cyberstuff.key"