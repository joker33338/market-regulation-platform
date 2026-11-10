ARG LOCAL_BASE_IMAGE=market-regulation-app:local
FROM ${LOCAL_BASE_IMAGE}
ARG SOURCE_COMMIT
LABEL org.opencontainers.image.title="market-regulation-workbench" \
      org.opencontainers.image.revision="${SOURCE_COMMIT}"
USER root
WORKDIR /app
COPY qa_core ./qa_core
COPY query.py ./
COPY scripts/verify_mineru_cloud.py ./scripts/verify_mineru_cloud.py
COPY scripts/preview_offline_ingestion.py ./scripts/preview_offline_ingestion.py
COPY scripts/run_test_batch.py ./scripts/run_test_batch.py
COPY deploy/local/entrypoint.py /opt/workbench/entrypoint.py
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
    PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True
USER 65534:65534
ENTRYPOINT ["python", "-B", "/opt/workbench/entrypoint.py"]
