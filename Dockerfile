# syntax=docker/dockerfile:1.7-labs
FROM python:3.12-slim AS base
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

FROM base AS deps
RUN pip install --no-cache-dir pip==24.2
COPY pyproject.toml* poetry.lock* requirements*.txt* /app/ 2>/dev/null || true
# Fallback to requirements if poetry not present
RUN if [ -f requirements.txt ]; then pip install --no-cache-dir -r requirements.txt; fi

FROM base AS app
COPY --from=deps /usr/local/lib/python3.12 /usr/local/lib/python3.12
COPY . /app
EXPOSE 8080 9000
CMD ["uvicorn", "main:app", "--host=0.0.0.0", "--port=8080"]
