FROM ubuntu:20.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    openvswitch-switch \
    openvswitch-common \
    iproute2 \
    && rm -rf /var/lib/apt/lists/*

CMD ["/bin/bash"]
