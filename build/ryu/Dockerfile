ARG SDN_IMAGE
ARG SDN_IMAGE_TAG

FROM ${SDN_IMAGE}:${SDN_IMAGE_TAG}

ARG SDN_PORT

WORKDIR /
COPY ./files/ ./

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE ${SDN_PORT}

CMD ["ryu-manager", "--ofp-tcp-listen-port", "6633", "/ddos_blocker.py", "ryu.app.ofctl_rest"]
