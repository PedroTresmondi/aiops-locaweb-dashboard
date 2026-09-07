FROM node:24-alpine AS frontend
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000
WORKDIR /app

# Imagem única publicada no Azure Container Registry (acraiopsvisionopsai) e
# executada no Azure Container Instance (aci-aiops-sla-monitor). As dependências
# Azure ficam instaladas mas só são exercidas quando VISIONOPS_DATASOURCE=mysql
# e/ou APPLICATIONINSIGHTS_CONNECTION_STRING estão no ambiente do container.
COPY backend/requirements.txt backend/requirements-azure.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements-azure.txt

COPY model_pipeline.py risk_pipeline.py dataset_limpo.parquet ./
COPY backend/ ./backend/
COPY --from=frontend /build/dist ./frontend/dist

EXPOSE 8000
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT}"]
