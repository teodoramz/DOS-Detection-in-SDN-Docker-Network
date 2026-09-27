ARG WEBSERVER_IMAGE=python
ARG WEBSERVER_IMAGE_TAG=3.12-slim

FROM ${WEBSERVER_IMAGE}:${WEBSERVER_IMAGE_TAG}

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update -qq && \
    apt-get install -y --no-install-recommends \
        tcpdump iproute2 iputils-ping traceroute netcat-openbsd && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app
RUN pip install --no-cache-dir minio==7.2.10 kafka-python==2.2.15

COPY collector.py /app/
COPY entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/entrypoint.sh

ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["entrypoint.sh"]
