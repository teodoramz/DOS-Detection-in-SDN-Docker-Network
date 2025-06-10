#!/usr/bin/env python3

import os
import subprocess
import time
from datetime import datetime, timedelta
import logging
import sys
import json

from minio import Minio
from kafka import KafkaProducer

INTERFACE = 'eth0' 
DURATION = 30  
TMP_DIR = '/tmp'

MINIO_ENDPOINT = '10.0.5.9:9000'
MINIO_ACCESS_KEY = 'minioadmin'
MINIO_SECRET_KEY = 'minioadmin'
MINIO_BUCKET = 'top-layer'
MINIO_SECURE = False

KAFKA_BROKER = '10.0.5.2:9092'
KAFKA_TOPIC = 'top-layer'

tlogging_format = '[%(asctime)s] %(message)s'
logging.basicConfig(format=tlogging_format, datefmt='%Y-%m-%d %H:%M:%S', level=logging.INFO)

def main():
    minio_client = Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=MINIO_SECURE
    )

    if not minio_client.bucket_exists(MINIO_BUCKET):
        minio_client.make_bucket(MINIO_BUCKET)
        logging.info(f"Created bucket '{MINIO_BUCKET}'")

    producer = KafkaProducer(
        bootstrap_servers=[KAFKA_BROKER],
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
    )

    while True:
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        filename = f'capture-{timestamp}.pcap'
        filepath = os.path.join(TMP_DIR, filename)

        logging.info(f'Starting capture: {filename} on {INTERFACE} for {DURATION}s')
        proc = subprocess.Popen(
            ['tcpdump', '-i', INTERFACE, '-s', '0', '-w', filepath],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        try:
            proc.wait(timeout=DURATION)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        logging.info(f'Capture finished: {filepath}')

        object_name = filename
        logging.info(f'Uploading to MinIO: {MINIO_BUCKET}/{object_name}')
        minio_client.fput_object(MINIO_BUCKET, object_name, filepath)

        download_url = minio_client.presigned_get_object(
            MINIO_BUCKET,
            object_name,
            expires=timedelta(days=7)
        )
        logging.info(f'Download URL: {download_url}')
        print(download_url)

        message = {
            'filename': filename,
            'download_url': download_url
        }
        producer.send(KAFKA_TOPIC, message)
        producer.flush()
        logging.info(f'Sent Kafka message to "{KAFKA_TOPIC}": {message}')

        os.remove(filepath)
        logging.info(f'Removed local file: {filepath}')


if __name__ == '__main__':
    try:
        while True:
            try:
                main()
            except Exception as e:
                logging.info(f'Error on starting dns-collector: {e}')
    except KeyboardInterrupt:
        logging.info('Interrupted by user, exiting.')
        sys.exit(0)
