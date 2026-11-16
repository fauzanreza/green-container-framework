FROM python:3.10-slim

WORKDIR /app

# Install stress-ng for cgroups v2 manual throttling & verification tests
RUN apt-get update && apt-get install -y --no-install-recommends stress-ng && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run Uvicorn server, mimicking a typical multi-worker Python microservice
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
