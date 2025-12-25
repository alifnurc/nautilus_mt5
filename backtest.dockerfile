# Build stage
FROM python:3.13-slim AS builder

WORKDIR /app

COPY requirements.txt .

RUN apt-get update && apt-get upgrade -y --no-install-recommends && \
  apt-get clean && \
  rm -rf /var/lib/apt/lists/* && \
  pip install --user --no-cache-dir -r requirements.txt && \
  rm -f requirements.txt

# Runtime stage
FROM python:3.13-slim

WORKDIR /app

COPY --from=builder /root/.local /root/.local

ENV PATH=/root/.local/bin:$PATH
