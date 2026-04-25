# Step 2: System Design

## What I Understood
You confirmed: use all defaults. I will now produce the complete system design before writing any code. This design will govern every subsequent step.

## What I Will Do
Produce the full architecture: directory structure, data flow, database schema, graph schema, and API specification.

---

## Final Technology Stack

```
Frontend      Next.js 14 + Tailwind CSS
Backend       Python 3.11 + FastAPI
PDF Parsing   PyMuPDF + pdfplumber + Tesseract OCR
Embeddings    BAAI/bge-m3 (local, sentence-transformers)
Vector DB     Qdrant (Docker)
Graph         NetworkX (in-memory)
Relational DB PostgreSQL 15 (Docker)
File Storage  Local filesystem
LLM           Llama 3.1 8B via Ollama (local)
VLM           LLaVA 1.6 via Ollama (local, for image understanding)
Orchestration Docker Compose
```

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER BROWSER                             │
│                                                                 │
│   ┌─────────────┐    ┌──────────────┐    ┌──────────────────┐  │
│   │ Upload Panel│    │  Chat Panel  │    │  Evidence Panel  │  │
│   └──────┬──────┘    └──────┬───────┘    └──────────────────┘  │
└──────────┼─────────────────┼────────────────────────────────────┘
           │ HTTP            │ HTTP
           ▼                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                      FASTAPI BACKEND                            │
│                                                                 │
│  ┌──────────────┐  ┌───────────────┐  ┌─────────────────────┐  │
│  │ Ingest Router│  │  Query Router │  │  Documents Router   │  │
│  └──────┬───────┘  └──────┬────────┘  └─────────────────────┘  │
│         │                 │                                     │
│  ┌──────▼───────┐  ┌──────▼────────┐                           │
│  │  Ingestion   │  │   Retrieval   │                           │
│  │  Pipeline    │  │   Pipeline    │                           │
│  └──────┬───────┘  └──────┬────────┘                           │
│         │                 │                                     │
│  ┌──────▼───────┐  ┌──────▼────────┐  ┌─────────────────────┐  │
│  │   Chunker    │  │ Hybrid Ranker │  │  Answer Generator   │  │
│  └──────┬───────┘  └──────┬────────┘  └─────────────────────┘  │
│         │                 │                                     │
│  ┌──────▼───────┐  ┌──────▼────────┐                           │
│  │ Graph Builder│  │ Graph + Vec   │                           │
│  └──────┬───────┘  │   Search      │                           │
│         │          └───────────────┘                           │
└─────────┼───────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────┐
│                     DATA LAYER                                  │
│                                                                 │
│   ┌─────────────┐  ┌──────────┐  ┌──────────┐  ┌───────────┐  │
│   │ PostgreSQL  │  │  Qdrant  │  │NetworkX  │  │ Local FS  │  │
│   │  metadata   │  │ vectors  │  │  graphs  │  │  images/  │  │
│   │  chunks     │  │          │  │          │  │  PDFs     │  │
│   └─────────────┘  └──────────┘  └──────────┘  └───────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Data Flow

### Ingestion Flow
```
PDF File
    │
    ▼
[1] Save to ./storage/pdfs/{doc_id}.pdf
    │
    ▼
[2] PyMuPDF → extract text blocks with bounding boxes + page numbers
    │
    ▼
[3] PyMuPDF → extract embedded images → save to ./storage/figures/
    │
    ▼
[4] pdfplumber → extract tables as structured row/column data
    │
    ▼
[5] Regex + heuristics → detect equations in text blocks
    │
    ▼
[6] OCR fallback → Tesseract on pages where text yield is low
    │
    ▼
[7] Caption detection → link captions to nearest figure/table
    │
    ▼
[8] Section detection → assign every block to a section title
    │
    ▼
[9] Chunker → normalize all blocks into Chunk objects
    │
    ▼
[10] Store chunks in PostgreSQL
     │
     ▼
[11] Build NetworkX graph → serialize to ./storage/graphs/{doc_id}.pkl
     │
     ▼
[12] Embed each chunk text → store vectors in Qdrant
     │
     ▼
[13] Mark document as READY in PostgreSQL
```

### Query Flow
```
User Question
    │
    ▼
[1] Classify query intent (text / figure / table / equation / mixed)
    │
    ▼
[2] Embed question → Qdrant vector search → top-K chunks
    │
    ▼
[3] Load document graph → BFS from matched chunk nodes
    │
    ▼
[4] Merge vector results + graph neighbors → deduplicate → re-rank
    │
    ▼
[5] For figure chunks → load image from filesystem
    │
    ▼
[6] Build GPT-4o prompt with text chunks + images
    │
    ▼
[7] GPT-4o → generates grounded answer
    │
    ▼
[8] Return answer + evidence list (chunk_id, page, type, snippet, image_url)
```

