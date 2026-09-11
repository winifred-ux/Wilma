# Wilma API -- Hugging Face Spaces deployment.
# Hugging Face expects port 7860 by default.

FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/app/.hf-cache \
    TRANSFORMERS_CACHE=/app/.hf-cache

COPY requirements-hf.txt /app/requirements-hf.txt
RUN pip install --upgrade pip && pip install -r /app/requirements-hf.txt

COPY pyproject.toml /app/pyproject.toml
COPY src /app/src
COPY static /app/static

RUN pip install -e .

EXPOSE 7860

CMD ["uvicorn", "wilma.api.service:app", "--host", "0.0.0.0", "--port", "7860"]
