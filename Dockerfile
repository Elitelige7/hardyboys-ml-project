FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY backend/requirements.txt /tmp/requirements.txt
RUN python -m pip install -r /tmp/requirements.txt

RUN useradd --create-home --uid 10001 appuser
RUN chown appuser:appuser /app
COPY --chown=appuser:appuser . /app
USER appuser

EXPOSE 8000
CMD ["python", "docker_start.py"]
