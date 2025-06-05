ARG BIND9_IMAGE_TAG
ARG BIND9_IMAGE

FROM ${BIND9_IMAGE}:${BIND9_IMAGE_TAG}

RUN apk add --no-cache \
    iproute2      \  
    iputils       \  
    traceroute    \
    tcpdump

COPY named.conf /etc/bind/named.conf
COPY db.cyberstuff.local /etc/bind/db.cyberstuff.local
COPY db.cyberstuff.local /var/cache/bind/db.cyberstuff.local


CMD [ "-g" ]