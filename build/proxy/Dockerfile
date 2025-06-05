ARG NGINX_IMAGE_TAG
ARG NGINX_IMAGE

FROM ${NGINX_IMAGE}:${NGINX_IMAGE_TAG}


RUN apk add --no-cache \
    iproute2 iputils \
    bind-tools      \   
    iptables curl ca-certificates \
    traceroute tcpdump

COPY nginx.conf /etc/nginx/nginx.conf
COPY ./certs/ssl/  /etc/nginx/ssl/