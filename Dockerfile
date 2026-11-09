FROM python:3.12-slim-bookworm
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
WORKDIR /app
COPY requirements.txt ./
RUN sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list.d/debian.sources \
    && apt-get -o Acquire::Retries=3 update \
    && apt-get -o Acquire::Retries=3 install -y --no-install-recommends libgl1 libglib2.0-0 libgomp1 libxext6 libsm6 \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir torch==2.7.1 --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt
ENV PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True
COPY qa_core ./qa_core
COPY scripts ./scripts
COPY scenarios ./scenarios
COPY tests ./tests
COPY query.py ./
CMD ["sleep", "infinity"]
