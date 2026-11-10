FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --upgrade pip && pip install -r /app/backend/requirements.txt

COPY backend /app/backend
COPY frontend /app/frontend
RUN mkdir -p /app/uploads /app/secrets \
    && sed -i 's/\r$//' /app/backend/scripts/entrypoint.sh \
    && chmod +x /app/backend/scripts/entrypoint.sh

WORKDIR /app/backend
EXPOSE 8000

ENTRYPOINT ["/app/backend/scripts/entrypoint.sh"]
CMD ["api"]
