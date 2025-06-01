FROM ubuntu:20.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y --no-install-recommends  \
    iproute2 iputils-ping dnsutils  iptables netbase ca-certificates \
    && apt-get update && apt-get install -y traceroute

CMD ["sleep", "infinity"]
