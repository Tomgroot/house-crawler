FROM python:3.12-slim

WORKDIR /app

# Install supercronic — a Docker-native cron daemon that logs to stdout
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && curl -fsSL \
       https://github.com/aptible/supercronic/releases/download/v0.2.29/supercronic-linux-amd64 \
       -o /usr/local/bin/supercronic \
    && chmod +x /usr/local/bin/supercronic \
    && apt-get purge -y --auto-remove curl \
    && rm -rf /var/lib/apt/lists/*

COPY . .

RUN pip install --no-cache-dir .

# Persistent data directory (SQLite DB lives here via volume mount)
RUN mkdir -p /data

RUN chmod +x /app/scripts/crawl.sh /app/scripts/app-entrypoint.sh

ENV DATABASE_URL=sqlite:////data/house_crawler.db
ENV MAX_PAGES=20
ENV LOG_LEVEL=INFO

EXPOSE 8501
