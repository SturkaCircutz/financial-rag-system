# Financial RAG System

<p>
  <a href="http://localhost:5173/"><img alt="Project UI" src="https://img.shields.io/badge/Project-UI-2f6f9f?style=for-the-badge"></a>
  <a href="http://localhost:8080/swagger-ui/index.html"><img alt="API Docs" src="https://img.shields.io/badge/API-Docs-4b5563?style=for-the-badge"></a>
  <a href="http://localhost:8001/health"><img alt="RAG Service" src="https://img.shields.io/badge/RAG-Service-6d4aff?style=for-the-badge"></a>
  <a href="http://localhost:8080/actuator/health"><img alt="Spring Backend" src="https://img.shields.io/badge/Spring-Backend-2f855a?style=for-the-badge"></a>
  <img alt="Local First" src="https://img.shields.io/badge/Local-First-c2410c?style=for-the-badge">
</p>

A local-first financial research app: Spring Boot handles the API, the Python RAG service handles retrieval and report generation, and React gives it a small UI.

## Run

```bash
docker compose up --build -d
cd frontend
npm run dev -- --host 0.0.0.0
```

Open:

- UI: http://localhost:5173/
- Backend health: http://localhost:8080/actuator/health
- RAG health: http://localhost:8001/health
- API docs: http://localhost:8080/swagger-ui/index.html

## LLM

The app works without OpenAI by using the local structured generator.

To try OpenAI locally, set these in `.env`:

```bash
RAG_LLM_PROVIDER=openai
OPENAI_API_KEY=your_key_here
OPENAI_MODEL=gpt-4.1-mini
```

If the key or model fails, the RAG service falls back to local generation.

## Project Map

- `backend/` - Spring Boot API, report jobs, exports, request IDs, OpenAPI docs.
- `rag-service/` - LangGraph flow, ingestion, chunking, retrieval, reranking, context building, report generation.
- `frontend/` - React/Vite UI for creating reports, checking history, viewing citations, and exporting.
- `compose.yaml` - local backend, RAG service, and DynamoDB Local.
- `scripts/` - local checks, dev helpers, RAG backfill/reindex/retention.
- `docs/ROADMAP.md` - phase plan and architecture notes.

## Checks

```bash
./scripts/check.sh
./scripts/check-rag-service.sh
cd frontend && npm test
```
