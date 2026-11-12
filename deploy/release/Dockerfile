ARG LOCAL_BASE_IMAGE=market-regulation-workbench:candidate-v022-4fc4cf124a12
FROM ${LOCAL_BASE_IMAGE}
ARG SOURCE_COMMIT
ARG FRONTEND_COMMIT=63bbcc07a6b6d12a6be56fa7b0e81731c3917a45
LABEL org.opencontainers.image.title="market-regulation-platform" \
      org.opencontainers.image.revision="${SOURCE_COMMIT}" \
      cn.market-regulation.frontend.revision="${FRONTEND_COMMIT}"
USER root
WORKDIR /app
COPY qa_core ./qa_core
COPY deploy/release/entrypoint.py /opt/workbench/entrypoint.py
COPY deploy/release/application.py ./deploy/release/application.py
COPY frontend/dist ./frontend/dist
USER 65534:65534
ENTRYPOINT ["python", "-B", "/opt/workbench/entrypoint.py"]
