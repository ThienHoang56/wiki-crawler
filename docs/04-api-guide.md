# 04 — Hướng dẫn API: Ví dụ thực tế cho mọi endpoint

> Tất cả ví dụ dùng `curl`. Server chạy tại `http://localhost:8000`.
> Swagger UI đầy đủ: http://localhost:8000/docs

---

## Nhóm 1: CRAWL

### `POST /api/v1/crawl/search-titles` — Tìm tiêu đề (không lưu)

Dùng khi: Muốn preview trước khi crawl, kiểm tra Wikipedia có bài về topic không.

```bash
curl -X POST http://localhost:8000/api/v1/crawl/search-titles \
  -H "Content-Type: application/json" \
  -d '{
    "keyword": "Transformer neural network",
    "limit": 5,
    "lang": "en"
  }'
```

**Response:**
```json
{
  "keyword": "Transformer neural network",
  "lang": "en",
  "titles": [
    "Transformer (deep learning)",
    "Attention (machine learning)",
    "BERT (language model)",
    "GPT-4",
    "Large language model"
  ]
}
```

---

### `POST /api/v1/crawl/fetch` — Fetch 1 bài theo tiêu đề

Dùng khi: Biết chính xác tên bài muốn lấy.

```bash
curl -X POST http://localhost:8000/api/v1/crawl/fetch \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Transformer (deep learning)",
    "lang": "en"
  }'
```

**Response:**
```json
{
  "article_id": 1,
  "title": "Transformer (deep learning)",
  "url": "https://en.wikipedia.org/wiki/Transformer_(deep_learning)",
  "lang": "en",
  "created": true
}
```

`created: false` = bài đã tồn tại trong DB, không tạo mới.

---

### `POST /api/v1/crawl/topic` — Crawl theo chủ đề

Dùng khi: Muốn thu thập nhiều bài xoay quanh 1 chủ đề.

```bash
curl -X POST http://localhost:8000/api/v1/crawl/topic \
  -H "Content-Type: application/json" \
  -d '{
    "keyword": "Large language model",
    "limit": 10,
    "lang": "en"
  }'
```

**Response:**
```json
{
  "keyword": "Large language model",
  "pages_found": 10,
  "pages_saved": 8,
  "failed": 0,
  "articles": [...]
}
```

`pages_saved < pages_found` = một số bài đã có trong DB từ trước.

---

### `POST /api/v1/crawl/urls` — Crawl từ danh sách URLs

Dùng khi: Đã có danh sách URLs cụ thể, hoặc mix nhiều ngôn ngữ.

```bash
curl -X POST http://localhost:8000/api/v1/crawl/urls \
  -H "Content-Type: application/json" \
  -d '{
    "urls": [
      "https://en.wikipedia.org/wiki/Machine_learning",
      "https://vi.wikipedia.org/wiki/Học_máy",
      "https://ja.wikipedia.org/wiki/機械学習",
      "https://en.wikipedia.org/wiki/Deep_learning"
    ]
  }'
```

**Lưu ý:** Ngôn ngữ tự detect từ subdomain (vi.wikipedia.org → lang=vi).
Tối đa 100 URLs per request.

---

### `POST /api/v1/crawl/keywords` — Crawl nhiều keyword

Dùng khi: Muốn thu thập dữ liệu hàng loạt về nhiều chủ đề.

```bash
curl -X POST http://localhost:8000/api/v1/crawl/keywords \
  -H "Content-Type: application/json" \
  -d '{
    "keywords": [
      "Machine learning",
      "Deep learning",
      "Natural language processing",
      "Computer vision",
      "Reinforcement learning"
    ],
    "limit_per_keyword": 5,
    "lang": "en"
  }'
```

**Lưu ý:** Tự động deduplicate — nếu "Deep learning" xuất hiện kết quả của cả 2 keyword, chỉ lưu 1 lần.
Tối đa 20 keywords per request.

---

## Nhóm 2: ARTICLES — Quản lý bài viết

### `GET /api/v1/articles/stats`

```bash
curl http://localhost:8000/api/v1/articles/stats
```
```json
{
  "total": 25,
  "indexed": 15,
  "not_indexed": 10
}
```

### `GET /api/v1/articles/?page=1&page_size=10`

```bash
curl "http://localhost:8000/api/v1/articles/?page=1&page_size=5"
```

### `GET /api/v1/articles/{id}`

```bash
curl http://localhost:8000/api/v1/articles/1
```

### `DELETE /api/v1/articles/{id}`

```bash
curl -X DELETE http://localhost:8000/api/v1/articles/1
```

---

## Nhóm 3: INDEX — Đưa bài vào Elasticsearch

### Workflow chuẩn: Submit → Poll

**Bước 1: Submit job**
```bash
curl -X POST http://localhost:8000/api/v1/index/run \
  -H "Content-Type: application/json" \
  -d '{"batch_size": 100}'
```
```json
{
  "job_id": "d43540e8-0da8-47e4-a92e-0e3cd548e4bb",
  "status": "pending",
  "message": "Job đã được tạo. Poll GET /api/v1/index/status/..."
}
```

