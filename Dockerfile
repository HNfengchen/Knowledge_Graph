FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src

RUN pip install --no-cache-dir -e ".[dev]"

COPY prompts ./prompts

EXPOSE 8000

CMD ["uvicorn", "kg_system.main:app", "--host", "0.0.0.0", "--port", "8000"]
