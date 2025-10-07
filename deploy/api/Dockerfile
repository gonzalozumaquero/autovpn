# deploy/api/Dockerfile
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_MODE=installer

RUN apt-get update && apt-get install -y --no-install-recommends \
    openssh-client sshpass curl git \
    ansible \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt ./
RUN pip install -U pip && pip install -r requirements.txt

# Copia el código
COPY . /app

# Exponer en 4000
EXPOSE 4000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "4000"]

