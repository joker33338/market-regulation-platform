ARG QA_BASE_IMAGE=market-regulation-qa-base:b4010953
FROM ${QA_BASE_IMAGE}
USER root
COPY deploy/qa-gateway/package-lock.json /opt/qa/package-lock.json
COPY deploy/qa-gateway/install_locked.py /opt/qa/install_locked.py
RUN python -B /opt/qa/install_locked.py
COPY deploy/qa-gateway/*.py /opt/qa/
COPY tests/qa_mineru_egress_proxy.py /opt/qa/qa_mineru_egress_proxy.py
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
ENTRYPOINT ["python", "-B", "/opt/qa/init.py"]
