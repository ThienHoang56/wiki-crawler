# Wikipedia RAG API

Hệ thống RAG (Retrieval-Augmented Generation) từ Wikipedia — cào bài viết, lưu vào PostgreSQL, index vào Elasticsearch, trả lời câu hỏi bằng LLM.

> **Tài liệu kỹ thuật đầy đủ:** xem thư mục [`docs/`](./docs/)

---

## Kiến trúc tổng quan

```
Wikipedia API
     │
     ▼
[ Crawler ] ──────────────────► PostgreSQL (raw articles)
  httpx, async, semaphore               │
  retry + backoff                       │
  multilingual (en/vi/ja/...)           ▼
                               [ RAG Indexing Pipeline ]
                                  Clean → Chunk → Embed
                                       │
                                       ▼
                               Elasticsearch
                               ├─ Full-text index (BM25)
                               └─ Dense vector index (384-dim)
                                       │
                                       ▼
                               [ Search & RAG ]
                               BM25 + Vector + RRF Fusion
                                       │
                                       ▼
                                  LLM (OpenAI)
                                  → Answer + Sources
```

---

## Yêu cầu

- Python 3.11+
- Docker & Docker Compose
- OpenAI API Key (cho endpoint `/search/ask`)

---

## Cài đặt nhanh

```bash
# 1. Clone và cài dependencies
git clone <repo-url>
cd wiki-crawler
python -m venv .venv && source .venv/bin/activate
pip install -e .

# 2. Cấu hình
cp .env.example .env
# Chỉnh sửa .env: đặt DATABASE_URL, OPENAI_API_KEY, ES_HOST

# 3. Khởi động infrastructure (PostgreSQL + Elasticsearch)
make infra

# 4. Tạo bảng PostgreSQL
make migrate

# 5. Chạy server
make dev
# → http://localhost:8000/docs
```

---

## Luồng sử dụng chuẩn

```
Bước 1: Crawl bài viết Wikipedia → lưu PostgreSQL
Bước 2: Index bài viết → Elasticsearch (background job)
Bước 3: Tìm kiếm / hỏi đáp
```

### Bước 1 — Crawl

| Endpoint | Mô tả | Use case |
|---|---|---|
| `POST /api/v1/crawl/search-titles` | Tìm tiêu đề theo keyword, không lưu | Preview trước khi crawl |
| `POST /api/v1/crawl/fetch` | Fetch 1 bài theo tiêu đề | Lấy bài cụ thể |
| `POST /api/v1/crawl/topic` | Crawl theo 1 keyword, song song | Thu thập theo chủ đề |
| `POST /api/v1/crawl/urls` | Crawl từ danh sách URL, song song | Có sẵn URL |
| `POST /api/v1/crawl/keywords` | Crawl nhiều keyword cùng lúc | Thu thập hàng loạt |

**Ví dụ — crawl nhiều keyword:**
```bash
curl -X POST http://localhost:8000/api/v1/crawl/keywords \
  -H "Content-Type: application/json" \
  -d '{
    "keywords": ["Machine learning", "Deep learning", "NLP"],
    "limit_per_keyword": 5,
    "lang": "en"
  }'
```

**Ví dụ — crawl URLs mix ngôn ngữ:**
```bash
curl -X POST http://localhost:8000/api/v1/crawl/urls \
  -H "Content-Type: application/json" \
  -d '{
    "urls": [
      "https://en.wikipedia.org/wiki/Transformer_(machine_learning_model)",
      "https://vi.wikipedia.org/wiki/Học_máy",
      "https://ja.wikipedia.org/wiki/機械学習"
    ]
  }'
```

### Bước 2 — Index (async)

```bash
# Submit job — trả về job_id ngay, không block
curl -X POST http://localhost:8000/api/v1/index/run \
  -d '{"batch_size": 100}'

# Poll tiến trình
curl http://localhost:8000/api/v1/index/status/<job_id>
# → {"status": "running", "progress": {"percent": 45.0, ...}}

# Xem tất cả jobs
curl http://localhost:8000/api/v1/index/jobs
```

### Bước 3 — Search & RAG

```bash
# Hybrid search (BM25 + Vector + RRF) — chỉ trả chunks
curl -X POST http://localhost:8000/api/v1/search/hybrid \
  -d '{"query": "How does attention mechanism work?", "top_k": 5}'

# RAG full pipeline — trả lời tự nhiên bằng LLM
curl -X POST http://localhost:8000/api/v1/search/ask \
  -d '{"query": "Explain transformers in machine learning"}'
```

---

## Tất cả API endpoints (19 endpoints)

### Crawl (`/api/v1/crawl`)
| Method | Path | Mô tả |
|---|---|---|
| POST | `/crawl/search-titles` | Tìm tiêu đề theo keyword |
| POST | `/crawl/fetch` | Fetch 1 bài theo tiêu đề |
| POST | `/crawl/topic` | Crawl chủ đề — search + fetch song song |
| POST | `/crawl/urls` | Crawl từ danh sách URLs, tự detect ngôn ngữ |
| POST | `/crawl/keywords` | Crawl nhiều keyword song song, deduplicate |

