#!/bin/bash

if [ "$#" -eq 0 ]; then
  echo "Usage: $0 <path_to_openssl_cnf_folder>"
  echo "Example: $0 /path/to/folder or $0 ./folder"
  exit 1
fi

BASE_PATH="$1"

ABS_PATH=$(realpath "$BASE_PATH")

SSL_DIR="$ABS_PATH/ssl"

if [ ! -d "$SSL_DIR" ]; then
  mkdir -p "$SSL_DIR"
fi

openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout "$SSL_DIR/cyberstuff.key" -out "$SSL_DIR/cyberstuff.crt" \
  -config "$ABS_PATH/openssl.cnf"
