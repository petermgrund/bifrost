FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt dev/requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-dev.txt

ENV BIFROST_CONFIG=/app/dev/config.yaml
EXPOSE 8800
CMD ["uvicorn", "bifrost.web.app:app", "--host", "0.0.0.0", "--port", "8800", "--reload"]