---

## Directory Structure

```
research-rag/
│
├── docker-compose.yml
├── .env.example
├── README.md
│
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py                        # FastAPI app entry point
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   ├── ingest.py              # POST /ingest/upload
│   │   │   ├── query.py               # POST /query/ask
│   │   │   └── documents.py           # GET /documents, GET /documents/{id}
│   │   └── models/
│   │       ├── __init__.py
│   │       ├── request_models.py      # Pydantic input schemas
│   │       └── response_models.py     # Pydantic output schemas
│   │
│   ├── ingestion/
│   │   ├── __init__.py
│   │   ├── pdf_parser.py              # PyMuPDF + pdfplumber parsing
│   │   ├── ocr_fallback.py            # Tesseract OCR
│   │   ├── figure_extractor.py        # Image extraction + saving
│   │   ├── table_extractor.py         # Table row/col extraction
│   │   ├── equation_detector.py       # Equation heuristics
│   │   ├── caption_linker.py          # Link captions to figures/tables
│   │   ├── section_detector.py        # Section title detection
│   │   └── pipeline.py                # Orchestrates all ingestion steps
│   │
│   ├── chunking/
│   │   ├── __init__.py
│   │   └── chunker.py                 # Produces normalized Chunk objects
│   │
│   ├── graph/
│   │   ├── __init__.py
│   │   └── graph_builder.py           # NetworkX graph construction
│   │
│   ├── embeddings/
│   │   ├── __init__.py
│   │   └── embedder.py                # bge-m3 embedding wrapper
│   │
│   ├── retrieval/
│   │   ├── __init__.py
│   │   ├── vector_search.py           # Qdrant search
│   │   ├── graph_search.py            # NetworkX traversal
│   │   └── hybrid_ranker.py           # Merge + re-rank results
│   │
│   ├── generation/
│   │   ├── __init__.py
│   │   ├── query_classifier.py        # Detect query intent
│   │   └── answer_generator.py        # GPT-4o prompt + call
│   │
│   ├── db/
│   │   ├── __init__.py
│   │   ├── database.py                # SQLAlchemy engine + session
│   │   ├── models.py                  # ORM models
│   │   └── migrations/
│   │       └── init.sql               # Initial schema
│   │
│   ├── storage/
│   │   ├── __init__.py
│   │   └── file_store.py              # File read/write helpers
│   │
│   └── config.py                      # All settings from env vars
│
├── frontend/
│   ├── package.json
│   ├── next.config.js
│   ├── tailwind.config.js
│   ├── tsconfig.json
│   │
│   └── src/
│       ├── app/
│       │   ├── layout.tsx
│       │   ├── page.tsx               # Main page
│       │   └── globals.css
│       │
│       ├── components/
│       │   ├── UploadPanel.tsx
│       │   ├── DocumentList.tsx
│       │   ├── ChatPanel.tsx
│       │   ├── AnswerPane.tsx
│       │   ├── EvidencePane.tsx
│       │   └── PagePreview.tsx
│       │
│       ├── lib/
│       │   └── api.ts                 # API client functions
│       │
│       └── types/
│           └── index.ts               # Shared TypeScript types
│
├── storage/                           # Runtime data (git-ignored)
│   ├── pdfs/
│   ├── figures/
│   └── graphs/
│
└── evaluation/
    ├── eval_dataset.json              # Ground truth QA pairs
    └── evaluate.py                    # Accuracy + retrieval metrics
```

---

## PostgreSQL Schema

```sql
-- documents table
CREATE TABLE documents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    filename        VARCHAR(255) NOT NULL,
    file_path       TEXT NOT NULL,
    status          VARCHAR(50) DEFAULT 'pending',
                    -- pending | processing | ready | failed
    page_count      INTEGER,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    error_message   TEXT
);

-- chunks table (one row per extracted block)
CREATE TABLE chunks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id     UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_type      VARCHAR(50) NOT NULL,
                    -- text | figure | table | equation | caption
    content         TEXT NOT NULL,     -- text or textual proxy
    page_number     INTEGER NOT NULL,
    section_title   VARCHAR(500),
    caption         TEXT,
    image_path      TEXT,              -- for figure chunks
    bbox            JSONB,             -- {x0, y0, x1, y1}
    metadata        JSONB,             -- arbitrary extra fields
    chunk_index     INTEGER,           -- order within document
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- indexes
CREATE INDEX idx_chunks_document_id ON chunks(document_id);
CREATE INDEX idx_chunks_type        ON chunks(chunk_type);
CREATE INDEX idx_chunks_page        ON chunks(page_number);

-- conversations table
CREATE TABLE conversations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id     UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- messages table
CREATE TABLE messages (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role            VARCHAR(20) NOT NULL,  -- user | assistant
    content         TEXT NOT NULL,
    evidence        JSONB,                 -- list of evidence references
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
```

