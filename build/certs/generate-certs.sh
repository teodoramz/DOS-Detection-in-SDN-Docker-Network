#!/bin/bash


if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
  echo "Usage: $0 <path_to_openssl_cnf_folder> [output_directory]"
  echo "Example: $0 /path/to/folder or $0 /path/to/folder /path/to/output"
  exit 1
fi

BASE_PATH="$1"
ABS_PATH=$(realpath "$BASE_PATH")

# handle output dir safely
if [ "$#" -eq 2 ]; then
  OUTPUT_DIR="$2"
else
  OUTPUT_DIR="$ABS_PATH"
fi

# create directory *before* resolving full path
mkdir -p "$OUTPUT_DIR"
OUTPUT_DIR=$(realpath "$OUTPUT_DIR")

echo ""
echo "Choose certificate generation method:"
echo "1) Use predefined openssl.cnf (from ${DDOS_DETECTION_HOME}/startup/templates/openssl.cnf)"
echo "2) Enter certificate details manually"
read -rp "Enter your choice [1/2]: " choice

if [ "$choice" = "1" ]; then
  PREDEF_CNF="$DDOS_DETECTION_HOME/startup/templates/openssl.cnf.j2"

  echo "Using predefined OpenSSL configuration file: $PREDEF_CNF"
  if [ ! -f "$PREDEF_CNF" ]; then
    echo "Error: $PREDEF_CNF not found!"
    exit 1
  fi

  # copy and rename so OpenSSL can read it (ignore .j2 extension)
  cp "$PREDEF_CNF" "$OUTPUT_DIR/openssl.cnf"

  openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout "$OUTPUT_DIR/cyberstuff.key" \
    -out "$OUTPUT_DIR/cyberstuff.crt" \
    -config "$OUTPUT_DIR/openssl.cnf"

elif [ "$choice" = "2" ]; then
  echo "Generating certificate with manual input..."
  openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout "$OUTPUT_DIR/cyberstuff.key" \
    -out "$OUTPUT_DIR/cyberstuff.crt"
else
  echo "Invalid choice. Exiting."
  exit 1
fi

sudo chmod 600 "$OUTPUT_DIR/cyberstuff.key"
sudo chmod 644 "$OUTPUT_DIR/cyberstuff.crt"

echo ""
echo "Certificate and key created successfully in: $OUTPUT_DIR"
echo ""
