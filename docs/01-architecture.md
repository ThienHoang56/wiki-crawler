# 01 — Kiến trúc: Tại sao thiết kế như vậy?

> Tư duy: Sau khi hiểu hệ thống làm gì, câu hỏi tiếp theo là **tại sao** chọn các thành phần này.
> Mỗi quyết định thiết kế đều có lý do — section này giải thích reasoning đằng sau.

---

## Toàn cảnh kiến trúc

```
┌─── DATA INGESTION ──────────────────────────────────────────────────┐
│                                                                      │
│   Wikipedia API                                                      │
│        │                                                             │
│   [ WikiCrawler ]  ←── httpx (async), Semaphore, retry              │
│        │                                                             │
│        ▼                                                             │
│   PostgreSQL ──── Table: articles                                    │
│   (id, title, url, raw_text, is_indexed, created_at)                │
└──────────────────────────────────────────────────────────────────────┘
         │
         │ (is_indexed = False)
         ▼
┌─── RAG INDEXING PIPELINE ───────────────────────────────────────────┐
│                                                                      │
│   [ TextCleaner ]  ── strip wiki markup, HTML artifacts             │
│        │                                                             │
│   [ TextChunker ]  ── RecursiveCharacterTextSplitter (500 chars)    │
│        │                                                             │
│   [ Embedder ]     ── SentenceTransformer all-MiniLM-L6-v2 (384d)  │
│        │                                                             │
│   [ ES Bulk ]      ── bulk API, 500 docs/batch                      │
│        │                                                             │
│   Elasticsearch ─── index: wiki_chunks                              │
│   ├── text field (BM25 full-text)                                   │
│   └── embedding field (dense_vector 384-dim, cosine)                │
└──────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─── SEARCH & RETRIEVAL ──────────────────────────────────────────────┐
│                                                                      │
│   User Query                                                         │
│        │                                                             │
│        ├──► [ BM25 search ]   → top-20 chunks (keyword match)       │
│        │                                                             │
│        ├──► [ Vector search ] → top-20 chunks (semantic match)      │
│        │         (query → embed → cosine similarity)                │
│        │                                                             │
│        └──► [ RRF Fusion ]    → top-K chunks (combined score)       │
│                  │                                                   │
│             [ Reranker ]  → top-3 chunks (by RRF score)             │
│                  │                                                   │
│             [ LLM ] (OpenAI gpt-4o-mini)                            │
│                  │                                                   │
│             Answer + Sources                                         │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Tại sao dùng PostgreSQL làm staging layer?

**Câu hỏi:** "Tại sao không crawl xong là đưa thẳng vào Elasticsearch?"

**Trả lời:**

```
Nếu không có PostgreSQL:
  - Mất bài viết nếu quá trình index lỗi giữa chừng → phải crawl lại
  - Không thể re-index với model mới mà không crawl lại
  - Không thể xem/quản lý bài viết đã thu thập
  - Không có cờ is_indexed → không biết bài nào đã xử lý

Với PostgreSQL:
  - Raw data được lưu an toàn, độc lập với Elasticsearch
  - Có thể reset/rebuild Elasticsearch index bất kỳ lúc nào
  - Có thể nâng cấp embedding model → re-index mà không crawl lại
  - Quản lý bài viết như một database bình thường
```

**Mô hình:** PostgreSQL là "nguồn sự thật" (source of truth), Elasticsearch là "bản copy có thể tìm kiếm".

---

## Tại sao dùng Elasticsearch thay vì pgvector hoặc Pinecone?

| | Elasticsearch | pgvector | Pinecone |
|---|---|---|---|
| **Full-text BM25** | ✅ Native | ❌ Không có | ❌ Không có |
| **Vector search** | ✅ Dense vector | ✅ | ✅ |
| **Hybrid search** | ✅ (trong cùng index) | ⚠️ Phải kết hợp 2 query | ⚠️ Cần xử lý ngoài |
| **Self-hosted** | ✅ | ✅ (là extension PG) | ❌ Cloud only |
| **Scale** | Tốt | Vừa | Tốt |

**Lý do chọn ES:** Hỗ trợ native cả BM25 và vector trong **cùng một index**, không cần orchestrate 2 hệ thống riêng.

---

## Tại sao cần cả BM25 lẫn Vector search? (Hybrid)

```
BM25 (Full-text):
  GIỎI ở: tìm từ khoá chính xác
    "transformer architecture" → tìm đúng từ "transformer"
  YẾU ở: không hiểu ngữ nghĩa
    "how does self-attention work?" → có thể miss "attention mechanism"

