# API image for ECS Fargate. Build context is the repo root, because the API
# reads "Sample Data/", data/synthetic/ and data/index/ as well as backend/.
#   docker build -f backend/Dockerfile -t gs-guided-api .
FROM public.ecr.aws/docker/library/python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install -r backend/requirements.txt

COPY backend/ backend/
COPY ["Sample Data/", "Sample Data/"]
COPY data/synthetic/ data/synthetic/
COPY data/index/ data/index/

RUN useradd --create-home --uid 1000 app && mkdir -p data/runtime && chown -R app /app/data
USER app

WORKDIR /app/backend
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health')"
CMD ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
