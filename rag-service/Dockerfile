FROM python:3.13-slim

WORKDIR /app

RUN useradd --system --home-dir /app app

COPY pyproject.toml .
COPY src ./src
COPY data ./data

RUN pip install --no-cache-dir .
RUN mkdir -p /app/data/processed && chown -R app:app /app

USER app

EXPOSE 8001

ENV RAG_OPS_ENABLE_CACHE=true
ENV RAG_DATA_ROOT=/app/data

CMD ["uvicorn", "rag_service.api:app", "--host", "0.0.0.0", "--port", "8001"]
