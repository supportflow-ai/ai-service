FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1
WORKDIR /build
COPY pyproject.toml README.md requirements-runtime.lock ./
COPY src ./src
RUN python -m pip wheel --wheel-dir /wheels -r requirements-runtime.lock \
    && python -m pip wheel --no-deps --wheel-dir /wheels .

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN groupadd --system app && useradd --system --gid app --create-home app
WORKDIR /app
COPY --from=builder /wheels /wheels
COPY requirements-runtime.lock ./
RUN python -m pip install --no-index --find-links=/wheels -r requirements-runtime.lock \
    && python -m pip install --no-index --no-deps --find-links=/wheels supportflow-ai-service \
    && rm -rf /wheels

USER app
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/ready', timeout=2)" || exit 1
CMD ["uvicorn", "supportflow_ai.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