### Articles (`/api/v1/articles`)
| Method | Path | Mô tả |
|---|---|---|
| GET | `/articles/stats` | Thống kê số bài (tổng, đã index, chưa index) |
| GET | `/articles/` | Danh sách bài viết (pagination) |
| GET | `/articles/{id}` | Chi tiết 1 bài |
| DELETE | `/articles/{id}` | Xóa 1 bài |

### Index (`/api/v1/index`)
| Method | Path | Mô tả |
|---|---|---|
| GET | `/index/stats` | Thống kê Elasticsearch |
| POST | `/index/run` | Submit indexing job (async, trả job_id ngay) |
| GET | `/index/status/{job_id}` | Poll tiến trình job |
| GET | `/index/jobs` | Danh sách 20 jobs gần nhất |
| POST | `/index/reset` | Reset toàn bộ ES index |

### Search & RAG (`/api/v1/search`)
| Method | Path | Mô tả |
|---|---|---|
| POST | `/search/fulltext` | BM25 full-text search |
| POST | `/search/semantic` | Dense vector (cosine) search |
| POST | `/search/hybrid` | BM25 + Vector + RRF Fusion |
| POST | `/search/ask` | RAG pipeline — trả lời bằng LLM |

---

## Cấu hình `.env`

```bash
# PostgreSQL
DATABASE_URL=postgresql://admin:password@localhost:5432/wiki_db

# Elasticsearch
ES_HOST=http://localhost:9200
INDEX_NAME=wiki_chunks

# LLM
OPENAI_API_KEY=sk-...
LLM_MODEL=gpt-4o-mini

# Embedding — dims phải khớp với model
# all-MiniLM-L6-v2=384 | all-mpnet-base-v2=768
EMBEDDING_MODEL=all-MiniLM-L6-v2
EMBEDDING_DIMS=384
CHUNK_SIZE=500
CHUNK_OVERLAP=50

# Crawler
CRAWLER_WIKI_LANG=en          # Ngôn ngữ mặc định (en, vi, ja, zh...)
CRAWLER_CONCURRENCY=3          # Số request đồng thời (an toàn: 3-5)
CRAWLER_RATE_LIMIT_SECONDS=1.0
CRAWLER_RETRY_COUNT=3
CRAWLER_TIMEOUT_SECONDS=15.0

# Search & RAG
SEARCH_CANDIDATE_POOL=20       # Pool BM25+Vector trước RRF
RRF_K=60                       # Hằng số RRF (paper gốc: 60)
RAG_HYBRID_POOL=10             # Số chunks hybrid trước rerank
RAG_TOP_K_CONTEXT=3            # Số chunks truyền vào LLM
```

---

## Cấu trúc thư mục

```
wiki-crawler/
├── src/
│   ├── api/main.py              # FastAPI app entry point
│   ├── routers/                 # HTTP routing (4 groups)
│   ├── controller/              # Request/response handling
│   ├── services/                # Business logic
│   ├── utils/                   # crawler, cleaner, chunker, embedder
│   ├── core/                    # config, database, vector_db, llm_client, job_store
│   ├── models/                  # SQLAlchemy models (PostgreSQL)
│   ├── repository/              # Data access layer
│   └── schemas/                 # Pydantic request/response models
├── jobs/
│   └── ingest_pipeline.py       # Standalone offline indexing script
├── docs/                        # Tài liệu kỹ thuật chi tiết
│   ├── 00-blackbox.md           # Hệ thống nhận gì, trả gì
│   ├── 01-architecture.md       # Quyết định thiết kế
│   ├── 02-data-flow.md          # Luồng dữ liệu chi tiết
│   ├── 03-pipeline-pseudocode.md # Pseudo code từng pipeline
│   ├── 04-api-guide.md          # Hướng dẫn sử dụng API
│   └── 05-config-explained.md  # Giải thích từng config param
├── docker-compose.yml
├── Makefile
└── .env.example
```

---

## Make commands

```bash
make infra      # Chạy PostgreSQL + Elasticsearch
make infra-down # Dừng infrastructure
make dev        # Chạy FastAPI dev server (--reload)
make migrate    # Tạo bảng PostgreSQL
make index      # Chạy offline indexing job
make logs       # Xem logs containers
make shell      # Vào shell Python với context đầy đủ
```

---

## Tính năng nổi bật

| Tính năng | Chi tiết |
|---|---|
| **Parallel crawling** | `asyncio.Semaphore` — N request đồng thời, configurable |
| **Auto retry** | Exponential backoff, 3 lần thử |
| **Multilingual** | Hỗ trợ en, vi, ja, zh, fr, de,... — tự detect từ URL |
| **Bulk indexing** | ES `helpers.bulk()` — nhanh hơn ~10-20x |
| **Async index jobs** | Submit job → poll status, không block API |
| **Hybrid search** | BM25 + Dense Vector + RRF Fusion (paper Cormack 2009) |
| **No magic numbers** | Tất cả params trong `.env`, không hard-code |
| **Lazy init** | ES, LLM, Embedding model chỉ load khi cần |

---

## Giới hạn hiện tại (roadmap)

| Tính năng | Trạng thái |
|---|---|
| Redis caching cho query | ⏳ Config có sẵn, chưa implement |
| Crawl theo Wikipedia Category | ⏳ Chưa có |
| Cross-encoder reranker | ⏳ Hiện tại dùng RRF score |
| Incremental re-index (hash diff) | ⏳ Chưa có |
| Streaming LLM response | ⏳ Chưa có |
