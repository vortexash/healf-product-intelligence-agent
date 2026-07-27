FROM python:3.12-slim

WORKDIR /app

# lxml needs libxml2/libxslt at build+run time.
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libxml2-dev libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
# Shell form so hosts that inject $PORT (Render, Railway, Fly) are honored.
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