---

## Graph Schema (NetworkX)

```
NODE TYPES
──────────
document    { id, filename }
section     { id, title, page_number }
paragraph   { id, content, page_number, chunk_id }
figure      { id, image_path, page_number, chunk_id }
table       { id, content, page_number, chunk_id }
equation    { id, content, page_number, chunk_id }
caption     { id, content, page_number, chunk_id }

EDGE TYPES
──────────
belongs_to      paragraph   → section
belongs_to      figure      → section
belongs_to      table       → section
belongs_to      equation    → section
belongs_to      section     → document
describes       caption     → figure
describes       caption     → table
caption_for     figure      → caption
next_to         paragraph   ↔ paragraph   (sequential on same page)
next_to         paragraph   ↔ figure      (proximity on same page)
next_to         paragraph   ↔ table       (proximity on same page)
same_section_as paragraph   ↔ figure      (shared section)
same_section_as paragraph   ↔ table       (shared section)
refers_to       paragraph   → figure      (when text says "Figure N")
refers_to       paragraph   → table       (when text says "Table N")
refers_to       paragraph   → equation    (when text says "Eq. N")
```

---

## API Endpoints

```
INGESTION
─────────
POST   /api/ingest/upload
       Body: multipart/form-data { file: PDF }
       Returns: { document_id, filename, status }

GET    /api/ingest/status/{document_id}
       Returns: { document_id, status, page_count, error_message }

DOCUMENTS
─────────
GET    /api/documents
       Returns: [ { id, filename, status, page_count, created_at } ]

GET    /api/documents/{document_id}
       Returns: { id, filename, status, chunks: [...] }

GET    /api/documents/{document_id}/chunks
       Query params: ?type=figure&page=3
       Returns: [ chunk objects ]

GET    /api/documents/{document_id}/figure/{chunk_id}
       Returns: image file (binary)

QUERY
─────
POST   /api/query/ask
       Body: { document_id, question, conversation_id? }
       Returns: {
           answer,
           conversation_id,
           evidence: [
               {
                   chunk_id,
                   chunk_type,
                   page_number,
                   section_title,
                   snippet,
                   image_url,
                   relevance_score
               }
           ]
       }

GET    /api/query/conversations/{conversation_id}
       Returns: { id, messages: [...] }

HEALTH
──────
GET    /api/health
       Returns: { status: "ok", version }
```

---

## Chunk Data Model (Python)

```python
@dataclass
class Chunk:
    id:            str          # UUID
    document_id:   str          # UUID
    chunk_type:    str          # text | figure | table | equation | caption
    content:       str          # text or textual proxy for non-text
    page_number:   int
    section_title: str | None
    caption:       str | None
    image_path:    str | None   # absolute local path for figures
    bbox:          dict | None  # {x0, y0, x1, y1} in PDF points
    metadata:      dict         # anything extra
    chunk_index:   int          # order in document
```

---

## Confirmed: Step 2 Complete

| Deliverable | Status |
|---|---|
| Technology stack | ✅ Finalized |
| Architecture diagram | ✅ Complete |
| Data flow (ingest + query) | ✅ Complete |
| Directory structure | ✅ Complete |
| PostgreSQL schema | ✅ Complete |
| Graph schema | ✅ Complete |
| API endpoint spec | ✅ Complete |
| Chunk data model | ✅ Complete |

---

## Next Step: Step 3 — Infrastructure + Ingestion Pipeline

I will create, in order:

1. `docker-compose.yml` — PostgreSQL + Qdrant + backend + frontend
2. `.env.example` — all required environment variables
3. `backend/config.py` — settings loader
4. `backend/db/models.py` — SQLAlchemy ORM models
5. `backend/db/database.py` — engine and session
6. `backend/db/migrations/init.sql` — schema creation
7. `backend/ingestion/pdf_parser.py` — core parsing
8. `backend/ingestion/figure_extractor.py`
9. `backend/ingestion/table_extractor.py`
10. `backend/ingestion/equation_detector.py`
11. `backend/ingestion/caption_linker.py`
12. `backend/ingestion/section_detector.py`
13. `backend/ingestion/pipeline.py`
14. `backend/api/routers/ingest.py`
15. `backend/main.py`

**Shall I proceed to Step 3?** Reply **"yes"** or ask any design questions first.