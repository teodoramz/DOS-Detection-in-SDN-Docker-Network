ARG MINIO_IMAGE=chainguard/minio
ARG MINIO_IMAGE_TAG=latest

FROM ${MINIO_IMAGE}:${MINIO_IMAGE_TAG}

ARG MINIO_SERVER_PORT=9000
ARG MINIO_WEBUI_PORT=9001

EXPOSE ${MINIO_SERVER_PORT} ${MINIO_WEBUI_PORT}

# The image is distroless, so there is no entrypoint script. MinIO binds
# 0.0.0.0 and accepts on eth0 once the topology scripts attach it.
ENTRYPOINT ["/usr/bin/minio"]
CMD ["server", "/data", "--console-address", ":9001"]
