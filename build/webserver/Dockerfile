ARG WEBSERVER_IMAGE
ARG WEBSERVER_IMAGE_TAG

FROM ${WEBSERVER_IMAGE}:${WEBSERVER_IMAGE_TAG}

ARG WEBSERVER_PORT

WORKDIR /app
COPY ./project/ ./

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE ${WEBSERVER_PORT}

CMD ["python", "app.py"]
