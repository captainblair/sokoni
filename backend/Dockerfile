# syntax=docker/dockerfile:1

FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements/base.txt /tmp/requirements-base.txt
COPY backend/requirements/production.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

COPY backend /app

RUN adduser --disabled-password --gecos "" sokoni \
    && chown -R sokoni:sokoni /app
USER sokoni

EXPOSE 8000

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2"]
