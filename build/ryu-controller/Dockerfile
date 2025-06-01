FROM ubuntu:20.04

ENV DEBIAN_FRONTEND=noninteractive
ARG TZ=Etc/UTC

RUN apt-get update && apt-get install -y python3-pip git iproute2 traceroute iputils-ping dnsutils iptables

RUN pip3 install eventlet==0.25.2 dnspython==1.16.0
RUN git clone https://github.com/faucetsdn/ryu.git

WORKDIR ryu
RUN pip3 install .

#RUN pip3 install git+https://github.com/osrg/ryu.git@v4.34

EXPOSE 6633 8080

CMD ["ryu-manager", \
    "--observe-links", \
     "ryu.app.simple_switch_13", \
     "ryu.app.ofctl_rest", \
     "ryu.app.rest_topology", \
     "ryu.app.ws_topology", \
     "ryu.app.gui_topology.gui_topology"]