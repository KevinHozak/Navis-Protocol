FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Environment variables for cloud deployment
ENV PORT 8080
ENV PROTOCOL_PATH /data/protocol

# Run with uvicorn on the cloud-standard port
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port $PORT"]
