ARG KAFKA_IMAGE=confluentinc/cp-kafka
ARG KAFKA_IMAGE_TAG

FROM ${KAFKA_IMAGE}:${KAFKA_IMAGE_TAG}

USER root                             
RUN mkdir -p /var/cache/yum/lock && \
    microdnf --disablerepo=temurin-jdk install -y  net-tools iproute


COPY ./wait-for-eth0.sh /wait-for-eth0.sh
ENTRYPOINT ["sh","/wait-for-eth0.sh","10.0.5.2","/etc/confluent/docker/run"]
