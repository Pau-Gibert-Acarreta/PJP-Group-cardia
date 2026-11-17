# Risk Engine: frozen CoxPH model + exact SHAP, served with FastAPI.
# Python 3.12 and the locked scikit-learn/scipy versions are required to unpickle the model.
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYTHONUTF8=1 PATH="/app/ml/.venv/bin:$PATH"
WORKDIR /app/ml
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project
COPY service.py ./
COPY src ./src
COPY models ./models
COPY experiments/coxph/best_pipeline.py ./experiments/coxph/best_pipeline.py
EXPOSE 8001
CMD ["uvicorn", "service:app", "--host", "0.0.0.0", "--port", "8001"]
