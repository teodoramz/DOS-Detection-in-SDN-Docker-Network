ARG WEBSERVER_IMAGE
ARG WEBSERVER_IMAGE_TAG

FROM ${WEBSERVER_IMAGE}:${WEBSERVER_IMAGE_TAG}

ARG WEBSERVER_PORT

WORKDIR /app
COPY ./project/ ./

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y --no-install-recommends iproute2 iputils-ping

RUN pip install --no-cache-dir -r requirements.txt

COPY entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/entrypoint.sh

EXPOSE ${WEBSERVER_PORT}

ENTRYPOINT ["entrypoint.sh"]
