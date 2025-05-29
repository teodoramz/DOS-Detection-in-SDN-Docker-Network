FROM ubuntu:20.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y --no-install-recommends  \
    iproute2 traceroute iputils-ping dnsutils  iptables netbase ca-certificates && \
    rm -rf /var/lib/apt/lists/*

CMD ["sleep", "infinity"]
