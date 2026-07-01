FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY framework/ ./framework/
COPY dashboard.py .

# Default: auto-discover containers
# Override with: -e HECF_TARGETS="bench-json,other-app"
ENV HECF_TARGETS=""

CMD ["python", "-m", "framework.main"]