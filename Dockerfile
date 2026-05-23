FROM python:3.11-slim

WORKDIR /app

# install dependencies first (better caching)
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# ⚠️ IMPORTANT:
# Do NOT rely on COPY . . for dev hot-reload
# Code will be mounted from docker-compose instead

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--reload-dir", "/app"]