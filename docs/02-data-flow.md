# 02 — Luồng dữ liệu: Một mẩu text đi qua hệ thống như thế nào?

> Tư duy: Theo dõi **một bài viết Wikipedia** từ lúc được crawl đến khi trở thành câu trả lời.
> Đây là "hành trình của dữ liệu" — giúp hiểu tại sao mỗi bước cần tồn tại.

---

## Hành trình đầy đủ

```
Wikipedia Article "Machine Learning"
          │
          │  (1) CRAWL
          ▼
┌─────────────────────────────────────────────────────────────┐
│ raw_text = "Machine learning (ML) is a field of study..."  │
│ (≈ 50,000 ký tự, bao gồm markup wiki: [[links]], ==headings==) │
└─────────────────────────────────────────────────────────────┘
          │
          │  Lưu vào PostgreSQL
          │  articles(id=1, title="Machine learning",
          │            url="https://en.wikipedia.org/...",
          │            raw_text="...", is_indexed=False)
          │
          │  (2) CLEAN
          ▼
┌─────────────────────────────────────────────────────────────┐
│ clean_text = "Machine learning ML is a field of study..."  │
│ (markup bị xóa, text thuần)                                 │
└─────────────────────────────────────────────────────────────┘
          │
          │  (3) CHUNK
          ▼
┌─────────────────────────────────────────────────────────────┐
│ chunks = [                                                   │
│   "Machine learning ML is a field of study in artificial...",  │
│   "...intelligence. The study of mathematical optimization...", │
│   "...Supervised learning algorithms build a mathematical...",  │
│   ... (≈ 100 chunks × 500 ký tự)                             │
│ ]                                                            │
└─────────────────────────────────────────────────────────────┘
          │
          │  (4) EMBED (batch)
          ▼
┌─────────────────────────────────────────────────────────────┐
│ embeddings = [                                               │
│   [0.023, -0.145, 0.078, ..., 0.031],  ← 384 số float       │
│   [0.051, -0.092, 0.114, ..., -0.018], ← chunk 2            │
│   ...                                                        │
│ ]  ← mỗi chunk trở thành 1 vector 384 chiều                 │
└─────────────────────────────────────────────────────────────┘
          │
          │  (5) BULK INDEX vào Elasticsearch
          ▼
┌─────────────────────────────────────────────────────────────┐
│ ES document (mỗi chunk là 1 document):                       │
│ {                                                            │
│   "text": "Machine learning ML is a field...",              │
│   "embedding": [0.023, -0.145, ..., 0.031],                  │
│   "title": "Machine learning",                               │
│   "url": "https://en.wikipedia.org/wiki/Machine_learning",  │
│   "chunk_index": 0,                                          │
│   "lang": "en"                                               │
│ }                                                            │
└─────────────────────────────────────────────────────────────┘
          │
          │  PostgreSQL: is_indexed = True
          │
          ▼
     [READY FOR SEARCH]
```

---

## Hành trình của một câu hỏi

