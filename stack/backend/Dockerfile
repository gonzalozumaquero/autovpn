FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libffi-dev libjpeg62-turbo-dev zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiamos el paquete como /app/app
COPY app /app/app
# (opcional pero útil) deja claro el PYTHONPATH
ENV PYTHONPATH=/app

VOLUME ["/app/data"]
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host","0.0.0.0","--port","8000","--log-level","info"]

