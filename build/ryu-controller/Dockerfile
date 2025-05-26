FROM ubuntu:20.04

RUN apt-get update && apt-get install -y python3-pip iproute2 iputils-ping dnsutils

RUN pip3 install ryu eventlet==0.25.2 dnspython==1.16.0

EXPOSE 6633

CMD ["ryu-manager", "ryu.app.simple_switch_13"]
