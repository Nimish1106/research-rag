# Research RAG

Production-grade multimodal RAG for research papers.

Research RAG ingests PDFs, extracts text and visual signals (figures, tables, equations), builds structured context, and provides grounded answers with evidence.

## What Is Included Today

- Multimodal ingestion pipeline for PDF content
- Figure, table, equation, caption, and text chunk handling
- Hybrid retrieval (vector + graph expansion + ranking)
- Evidence-first responses with per-source relevance scores
- Conversation-aware chat per document
- Conversation history APIs (latest + full list)
- Figure reference-aware ranking (for prompts like "Figure 1")
- Invalid/black image filtering before evidence rendering
- Docker Compose deployment for frontend, backend, PostgreSQL, and Qdrant
- Optional Ollama service profile

## Architecture

```text
Frontend (Next.js)
  -> Upload, document workspace, chat, evidence inspector

Backend (FastAPI)
  -> Ingestion, chunking, graph building, embeddings, retrieval, answer generation

Data and Infra
  -> PostgreSQL (metadata, chunks, conversations)
  -> Qdrant (vector index)
  -> Local storage (pdfs, figures, graphs)
  -> Optional Ollama profile for local LLM/VLM
```

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 14, TypeScript, Tailwind CSS |
| Backend API | FastAPI, Pydantic |
| Database | PostgreSQL 15 |
| Vector DB | Qdrant |
| Embeddings | BAAI/bge-m3 |
| LLM Providers | Gemini (default), Ollama (optional profile) |
| Orchestration | Docker Compose |

## Repository Layout

```text
research-rag/
  backend/
    api/
      routers/
      models/
    chunking/
    db/
    embeddings/
    file_storage/
    generation/
    graph/
    ingestion/
    llm/
    retrieval/
    config.py
    main.py
  frontend/
    src/
      app/
      components/
      lib/
      types/
  evaluation/
    eval_dataset.json
    evaluate.py
  storage/
    pdfs/
    figures/
    graphs/
  docker-compose.yml
  .env.example
  setup.sh
```

## Prerequisites

- Docker Desktop (or Docker Engine + Compose plugin)
- At least 16 GB RAM recommended for comfortable local execution
- Sufficient free disk for model/cache and extracted assets

## Configuration

Create `.env` from `.env.example` and update values as needed.

Minimum required runtime settings:

```env
# Database
POSTGRES_DB=research_rag
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres

# Backend
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/research_rag

# LLM provider
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-1.5-flash
GEMINI_TIMEOUT_SECONDS=120

# Retrieval
TOP_K_VECTOR=10
TOP_K_GRAPH=5
```

Important:
- `GEMINI_TIMEOUT_SECONDS` must be a valid integer (do not leave empty).
- If `LLM_PROVIDER=ollama`, ensure Ollama is running and models are pulled.

## Quick Start (Docker)

1. Build and start the full stack:

```bash
docker compose up -d --build
```

2. Verify services:

```bash
docker compose ps
```

3. Open applications:
- Frontend: http://localhost:3000
- Backend OpenAPI: http://localhost:8000/docs
- Health endpoint: http://localhost:8000/api/health
- Qdrant: http://localhost:6333

## Optional: Run Ollama Profile

Ollama is not started by default.

1. Start Ollama service:

```bash
docker compose --profile ollama up -d ollama
```

2. Pull models:

```bash
docker exec research-rag-ollama ollama pull llama3.2:3b
docker exec research-rag-ollama ollama pull llava:13b
```

3. Switch provider in `.env`:

```env
LLM_PROVIDER=ollama
```

Then restart backend:

```bash
docker compose restart backend
```

## API Overview

Base URL: `http://localhost:8000/api`

### Ingestion

- `POST /ingest/upload`
  - Upload PDF and start background processing
- `GET /ingest/status/{document_id}`
  - Poll ingestion status (`pending`, `processing`, `ready`, `failed`)

### Documents

- `GET /documents`
  - List all documents
- `GET /documents/{document_id}`
  - Get single document
- `GET /documents/{document_id}/chunks`
  - Optional filters: `chunk_type`, `page`
- `GET /documents/{document_id}/figure/{chunk_id}`
  - Fetch figure image for evidence rendering
- `DELETE /documents/{document_id}`
  - Delete document and cascaded data

### Query and Conversations

- `POST /query/ask`
  - Ask grounded question for a document
  - Supports continuing an existing conversation via `conversation_id`
- `GET /query/conversations/{conversation_id}`
  - Full message history for one conversation
- `GET /query/documents/{document_id}/latest-conversation`
  - Most recent conversation for a document
- `GET /query/documents/{document_id}/conversations`
  - All conversation summaries for a document (newest first)

## Example API Requests

Upload PDF:

```bash
curl -X POST http://localhost:8000/api/ingest/upload \
  -F "file=@paper.pdf"
```

Ask question (new conversation):

```bash
curl -X POST http://localhost:8000/api/query/ask \
  -H "Content-Type: application/json" \
  -d '{
    "document_id": "<document-uuid>",
    "question": "Describe Figure 1"
  }'
```

Ask question (existing conversation):

```bash
curl -X POST http://localhost:8000/api/query/ask \
  -H "Content-Type: application/json" \
  -d '{
    "document_id": "<document-uuid>",
    "conversation_id": "<conversation-uuid>",
    "question": "Now compare it with Figure 2"
  }'
```

## Frontend Behavior

Current UI behavior includes:
- Product-style workspace shell
- Left panel: upload and document list
- Center panel: chat with conversation selector and "New chat"
- Right panel: evidence inspector for selected assistant response
- Graceful fallback when evidence image preview fails

## Operational Runbooks

### Restart all services

```bash
docker compose restart
```

### Clean data reset (fresh start)

Use this when local files are removed manually and indexes/state drift:

```bash
# 1) Clear relational data
docker exec research-rag-postgres psql -U postgres -d research_rag -c "TRUNCATE TABLE conversations CASCADE; TRUNCATE TABLE messages CASCADE; TRUNCATE TABLE chunks CASCADE; TRUNCATE TABLE documents CASCADE;"

# 2) Clear local storage assets
# Windows PowerShell
Remove-Item -Path .\storage\* -Recurse -Force -ErrorAction SilentlyContinue

# 3) Recreate running services cleanly
docker compose up -d
```

### Check health quickly

```bash
docker compose ps
curl http://localhost:8000/api/health
curl http://localhost:8000/api/documents
```

## Troubleshooting

### Backend fails with `gemini_timeout_seconds` validation error

Cause:
- `GEMINI_TIMEOUT_SECONDS` is empty or non-integer in `.env`.

Fix:
- Set a valid integer, for example:

```env
GEMINI_TIMEOUT_SECONDS=120
```

Then restart backend:

```bash
docker compose restart backend
```

### Backend starts but answers fail

Checks:
- `LLM_PROVIDER` is set correctly
- For Gemini: `GEMINI_API_KEY` exists
- For Ollama: service is running and models are available

### No documents shown in frontend

Checks:
- Backend up on port 8000
- Frontend up on port 3000
- `GET /api/documents` returns JSON

## Development Notes

- Backend source is mounted into container during local Docker runs.
- Frontend builds with `NEXT_PUBLIC_API_URL=http://backend:8000/api` in container.
- Persistent runtime data lives under `storage/` and PostgreSQL/Qdrant volumes.

## Evaluation

Run evaluation script from repository root:

```bash
python evaluation/evaluate.py
```

## License

MIT