Vector (Semantic):
  GIỎI ở: hiểu ngữ nghĩa, tìm bài viết liên quan dù khác từ
    "how does self-attention work?" → tìm được bài về "attention mechanism"
  YẾU ở: bỏ sót từ khoá quan trọng
    "GPT-4" → embedding có thể không phân biệt với GPT-3

Hybrid = BM25 + Vector + RRF:
  GIỎI ở: lấy điểm mạnh của cả hai, loại bỏ điểm yếu
  Recall cao hơn mỗi cái đơn lẻ ~15-30% (theo các benchmark)
```

---

## Tại sao dùng RRF (Reciprocal Rank Fusion)?

**Vấn đề:** BM25 trả về score 0-∞ (không có upper bound), vector trả về cosine 0-1. Không thể cộng trực tiếp.

**Giải pháp RRF:** Dùng thứ hạng (rank) thay vì điểm số.

```
Công thức: score(doc) = Σ 1 / (k + rank(doc, list_i))
  k = 60 (hằng số, theo paper gốc Cormack 2009)

Ví dụ:
  Doc "Transformer paper":
    - BM25 rank: #2  →  1/(60+2) = 0.0161
    - Vector rank: #1 →  1/(60+1) = 0.0164
    - RRF score: 0.0325  ← cao nhất → xuất hiện đầu

  Doc "BERT paper":
    - BM25 rank: #1  →  0.0164
    - Vector rank: #5 →  1/(60+5) = 0.0154
    - RRF score: 0.0318

Kết quả: "Transformer paper" > "BERT paper" (dù BERT rank cao hơn trong BM25)
```

---

## Tại sao dùng `all-MiniLM-L6-v2` làm embedding model?

| Model | Dims | Speed | Quality | Use case |
|---|---|---|---|---|
| `all-MiniLM-L6-v2` | 384 | ⚡ Rất nhanh | Tốt | General purpose, production |
| `all-mpnet-base-v2` | 768 | 🐢 Chậm hơn | Tốt hơn | Khi cần chất lượng cao hơn |
| `text-embedding-3-small` | 1536 | API call | Tốt nhất | Cloud, có budget |

`all-MiniLM-L6-v2` được chọn vì: **cân bằng tốt giữa tốc độ và chất lượng**, chạy local không cần API.

> **Đổi model:** Chỉ cần đổi `EMBEDDING_MODEL` và `EMBEDDING_DIMS` trong `.env`, sau đó reset ES index và re-index.

---

## Tại sao async + Semaphore cho crawler?

```python
# Cách cũ (sequential):
for title in titles:
    page = fetch_page(title)   # Chờ response rồi mới fetch bài tiếp
    await asyncio.sleep(1)
# → 10 bài × 2 giây = 20 giây

# Cách mới (parallel với semaphore):
semaphore = asyncio.Semaphore(3)  # Tối đa 3 request đồng thời
async def fetch_with_limit(title):
    async with semaphore:
        page = await fetch_page(title)
        await asyncio.sleep(1/3)  # Rate limit chia đều
        return page
results = await asyncio.gather(*[fetch_with_limit(t) for t in titles])
# → 10 bài ÷ 3 concurrent ≈ 7 giây (nhanh hơn ~3x)
```

Semaphore quan trọng vì: Wikipedia có rate limit. Gửi quá nhiều request cùng lúc → bị block IP.

---

## Tại sao background job cho indexing?

**Vấn đề:** Index 1000 bài mất ~5-10 phút. HTTP request timeout sau 30 giây.

```
Cách cũ (synchronous):
  Client → POST /index/run → [chờ 5 phút] → timeout ❌

Cách mới (async job):
  Client → POST /index/run → { job_id: "abc" }  ← trả ngay <1ms
  Client → GET /index/status/abc → { status: "running", percent: 45% }
  Client → GET /index/status/abc → { status: "done", result: {...} }
```

Indexing chạy trong **background thread** riêng, API server không bị block.

---

## Layer pattern: Router → Controller → Service → Repository

Tại sao không viết tất cả vào 1 file?

```
Router    : CHỈ định nghĩa HTTP endpoints, không có logic
Controller: CHỈ xử lý request/response format, gọi service
Service   : Toàn bộ business logic ở đây
Repository: CHỈ tương tác với database (PostgreSQL)
Utility   : Thuật toán độc lập (crawl, clean, chunk, embed)

Lợi ích:
  - Dễ test từng layer độc lập
  - Dễ thay thế: đổi database → chỉ sửa repository
  - Dễ đọc: mỗi file có 1 trách nhiệm rõ ràng
```
