# autovpn/mgmt/api/Dockerfile
FROM python:3.11-slim

# Variables de entorno recomendadas
ENV PYTHONUNBUFFERED=1 \
    UVICORN_PORT=8000

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

