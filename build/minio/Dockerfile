ARG MINIO_IMAGE
ARG MINIO_IMAGE_TAG

FROM registry.access.redhat.com/ubi9:9.6 AS toolbox

RUN dnf -y install iproute && dnf clean all

RUN mkdir -p /opt/ip && \
    cp /usr/sbin/ip /opt/ip/ && \
    ldd /usr/sbin/ip | awk '{print $3}' | grep '^/' | \
    xargs -I{} cp {} /opt/ip/

FROM ${MINIO_IMAGE}:${MINIO_IMAGE_TAG}

ARG MINIO_SERVER_PORT
ARG MINIO_WEBUI_PORT

COPY --from=toolbox /opt/ip /opt/ip
ENV PATH="/opt/ip:${PATH}" \
    LD_LIBRARY_PATH="/opt/ip"


COPY wait-for-eth0.sh /wait-for-eth0.sh
RUN chmod +x /wait-for-eth0.sh 

RUN mkdir -p /data && chown -R 1000:1000 /data
USER 1000:1000
EXPOSE ${MINIO_SERVER_PORT} ${MINIO_WEBUI_PORT}

ENTRYPOINT ["sh","/wait-for-eth0.sh"]
