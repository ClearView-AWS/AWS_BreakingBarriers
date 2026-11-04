FROM --platform=linux/amd64 python:3.12-slim

WORKDIR /app

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

COPY backend /app/backend
COPY data /app/data
# JSON form keeps the space in "Sample Data" intact.
COPY ["Sample Data/", "/app/Sample Data/"]

ENV PYTHONPATH=/app/backend
ENV GS_STATE_PATH=/tmp/gs-state.json
ENV GS_TODAY=2026-11-03
ENV AWS_REGION=us-east-1

WORKDIR /app/backend

EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
