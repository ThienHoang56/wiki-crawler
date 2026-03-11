# RAG System — Demo & Documentation

## Completed Features

### 1. Wikipedia Crawler
- Crawl any Wikipedia topic by keyword (single or batch)
- Crawl directly from a list of Wikipedia URLs
- Auto-detect language from URL subdomain (`en.wikipedia.org`, `vi.wikipedia.org`, ...)
- Parallel batch crawling with configurable concurrency (`CRAWLER_CONCURRENCY`)
- Retry with exponential backoff on network errors
- Stores raw articles in PostgreSQL

### 2. Data Chunking & Preprocessing
- Text cleaning (strip HTML, normalize whitespace, remove boilerplate)
- Fixed-size chunking with overlap (`CHUNK_SIZE=500`, `CHUNK_OVERLAP=50`)
- Each chunk tagged with `title`, `url`, `chunk_index`, `lang`

### 3. Vector Database (Elasticsearch)
- Dual-field mapping: `content` (BM25 text) + `embedding` (dense 384-dim vector)
- Language-aware BM25 analyzers per language (`en`, `vi`, `ja`, `zh`, `fr`, `de`, ...)
- Background indexing jobs with progress tracking (non-blocking API)
- Hybrid Search = BM25 + Dense Vector merged via RRF (Reciprocal Rank Fusion)

### 4. RAG Answer Generation
- Full pipeline: Query → Embed → Hybrid Search → Rerank → LLM
- Multi-provider LLM support: OpenAI, Gemini, Anthropic, Ollama (local)
- Per-request model/temperature/max_tokens override
- Returns answer + source chunks + token usage metadata
- Retry on rate limit (429), returns proper HTTP 429 instead of 500

---

## System Requirements

| Service        | Version      | Port  |
|----------------|--------------|-------|
| PostgreSQL     | 15           | 5432  |
| Elasticsearch  | 9.0.2        | 9200  |
| Python         | >= 3.13      | —     |
| Poetry         | >= 1.8       | —     |

---

## How to Start the System

### Step 1 — Start infrastructure (Docker)
```bash
# Run from the project root (same directory as docker-compose.yml)
docker compose up -d
```

### Step 2 — Install dependencies
```bash
# Run from the project root
poetry install
```

### Step 3 — Configure environment
```bash
# Copy the example and fill in your API keys
cp .env.example .env
# Edit .env:
#   GEMINI_API_KEY=your_key_here   (or use Ollama for local LLM)
#   LLM_MODEL=gemini-flash-lite-latest
```

### Step 4 — Start the API server
```bash
# Run from the project root
poetry run uvicorn src.api.main:app --reload --port 8001
```

API docs available at: http://localhost:8001/docs

---

## Usage Commands

All commands below are run from the **project root directory**.

### Crawl Wikipedia articles

```bash
# Crawl by topic keyword
curl -X POST http://localhost:8001/api/v1/crawl/topic \
  -H "Content-Type: application/json" \
  -d '{"topic": "machine learning", "max_pages": 5}'

# Crawl multiple keywords at once
curl -X POST http://localhost:8001/api/v1/crawl/keywords \
  -H "Content-Type: application/json" \
  -d '{"keywords": ["deep learning", "neural network", "transformer"], "max_pages_per_keyword": 3}'

# Crawl specific URLs
curl -X POST http://localhost:8001/api/v1/crawl/urls \
  -H "Content-Type: application/json" \
  -d '{"urls": ["https://en.wikipedia.org/wiki/Artificial_intelligence"]}'
```

### Index articles into Elasticsearch

```bash
# Start background indexing job
curl -X POST http://localhost:8001/api/v1/index/run

# Poll job progress
curl http://localhost:8001/api/v1/index/status/<job_id>

# List all indexing jobs
curl http://localhost:8001/api/v1/index/jobs
```

### Search & RAG

```bash
# Full RAG answer (Hybrid Search + LLM)
curl -X POST http://localhost:8001/api/v1/search/ask \
  -H "Content-Type: application/json" \
  -d '{"query": "What is deep learning?"}'

# Hybrid search (no LLM, returns raw chunks)
curl -X POST http://localhost:8001/api/v1/search/hybrid \
  -H "Content-Type: application/json" \
  -d '{"query": "neural networks", "top_k": 5}'

# Semantic (vector-only) search
curl -X POST http://localhost:8001/api/v1/search/semantic \
  -H "Content-Type: application/json" \
  -d '{"query": "gradient descent optimization"}'

# BM25 fulltext search
curl -X POST http://localhost:8001/api/v1/search/fulltext \
  -H "Content-Type: application/json" \
  -d '{"query": "backpropagation"}'
```

### Manage articles (PostgreSQL)

```bash
# List all crawled articles
curl http://localhost:8001/api/v1/articles

# Get a specific article
curl http://localhost:8001/api/v1/articles/1
```

---

## Full API Reference

| Method | Endpoint                          | Description                            |
|--------|-----------------------------------|----------------------------------------|
| POST   | `/api/v1/crawl/topic`             | Crawl Wikipedia topic by keyword       |
| POST   | `/api/v1/crawl/keywords`          | Batch crawl multiple keywords          |
| POST   | `/api/v1/crawl/urls`              | Crawl specific Wikipedia URLs          |
| POST   | `/api/v1/crawl/search-titles`     | Search Wikipedia titles (no crawl)     |
| GET    | `/api/v1/articles`                | List all articles in PostgreSQL        |
| GET    | `/api/v1/articles/{id}`           | Get article by ID                      |
| DELETE | `/api/v1/articles/{id}`           | Delete article                         |
| POST   | `/api/v1/index/run`               | Start background indexing job          |
| GET    | `/api/v1/index/status/{job_id}`   | Poll indexing job progress             |
| GET    | `/api/v1/index/jobs`              | List recent indexing jobs              |
| POST   | `/api/v1/search/ask`              | RAG: Hybrid Search + LLM answer        |
| POST   | `/api/v1/search/hybrid`           | Hybrid BM25 + vector search            |
| POST   | `/api/v1/search/semantic`         | Dense vector search only               |
| POST   | `/api/v1/search/fulltext`         | BM25 fulltext search only              |
| GET    | `/`                               | Health check                           |

---

## Screenshots

See `screenshots/` folder for visual proof of each feature.

| File | What it shows |
|------|---------------|
| `01_crawl.png` | Crawling a Wikipedia topic via Swagger UI |
| `02_index.png` | Starting background indexing job |
| `03_rag_answer.png` | RAG answer with sources |
| `04_articles_list.png` | Articles stored in PostgreSQL |
