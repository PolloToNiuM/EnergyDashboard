FROM python:3.11-slim

WORKDIR /app
ENV PYTHONPATH=/app/ingestion:/app

COPY backend/app ./app
COPY backend/pyproject.toml .
COPY ingestion ./ingestion

RUN pip install --no-cache-dir .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
