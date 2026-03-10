# 05 — Config: Ý nghĩa và cách chỉnh từng tham số

> Không có magic numbers trong code — tất cả có thể điều chỉnh qua `.env`.
> File này giải thích **tại sao** mỗi param tồn tại và **khi nào** cần thay đổi.

---

## Cấu trúc `.env`

```bash
# ─── Database ────────────────────────────────────────────────────────
DATABASE_URL=postgresql://admin:password@localhost:5432/wiki_db

# ─── Elasticsearch ───────────────────────────────────────────────────
ES_HOST=http://localhost:9200
ES_USER=
ES_PASSWORD=
INDEX_NAME=wiki_chunks

# ─── LLM ─────────────────────────────────────────────────────────────
OPENAI_API_KEY=sk-...
LLM_MODEL=gpt-4o-mini

# ─── Embedding ───────────────────────────────────────────────────────
EMBEDDING_MODEL=all-MiniLM-L6-v2
EMBEDDING_DIMS=384
CHUNK_SIZE=500
CHUNK_OVERLAP=50

# ─── Crawler ─────────────────────────────────────────────────────────
CRAWLER_WIKI_LANG=en
CRAWLER_CONCURRENCY=3
CRAWLER_RATE_LIMIT_SECONDS=1.0
CRAWLER_TIMEOUT_SECONDS=15.0
CRAWLER_RETRY_COUNT=3
CRAWLER_RETRY_BACKOFF=2.0
CRAWLER_USER_AGENT=wiki-rag-bot/1.0 (...)

# ─── Search & RAG ────────────────────────────────────────────────────
SEARCH_CANDIDATE_POOL=20
RRF_K=60
RAG_HYBRID_POOL=10
RAG_TOP_K_CONTEXT=3
```

---

## Nhóm: Embedding

### `EMBEDDING_MODEL`
**Giá trị mặc định:** `all-MiniLM-L6-v2`

| Model | Dims | Tốc độ | Chất lượng | Khi nào dùng |
|---|---|---|---|---|
| `all-MiniLM-L6-v2` | 384 | ⚡ Nhanh nhất | Tốt | Default, production |
| `all-mpnet-base-v2` | 768 | 🐢 Chậm ~3x | Tốt hơn | Khi cần recall cao hơn |
| `multi-qa-MiniLM-L6-cos-v1` | 384 | ⚡ Nhanh | Tốt cho Q&A | Hệ thống Q&A thuần túy |

### `EMBEDDING_DIMS`
**Phải khớp với model!** Nếu đổi model mà quên đổi dims → ES mapping sai → crash.

```
all-MiniLM-L6-v2  → EMBEDDING_DIMS=384
all-mpnet-base-v2 → EMBEDDING_DIMS=768
```

⚠️ Sau khi đổi model + dims: **phải reset ES index và re-index toàn bộ**.

### `CHUNK_SIZE`
**Giá trị mặc định:** `500` (ký tự)

```
Quá nhỏ (200): chunk không đủ ngữ cảnh → answer thiếu thông tin
Quá lớn (2000): vượt max_seq_length của model → thông tin bị cắt
Tốt nhất: 400-600 ký tự (≈ 1-2 đoạn văn)
```

### `CHUNK_OVERLAP`
**Giá trị mặc định:** `50` (ký tự)

Số ký tự lặp lại giữa 2 chunks liên tiếp.

```
Không có overlap (0): câu bị cắt đứt ở ranh giới chunk → mất ngữ cảnh
Overlap quá lớn (200): lưu trùng nhiều → ES lớn, search có nhiễu
Tốt nhất: 10-15% của CHUNK_SIZE
```

---

## Nhóm: Crawler

### `CRAWLER_WIKI_LANG`
**Giá trị mặc định:** `en`

Ngôn ngữ Wikipedia mặc định khi không truyền `lang` trong API.

```
en  → english.wikipedia.org
vi  → vietnamese (vi.wikipedia.org)
ja  → japanese
zh  → chinese
fr  → french
de  → german
```

**Lưu ý:** Ngôn ngữ này cũng quyết định ES analyzer được dùng khi tạo index:
```
en → "english" analyzer (stemming: "running" → "run")
vi → "standard" analyzer (không có stemmer cho tiếng Việt built-in)
zh/ja → "cjk" analyzer (tokenize từng ký tự cho Chinese/Japanese)
```

### `CRAWLER_CONCURRENCY`
**Giá trị mặc định:** `3`

Số request Wikipedia đồng thời tối đa.

```
1: Sequential, an toàn nhất nhưng chậm nhất
3: Balance tốt (mặc định)
5: Nhanh hơn, vẫn trong giới hạn Wikipedia
10+: Có thể bị rate-limit hoặc block IP
```

**Wikipedia API guidelines:** Không quá 200 req/s, nhưng để an toàn nên giữ ≤ 5 concurrent.

### `CRAWLER_RATE_LIMIT_SECONDS`
**Giá trị mặc định:** `1.0`

