ARG WEBSERVER_IMAGE=python
ARG WEBSERVER_IMAGE_TAG=3.12-slim

FROM ${WEBSERVER_IMAGE}:${WEBSERVER_IMAGE_TAG}

ENV DEBIAN_FRONTEND=noninteractive
ENV CFM_HOME=/opt/cicflowmeter

RUN apt-get update -qq && \
    apt-get install -y --no-install-recommends \
        default-jre-headless libpcap0.8 libpcap-dev tcpdump \
        iproute2 iputils-ping ca-certificates && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

COPY cicflowmeter ${CFM_HOME}

WORKDIR /app
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY ddos_worker /app/ddos_worker
COPY models /app/models
COPY entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/entrypoint.sh

ENV PYTHONUNBUFFERED=1 JAVA_OPTS="-Xms256m -Xmx1g"

ENTRYPOINT ["entrypoint.sh"]
