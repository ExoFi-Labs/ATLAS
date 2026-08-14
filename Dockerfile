FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src
COPY web ./web
COPY examples ./examples

RUN pip install --no-cache-dir .

EXPOSE 8080

CMD ["atlas", "serve"]
