FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY framework/ ./framework/

# Default: auto-discover containers
# Override dengan: -e HGCF_TARGETS="portfolio-web,app-signature"
ENV HGCF_TARGETS=""

CMD ["python", "-m", "framework.main"]