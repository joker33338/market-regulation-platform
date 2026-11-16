ARG LOCAL_BASE_IMAGE=market-regulation-runtime:v0.2.3-py312
FROM ${LOCAL_BASE_IMAGE}
ARG SOURCE_COMMIT
ARG FRONTEND_COMMIT
LABEL org.opencontainers.image.title="market-regulation-platform" \
      org.opencontainers.image.version="0.2.3" \
      org.opencontainers.image.revision="${SOURCE_COMMIT}" \
      cn.market-regulation.frontend.revision="${FRONTEND_COMMIT}"
USER root
WORKDIR /app
# 仅清理构建镜像继承的旧代码目录；不挂载、不清理宿主数据或模型。
RUN rm -rf /app/qa_core /app/tests /app/scripts /app/deploy/release /app/frontend/dist
EXPOSE 8180
ENV PYTHONPATH=/app
COPY qa_core ./qa_core
COPY deploy/release/application.py ./deploy/release/application.py
COPY deploy/release/entrypoint.py /opt/workbench/entrypoint.py
COPY scripts/provision_auth_accounts.py ./scripts/provision_auth_accounts.py
COPY scripts/sql ./scripts/sql
COPY requirements.txt requirements-review.txt ./
COPY frontend/dist ./frontend/dist
USER 65534:65534
HEALTHCHECK --interval=15s --timeout=6s --start-period=20s --retries=4 CMD python -B -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8180/', timeout=5).close()"
ENTRYPOINT ["python", "-B", "/opt/workbench/entrypoint.py"]
