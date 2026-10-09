# --- Stage 1: build ----------------------------------------------------------------------------------------
FROM python:3.14-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

# First only the dependency files: as long as they don't change, this layer stays in the cache.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project

# Then the code, and the static files with their fingerprints (fake keys: they only get Django started).
COPY . .
RUN SECRET_KEY=only-for-the-build ALLOWED_HOSTS=build SMTP_HOST=build DB_PASSWORD=build \
    /app/.venv/bin/python manage.py collectstatic --noinput

# --- Stage 2: the image that runs ---------------------------------------------------------------------------
FROM python:3.14-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH" \
    MEDIA_ROOT=/data/media \
    EMBEDDING_CACHE=/data/models

# An unprivileged user: if someone breaks the application, they are not root in the container.
RUN useradd --system --uid 10001 --home-dir /app vault \
    && mkdir -p /data/media /data/models \
    && chown -R vault /data

WORKDIR /app
COPY --from=build --chown=vault /app /app
USER vault

VOLUME /data
EXPOSE 8000

# The check uses Python (there is no curl in the image) and asks /health/ with an allowed Host.
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os, urllib.request as u; r = u.Request('http://127.0.0.1:8000/health/', headers={'Host': os.environ['ALLOWED_HOSTS'].split(',')[0]}); u.urlopen(r, timeout=3)" || exit 1

CMD ["gunicorn", "config.wsgi:application"]
