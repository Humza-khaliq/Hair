FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN addgroup --system app && adduser --system --ingroup app app \
 && chown -R app:app /app

USER app

EXPOSE 8080

CMD ["gunicorn", "--bind", "0.0.0.0:8080", "app:create_app()"]