Thời gian chờ tối thiểu giữa các requests.

```
Trong code: sleep(rate_limit / concurrency)
→ concurrency=3, rate_limit=1.0: mỗi slot chờ 0.33s
→ Tổng throughput: ~3 req/giây (an toàn)
```

### `CRAWLER_RETRY_COUNT` + `CRAWLER_RETRY_BACKOFF`
**Mặc định:** `3` retries, backoff `2.0` giây

```
Khi request thất bại:
  Lần 1: Thử lại sau 2.0 giây
  Lần 2: Thử lại sau 4.0 giây  (2.0 × 2)
  Lần 3: Thử lại sau 6.0 giây  (2.0 × 3)
  → Raise exception nếu vẫn thất bại
```

---

## Nhóm: Search & RAG

### `SEARCH_CANDIDATE_POOL`
**Giá trị mặc định:** `20`

Số chunks lấy từ mỗi phương pháp (BM25 và Vector) trước khi RRF fusion.

```
Tăng lên 50: Recall cao hơn (ít bỏ sót kết quả hay), chậm hơn một chút
Giảm xuống 10: Nhanh hơn, có thể miss một số kết quả liên quan
```

### `RRF_K`
**Giá trị mặc định:** `60`

Hằng số trong công thức RRF: `score = 1 / (k + rank)`

```
k=60 (theo paper gốc Cormack et al. 2009):
  - rank=1:  1/61 = 0.0164  ← không quá ưu tiên rank đầu
  - rank=10: 1/70 = 0.0143  ← sự chênh lệch nhỏ
  - rank=20: 1/80 = 0.0125

k=10 (aggressive):
  - rank=1:  1/11 = 0.0909  ← ưu tiên rất mạnh rank đầu
  - rank=10: 1/20 = 0.0500
  - rank=20: 1/30 = 0.0333  ← khoảng cách lớn hơn nhiều

Khuyến nghị: giữ k=60 trừ khi có lý do đặc biệt.
```

### `RAG_HYBRID_POOL`
**Giá trị mặc định:** `10`

Số chunks hybrid search retrieve trước khi đưa vào reranker.

```
Pool lớn hơn (20): Reranker có nhiều lựa chọn hơn → quality tốt hơn
Pool nhỏ hơn (5): Nhanh hơn, nhưng có thể miss context quan trọng
```

### `RAG_TOP_K_CONTEXT`
**Giá trị mặc định:** `3`

Số chunks cuối cùng đưa vào prompt LLM.

```
1: Ngắn nhất, focused nhưng có thể miss thông tin
3: Balance (mặc định)
5: Nhiều context hơn nhưng:
   - Prompt dài hơn → token nhiều hơn → tốn tiền hơn
   - LLM có thể bị "lost in the middle" (quên context ở giữa)

Công thức tính token estimate:
  3 chunks × 500 chars ÷ 4 ≈ 375 tokens context
  Prompt overhead: ~200 tokens
  Answer: ~300 tokens
  Total: ~875 tokens/request
```

---

## Quan hệ giữa các tham số

```
CHUNK_SIZE=500
    ↓
Mỗi bài ~100 chunks
    ↓
EMBEDDING_DIMS=384 → mỗi chunk = 1 vector [384 floats × 4 bytes = 1.5KB]
    ↓
100 bài × 100 chunks × 1.5KB = ~15MB ES storage per 100 articles
    ↓
SEARCH_CANDIDATE_POOL=20 → lấy 20 BM25 + 20 vector = 40 candidates
    ↓
RRF_K=60 → kết hợp → RAG_HYBRID_POOL=10 best
    ↓
RAG_TOP_K_CONTEXT=3 → đưa 3 chunks vào LLM
```

---

## Kịch bản: Muốn hệ thống chất lượng cao hơn

```bash
# Dùng model lớn hơn cho embedding
EMBEDDING_MODEL=all-mpnet-base-v2
EMBEDDING_DIMS=768

# Chunk nhỏ hơn để granular hơn
CHUNK_SIZE=400
CHUNK_OVERLAP=80

# Pool lớn hơn để recall cao hơn
SEARCH_CANDIDATE_POOL=50
RAG_HYBRID_POOL=20
RAG_TOP_K_CONTEXT=5

# LLM tốt hơn
LLM_MODEL=gpt-4o
```

**Trade-off:** Chậm hơn ~2-3x, tốn nhiều RAM hơn (768-dim), và tốn tiền OpenAI hơn.

## Kịch bản: Muốn hệ thống nhanh nhất

```bash
EMBEDDING_MODEL=all-MiniLM-L6-v2    # Nhanh nhất
EMBEDDING_DIMS=384
CHUNK_SIZE=600                        # Chunk to → ít chunk hơn
SEARCH_CANDIDATE_POOL=10             # Pool nhỏ
RAG_HYBRID_POOL=5
RAG_TOP_K_CONTEXT=2                  # Ít token LLM
LLM_MODEL=gpt-4o-mini                # Model nhanh + rẻ
```
