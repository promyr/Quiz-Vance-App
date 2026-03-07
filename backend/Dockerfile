FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY app ./app
COPY sql ./sql
COPY alembic.ini ./alembic.ini
COPY alembic ./alembic

EXPOSE 8080

CMD ["sh", "-c", "alembic upgrade head && gunicorn app.main:app -k uvicorn.workers.UvicornWorker -w ${WEB_CONCURRENCY:-2} --bind 0.0.0.0:${PORT:-8080} --timeout 120 --graceful-timeout 30 --keep-alive 30"]
