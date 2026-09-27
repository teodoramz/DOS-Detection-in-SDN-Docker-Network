ARG SDN_IMAGE=python
ARG SDN_IMAGE_TAG=3.9-slim

FROM ${SDN_IMAGE}:${SDN_IMAGE_TAG}

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update -qq && \
    apt-get install -y --no-install-recommends \
        gcc python3-dev iproute2 iputils-ping curl && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt /app/

# ryu 4.34 has a legacy setup.py that newer setuptools cannot build metadata for.
RUN pip install --no-cache-dir "setuptools<58" wheel && \
    pip install --no-cache-dir -r requirements.txt

COPY ddos_ryu /app/ddos_ryu

ENV PYTHONUNBUFFERED=1 PYTHONPATH=/app

EXPOSE 6633 8080

CMD ["ryu-manager", "--ofp-tcp-listen-port", "6633", "--wsapi-port", "8080", \
     "ddos_ryu.ddos_blocker", "ryu.app.ofctl_rest"]