**Bước 2: Poll tiến trình (lặp mỗi 5-10 giây)**
```bash
JOB_ID="d43540e8-0da8-47e4-a92e-0e3cd548e4bb"
curl http://localhost:8000/api/v1/index/status/$JOB_ID
```

Khi đang chạy:
```json
{
  "status": "running",
  "progress": {
    "articles_processed": 45,
    "chunks_indexed": 6300,
    "total_unindexed": 100,
    "percent": 45.0
  }
}
```

Khi xong:
```json
{
  "status": "done",
  "result": { "articles_processed": 100, "chunks_indexed": 14000 },
  "elapsed_seconds": 87.3
}
```

### `GET /api/v1/index/jobs` — Lịch sử jobs

```bash
curl http://localhost:8000/api/v1/index/jobs
```

### `GET /api/v1/index/stats` — Thống kê ES

```bash
curl http://localhost:8000/api/v1/index/stats
```
```json
{
  "index_name": "wiki_chunks",
  "total_chunks": 14523,
  "size_bytes": 87654321,
  "exists": true
}
```

### `POST /api/v1/index/reset` — Reset toàn bộ

```bash
curl -X POST http://localhost:8000/api/v1/index/reset
```
⚠️ **Cảnh báo:** Xóa toàn bộ Elasticsearch index. Phải chạy lại `/index/run` để rebuild.

---

## Nhóm 4: SEARCH & RAG

### `POST /api/v1/search/fulltext` — BM25

Tìm theo từ khoá chính xác.

```bash
curl -X POST http://localhost:8000/api/v1/search/fulltext \
  -H "Content-Type: application/json" \
  -d '{"query": "attention mechanism transformer", "top_k": 5}'
```

### `POST /api/v1/search/semantic` — Vector

Tìm theo ngữ nghĩa (không cần đúng từ khoá).

```bash
curl -X POST http://localhost:8000/api/v1/search/semantic \
  -H "Content-Type: application/json" \
  -d '{"query": "how does self-attention work", "top_k": 5}'
```

### `POST /api/v1/search/hybrid` — BM25 + Vector + RRF (khuyến nghị)

```bash
curl -X POST http://localhost:8000/api/v1/search/hybrid \
  -H "Content-Type: application/json" \
  -d '{"query": "transformer architecture explained", "top_k": 5}'
```

**Response (chung cho 3 chế độ search):**
```json
{
  "query": "transformer architecture explained",
  "mode": "hybrid",
  "results": [
    {
      "id": "abc123",
      "score": 0.032786,
      "text": "The Transformer is a deep learning architecture...",
      "title": "Transformer (deep learning)",
      "url": "https://en.wikipedia.org/wiki/Transformer_(deep_learning)",
      "chunk_index": 0
    },
    ...
  ]
}
```

### `POST /api/v1/search/ask` — RAG full pipeline (cần OpenAI key)

```bash
curl -X POST http://localhost:8000/api/v1/search/ask \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the difference between BERT and GPT?"}'
```

**Response:**
```json
{
  "query": "What is the difference between BERT and GPT?",
  "answer": "BERT (Bidirectional Encoder Representations from Transformers) and GPT (Generative Pre-trained Transformer) differ primarily in their training objectives and architecture. BERT uses a bidirectional encoder that processes text in both directions simultaneously, making it excellent for understanding tasks...",
  "sources": [
    {
      "id": "...",
      "score": 0.032786,
      "text": "BERT is designed to pretrain deep bidirectional representations...",
      "title": "BERT (language model)",
      "url": "https://en.wikipedia.org/wiki/BERT_(language_model)",
      "chunk_index": 2
    }
  ]
}
```

---

## Script tự động hóa toàn bộ workflow

```bash
#!/bin/bash
# Chạy toàn bộ pipeline từ đầu đến cuối

BASE="http://localhost:8000/api/v1"

echo "=== Bước 1: Crawl ==="
curl -s -X POST $BASE/crawl/keywords \
  -H "Content-Type: application/json" \
  -d '{
    "keywords": ["Machine learning", "Deep learning", "Transformer"],
    "limit_per_keyword": 5
  }' | python3 -m json.tool

echo ""
echo "=== Bước 2: Submit index job ==="
JOB_ID=$(curl -s -X POST $BASE/index/run \
  -H "Content-Type: application/json" \
  -d '{"batch_size": 100}' | python3 -c "import json,sys; print(json.load(sys.stdin)['job_id'])")
echo "Job ID: $JOB_ID"

echo ""
echo "=== Bước 3: Poll until done ==="
while true; do
  STATUS=$(curl -s $BASE/index/status/$JOB_ID | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['status'], d['progress'].get('percent',''))")
  echo "Status: $STATUS"
  if [[ $STATUS == done* || $STATUS == failed* ]]; then break; fi
  sleep 5
done

echo ""
echo "=== Bước 4: Test search ==="
curl -s -X POST $BASE/search/hybrid \
  -H "Content-Type: application/json" \
  -d '{"query": "How does attention mechanism work?", "top_k": 3}' \
  | python3 -m json.tool
```
