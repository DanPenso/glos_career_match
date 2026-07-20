# Gloucestershire Career Match API (FastAPI + ML artefacts)
FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY api ./api
COPY src ./src
COPY app/app_data ./app/app_data
COPY data/taxonomy ./data/taxonomy
COPY data/seed ./data/seed
COPY data/corpus ./data/corpus

RUN mkdir -p data/live

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
