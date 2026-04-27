FROM python:3.12-slim

LABEL maintainer="Patticus <patticus@proton.me>"
LABEL description="Headache Log - self-hostable headache tracking app"

# Install curl for health check
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy only requirements first for better caching
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY app/ ./app/
COPY static/ ./static/

# Non-root user for security
RUN useradd -m -u 1000 headache && chown -R headache:headache /app
USER headache

EXPOSE 5000

ENV PORT=5000
ENV DATA_FILE=/app/data/headache-log.json

# Pre-create data directory
RUN mkdir -p /app/data && touch "$DATA_FILE" && chown headache:headache "$DATA_FILE"

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:5000/ || exit 1

CMD ["python", "-u", "app/server.py"]