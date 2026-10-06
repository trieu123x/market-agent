FROM python:3.13-slim

# tesseract cho OCR ảnh nhúng trong PDF (OCR_ENABLED=true, OCR_LANGUAGE=vie+eng)
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-vie tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HF_HOME=/app/.cache/huggingface
WORKDIR /app

# Cài dependency trước (cache layer), rồi mới copy code
COPY pyproject.toml ./
# torch bản CPU (tránh kéo bản CUDA vài GB) cho Cross-Encoder reranker
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch
RUN mkdir app && touch app/__init__.py && pip install --no-cache-dir . && rm -rf app

COPY alembic.ini ./
COPY app ./app
COPY scripts ./scripts
RUN pip install --no-cache-dir --no-deps .

EXPOSE 8000
# Container "api": migrate + seed (idempotent) rồi chạy uvicorn. Worker override command trong docker-compose.
CMD ["sh", "-c", "alembic upgrade head && python -m scripts.seed && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
