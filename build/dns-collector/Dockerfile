ARG WEBSERVER_IMAGE
ARG WEBSERVER_IMAGE_TAG

FROM ${WEBSERVER_IMAGE}:${WEBSERVER_IMAGE_TAG}

RUN apt-get update -qq && \
    DEBIAN_FRONTEND=noninteractive \
    apt-get install -y --no-install-recommends \
    default-jre-headless nano vim\
    tcpdump iproute2 iputils-ping && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# -- Copy application code
WORKDIR /app
COPY dns-collector.py /app/
COPY dnsmodel.joblib /app/

# -- Python deps
RUN pip install --no-cache-dir scapy pandas joblib cicflowmeter imbalanced-learn


COPY entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/entrypoint.sh

# -- Default command (override at runtime if you need extra flags)
ENTRYPOINT ["entrypoint.sh"]
