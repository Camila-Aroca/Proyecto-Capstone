FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# libgomp1: runtime OpenMP que exige LightGBM.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY src/ src/
COPY scripts/ scripts/

RUN useradd --create-home --uid 1000 saad && chown -R saad:saad /app
USER saad

# Tarea por lotes: local con el volumen de Compose o en Fargate contra S3 (src/cloud/pipeline_task.py).
FROM base AS pipeline
CMD ["python", "-m", "src.cloud.pipeline_task", "--modo", "semanal"]

# Último stage: es el que se construye por defecto.
FROM base AS api
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/salud', timeout=4)"

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
