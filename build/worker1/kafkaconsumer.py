#!/usr/bin/env python3

import os
import sys
import json
import logging
import requests
from kafka import KafkaConsumer


KAFKA_BROKER = '10.0.5.2:9092' 
KAFKA_TOPIC = 'top-layer'
TMP_DIR = '/tmp'

tlogging_format = '[%(asctime)s] %(levelname)s %(message)s'
logging.basicConfig(format=tlogging_format, datefmt='%Y-%m-%d %H:%M:%S', level=logging.INFO)


def download_file(url: str, dest_path: str) -> bool:
    try:
        with requests.get(url, stream=True, timeout=60) as r:
            r.raise_for_status()
            with open(dest_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
        return True
    except Exception as e:
        logging.error(f"Eroare la descărcare {url}: {e}")
        return False


def main():

    os.makedirs(TMP_DIR, exist_ok=True)

    consumer = KafkaConsumer(
        KAFKA_TOPIC,
        bootstrap_servers=[KAFKA_BROKER],
        auto_offset_reset='earliest',
        enable_auto_commit=True,
        value_deserializer=lambda m: json.loads(m.decode('utf-8'))
    )
    logging.info(f"Ascult Kafka pe {KAFKA_BROKER}, topic {KAFKA_TOPIC}")

    for message in consumer:
        payload = message.value
        filename = payload.get('filename')
        url = payload.get('download_url')
        if not filename or not url:
            logging.warning(f"Mesaj invalid, lipsește filename/url: {payload}")
            continue

        dest = os.path.join(TMP_DIR, filename)
        logging.info(f"Încep descărcare: {filename} din {url}")
        if download_file(url, dest):
            logging.info(f"Salvat {filename} în {dest}")
        else:
            logging.error(f"Descărcare eșuată pentru {filename}")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logging.info('Oprit de utilizator, exit.')
        sys.exit(0)