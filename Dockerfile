# syntax=docker/dockerfile:1.7-labs
FROM python:3.12-slim AS base
WORKDIR /opt/collectai
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

FROM base AS deps
RUN pip install --no-cache-dir pip==24.2
COPY pyproject.toml* poetry.lock* requirements*.txt* /opt/collectai/ 2>/dev/null || true
# Fallback to requirements if poetry not present
RUN if [ -f requirements.txt ]; then pip install --no-cache-dir -r requirements.txt; fi

FROM base AS app
COPY --from=deps /usr/local/lib/python3.12 /usr/local/lib/python3.12
COPY server/ /opt/collectai/server/
COPY src/ /opt/collectai/src/

# Non-root user for security
RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid appuser --shell /bin/bash --create-home appuser && \
    chown -R appuser:appuser /opt/collectai
USER appuser

WORKDIR /opt/collectai/server

EXPOSE 8080 9000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/healthz')" || exit 1
CMD ["uvicorn", "main:app", "--host=0.0.0.0", "--port=8080"]
