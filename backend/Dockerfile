FROM python:3.11-slim

WORKDIR /app

# Install system deps for psycopg2, geopandas, etc.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc g++ libgdal-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Mount data/ and artifacts/ at runtime via docker-compose
EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
