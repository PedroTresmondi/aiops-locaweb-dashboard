FROM node:24-alpine AS frontend
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=7860
WORKDIR /app

# Build enxuto por padrão (Render, Hugging Face, Railway, local). Para a imagem
# do Azure Container Instance — que precisa de MySQL passwordless + Application
# Insights — construa com:  docker build --build-arg INSTALL_AZURE=true .
ARG INSTALL_AZURE=false
COPY backend/requirements.txt backend/requirements-azure.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt \
    && if [ "$INSTALL_AZURE" = "true" ]; then pip install --no-cache-dir -r backend/requirements-azure.txt; fi

COPY model_pipeline.py risk_pipeline.py dataset_limpo.parquet ./
COPY backend/ ./backend/
COPY --from=frontend /build/dist ./frontend/dist

EXPOSE 7860
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT}"]
