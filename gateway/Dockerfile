FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app
# PYTHONPATH=/app matters specifically for celery-worker/celery-beat: the
# `celery` console-script sets sys.path[0] to its own install directory,
# not the working directory, so /app (and gateway/shared/services) would
# otherwise be unimportable once Celery finalizes the app and runs
# autodiscover_tasks -- uvicorn/alembic/pytest aren't affected (they add
# cwd to sys.path themselves), but celery's worker/beat entrypoints are.

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY gateway ./gateway
COPY shared ./shared
COPY services ./services
COPY alembic.ini ./
COPY migrations ./migrations

EXPOSE 8000

CMD ["uvicorn", "gateway.main:app", "--host", "0.0.0.0", "--port", "8000"]
