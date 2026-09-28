ARG WEBSERVER_IMAGE=python
ARG WEBSERVER_IMAGE_TAG=3.12-slim

FROM ${WEBSERVER_IMAGE}:${WEBSERVER_IMAGE_TAG}

ENV DEBIAN_FRONTEND=noninteractive
ENV CFM_HOME=/opt/cicflowmeter

RUN apt-get update -qq && \
    apt-get install -y --no-install-recommends \
        default-jre-headless libpcap0.8 tcpdump \
        iproute2 iputils-ping wget ca-certificates && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

RUN mkdir -p ${CFM_HOME} && \
    wget -qO- "https://codeberg.org/iortega/TCPDUMP_and_CICFlowMeter/archive/v0.2.1.tar.gz" \
      | tar zxf - --strip-components=1 -C ${CFM_HOME} && \
    chmod +x ${CFM_HOME}/convert_pcap_csv.sh ${CFM_HOME}/capture_interface_pcap.sh && \
    mkdir -p ${CFM_HOME}/csv ${CFM_HOME}/pcap ${CFM_HOME}/logs

WORKDIR /app
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY ddos_worker /app/ddos_worker
COPY models /app/models
COPY entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/entrypoint.sh

ENV PYTHONUNBUFFERED=1 JAVA_OPTS="-Xms256m -Xmx1g"

ENTRYPOINT ["entrypoint.sh"]
