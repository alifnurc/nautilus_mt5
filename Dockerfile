FROM python:3.13-slim as builder

WORKDIR /app

RUN apt-get update && apt-get upgrade -y --no-install-recommends

COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

FROM python:3.13-slim

WORKDIR /app

COPY --from=builder /root/.local /root/.local

ENV PATH=/root/.local/bin:$PATH

CMD ["python", "src/main.py"]
