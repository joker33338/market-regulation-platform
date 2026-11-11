ARG FRONTEND_BASE_IMAGE=market-regulation-workbench:candidate-v022-4fc4cf124a12
FROM ${FRONTEND_BASE_IMAGE}
ARG FRONTEND_COMMIT
LABEL org.opencontainers.image.title="market-regulation-frontend" \
      org.opencontainers.image.revision="${FRONTEND_COMMIT}"
WORKDIR /opt/frontend
COPY server.py ./server.py
COPY dist/ ./dist/
USER 65534:65534
EXPOSE 8080
ENTRYPOINT ["python", "-B", "-m", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8080", "--no-access-log", "--no-proxy-headers"]
