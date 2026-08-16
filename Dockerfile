# Build from the polyrepo root (develop/). Same image, two commands:
#   rba-audit-service  — RabbitMQ consumer
#   rba-audit-api      — HTTP read API (:8002)
#   docker build -f rba-audit-service/Dockerfile -t rba-audit-service:dev .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN pip install --no-cache-dir -U pip setuptools wheel

COPY rba-contracts /opt/rba-contracts
COPY rba-audit-service /app

RUN pip install --no-cache-dir /opt/rba-contracts /app \
    && useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app

USER appuser
EXPOSE 8002
CMD ["rba-audit-service"]