```
User hỏi: "What is machine learning?"
          │
          │  (A) EMBED QUERY
          ▼
query_vector = [0.019, -0.132, 0.085, ..., 0.027]   ← 384 chiều
          │
          │
     ┌────┴────┐
     │         │
     │  (B1)   │  (B2)
     ▼         ▼
  BM25       Vector
  search     search
     │         │
     │ top-20  │ top-20
     │ chunks  │ chunks
     │         │
     └────┬────┘
          │
          │  (C) RRF FUSION
          ▼
┌─────────────────────────────────────────────────────────┐
│ Kết hợp 2 danh sách bằng rank:                          │
│                                                         │
│ "Machine learning is..." rank_BM25=1, rank_vec=1        │
│   → score = 1/(60+1) + 1/(60+1) = 0.0328  ← cao nhất  │
│                                                         │
│ "ML algorithms include..." rank_BM25=3, rank_vec=2      │
│   → score = 1/63 + 1/62 = 0.0320                       │
│                                                         │
│ → top-3 chunks được chọn                                │
└─────────────────────────────────────────────────────────┘
          │
          │  (D) BUILD PROMPT
          ▼
┌─────────────────────────────────────────────────────────┐
│ "Use the following Wikipedia context to answer...       │
│                                                         │
│ [1] Machine learning                                    │
│ Machine learning ML is a field of study in artificial   │
│ intelligence...                                         │
│                                                         │
│ [2] Machine learning                                    │
│ ML algorithms include supervised, unsupervised...       │
│                                                         │
│ [3] Machine learning                                    │
│ Applications include computer vision, NLP...            │
│                                                         │
│ Question: What is machine learning?                     │
│ Answer:"                                                │
└─────────────────────────────────────────────────────────┘
          │
          │  (E) LLM GENERATION
          ▼
┌─────────────────────────────────────────────────────────┐
│ {                                                       │
│   "answer": "Machine learning (ML) is a field of       │
│    artificial intelligence that gives computers the     │
│    ability to learn without being explicitly           │
│    programmed. It focuses on...",                       │
│                                                         │
│   "sources": [                                          │
│     { "title": "Machine learning", "score": 0.0328 },  │
│     { "title": "Machine learning", "score": 0.0320 },  │
│     { "title": "Machine learning", "score": 0.0308 }   │
│   ]                                                     │
│ }                                                       │
└─────────────────────────────────────────────────────────┘
```

---

## Tại sao cần bước CLEAN?

Nội dung Wikipedia thô trông như thế này:
```
== History ==
The term ''machine learning'' was coined in {{IPA|1959}} by
[[Arthur Samuel]].<ref>{{cite journal|...}}</ref>
It is seen as a subset of [[artificial intelligence]].
```

Sau khi CLEAN:
```
History
The term machine learning was coined in 1959 by Arthur Samuel.
It is seen as a subset of artificial intelligence.
```

**Lý do:** Embedding model học từ ngôn ngữ tự nhiên, không hiểu `[[Arthur Samuel]]` hay `{{cite journal}}`. Nếu để markup, vector sẽ bị nhiễu và search kém chính xác.

---

## Tại sao cần bước CHUNK?

```
Bài viết "Machine Learning" ≈ 50,000 ký tự (≈ 10,000 từ)

Nếu đưa cả bài vào 1 embedding:
  - Model chỉ encode được tối đa 512 token (≈ 400 từ)
  - Phần còn lại bị cắt bỏ
  - Vector không đại diện cho nội dung đa dạng của bài

Nếu chunk thành đoạn 500 ký tự:
  - ≈ 100 chunks per bài
  - Mỗi chunk = 1 khái niệm cụ thể
  - Khi search, tìm đúng đoạn liên quan thay vì toàn bài
  - Câu trả lời LLM ngắn gọn và chính xác hơn
```

**Overlap 50 ký tự:** Để không cắt đứt câu giữa 2 chunks — tránh mất ngữ cảnh.

---

## Tại sao Bulk index thay vì index từng document?

```python
# Cách chậm (single index):
for chunk in chunks:
    es.index(index="wiki_chunks", document=chunk)
    # Mỗi call = 1 HTTP round-trip = ~10-50ms
# 1000 chunks × 30ms = 30 giây

# Cách nhanh (bulk):
es.helpers.bulk(es_client, actions=[...all chunks...])
# 1 HTTP round-trip = ~200-500ms
# 1000 chunks = 0.5 giây
# Nhanh hơn 60x
```

---

## Trạng thái `is_indexed` — Tại sao cần?

```
PostgreSQL: articles table
┌────┬─────────────────────┬────────────┐
│ id │ title               │ is_indexed │
├────┼─────────────────────┼────────────┤
│  1 │ Machine learning    │   True     │ ← đã index, bỏ qua
│  2 │ Deep learning       │   True     │ ← đã index, bỏ qua
│  3 │ Transformer         │   False    │ ← chưa index, xử lý
│  4 │ BERT                │   False    │ ← chưa index, xử lý
└────┴─────────────────────┴────────────┘

Khi chạy index job:
  - Chỉ lấy bài có is_indexed = False
  - Sau khi index thành công → set is_indexed = True
  - Lần sau chạy job không xử lý lại bài đã xong
  - Nếu job crash giữa chừng → bài chưa done vẫn là False → tự recover
```
