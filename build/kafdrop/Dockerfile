ARG KAFDROP_IMAGE_TAG
ARG KAFDROP_IMAGE

FROM ${KAFDROP_IMAGE}:${KAFDROP_IMAGE_TAG}

USER root
RUN apt-get update && \
    apt-get install -y --no-install-recommends iproute2 

COPY ./wait-for-eth0.sh /wait-for-eth0.sh

ENTRYPOINT ["sh","/wait-for-eth0.sh","10.0.5.6","/kafdrop.sh"]