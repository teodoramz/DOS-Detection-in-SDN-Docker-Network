ARG WEBSERVER_IMAGE
ARG WEBSERVER_IMAGE_TAG

FROM ${WEBSERVER_IMAGE}:${WEBSERVER_IMAGE_TAG}

RUN apt-get update -qq && \
    DEBIAN_FRONTEND=noninteractive \
    apt-get install -y --no-install-recommends \
    default-jre-headless nano vim\
    tcpdump iproute2 traceroute iputils-ping netcat-openbsd && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY dns-collector.py /app/

RUN pip install --no-cache-dir minio kafka-python

COPY entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/entrypoint.sh

ENTRYPOINT ["entrypoint.sh"]
