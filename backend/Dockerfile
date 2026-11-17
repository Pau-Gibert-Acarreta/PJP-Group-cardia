# Core Backend API + data jobs (ETL, rules, KNN index, lab reports).
# Build context: repository root (the backend reads db/ and src/config/ from the repo layout).
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYTHONUTF8=1 PATH="/app/backend/.venv/bin:$PATH"
WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/app ./app
COPY db /app/db
COPY src/config /app/src/config
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
