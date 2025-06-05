FROM ubuntu:20.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y --no-install-recommends  \
    iproute2 iputils-ping dnsutils  iptables netbase vim curl ca-certificates \
    && apt-get update && apt-get install -y traceroute tcpdump python3 python3-pip python3-venv && \
    pip3 install --no-cache-dir kafka-python

CMD ["sleep", "infinity"]
