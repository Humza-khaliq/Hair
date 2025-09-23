FROM python:3.11-slim

WORKDIR /app

# Install dependencies first for better layer caching
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code and assets explicitly
COPY app.py ./
COPY templates ./templates
COPY static ./static

CMD ["sh", "-c", "gunicorn app:app --workers 2 --threads 4 --timeout 120 --bind 0.0.0.0:${PORT}"]
