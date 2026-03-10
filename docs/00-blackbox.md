# 00 — Nhìn từ bên ngoài: Hệ thống là gì?

> Tư duy: Trước khi hiểu bên trong, hãy hiểu **hệ thống làm gì** từ góc nhìn người dùng.
> Coi toàn bộ như một hộp đen — bạn chỉ thấy input và output.

---

## Hệ thống giải quyết bài toán gì?

**Bài toán:** Bạn muốn hỏi một câu hỏi phức tạp và nhận được câu trả lời có nguồn gốc rõ ràng, dựa trên kiến thức từ Wikipedia — không phải từ trí nhớ của AI (có thể sai/cũ), mà từ nội dung Wikipedia thực tế.

**Ví dụ thực tế:**
```
Bạn hỏi: "Cơ chế attention trong Transformer hoạt động như thế nào?"

Hệ thống trả lời:
  "The attention mechanism allows the model to focus on different parts
   of the input sequence... [giải thích chi tiết]
   
   Nguồn: [1] Transformer (deep learning) - wikipedia.org/wiki/Transformer
          [2] Attention mechanism - wikipedia.org/wiki/Attention_(machine_learning)"
```

Điểm khác biệt với ChatGPT thông thường: **câu trả lời được truy xuất từ nguồn Wikipedia cụ thể bạn đã nạp vào**, không phải từ training data ngẫu nhiên.

---

## Blackbox view — 3 hộp đen lớn

```
┌─────────────────────────────────────────────────────────────────────┐
│                        WIKIPEDIA RAG SYSTEM                         │
│                                                                     │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────────┐  │
│  │   HỘP ĐEN 1  │    │   HỘP ĐEN 2  │    │      HỘP ĐEN 3       │  │
│  │              │    │              │    │                      │  │
│  │    CRAWL     │───►│    INDEX     │───►│   SEARCH & ANSWER    │  │
│  │              │    │              │    │                      │  │
│  │ INPUT:       │    │ INPUT:       │    │ INPUT:               │  │
│  │  keyword/URL │    │  batch_size  │    │  câu hỏi (text)      │  │
│  │              │    │              │    │                      │  │
│  │ OUTPUT:      │    │ OUTPUT:      │    │ OUTPUT:              │  │
│  │  bài viết    │    │  job_id +    │    │  câu trả lời +       │  │
│  │  đã lưu      │    │  tiến trình  │    │  nguồn trích dẫn     │  │
│  └──────────────┘    └──────────────┘    └──────────────────────┘  │
│         │                   │                      ▲               │
│         ▼                   ▼                      │               │
│    PostgreSQL          Elasticsearch          Elasticsearch         │
│    (raw text)         (searchable chunks)    (query + LLM)         │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Hộp đen 1: CRAWL

| | Chi tiết |
|---|---|
| **Nhận vào** | keyword (vd: "Machine learning"), URL Wikipedia, hoặc danh sách cả hai |
| **Làm gì bên trong** | Gọi Wikipedia API, tải nội dung bài viết |
| **Trả ra** | Danh sách bài viết đã lưu vào database, kèm `article_id` |
| **Cần gì để chạy** | Kết nối internet, PostgreSQL |

**Input/Output cụ thể:**
```
Input:  { "keywords": ["AI", "Deep learning"], "limit_per_keyword": 5 }
Output: { "pages_saved": 8, "articles": [ {id:1, title:"...", url:"..."}, ... ] }
```

---

## Hộp đen 2: INDEX

| | Chi tiết |
|---|---|
| **Nhận vào** | `batch_size` (số bài xử lý mỗi lần) |
| **Làm gì bên trong** | Đọc bài từ PostgreSQL, xử lý, đưa lên Elasticsearch |
| **Trả ra** | `job_id` (ngay lập tức), có thể poll tiến trình |
| **Cần gì để chạy** | PostgreSQL có dữ liệu, Elasticsearch đang chạy |

**Input/Output cụ thể:**
```
Input:  { "batch_size": 100 }
Output: { "job_id": "abc-123", "status": "pending" }

Poll: GET /index/status/abc-123
→ { "status": "running", "progress": { "percent": 45.0, "chunks_indexed": 620 } }
→ { "status": "done",    "result":   { "articles_processed": 10, "chunks_indexed": 1384 } }
```

---

## Hộp đen 3: SEARCH & ANSWER

| | Chi tiết |
|---|---|
| **Nhận vào** | Câu hỏi dạng tự nhiên (text) |
| **Làm gì bên trong** | Tìm kiếm Elasticsearch, tổng hợp bằng LLM |
| **Trả ra** | Câu trả lời + danh sách nguồn |
| **Cần gì để chạy** | Elasticsearch có data, OpenAI API key |

**Input/Output cụ thể:**
```
Input:  { "query": "How does attention mechanism work?" }
Output: {
  "answer": "The attention mechanism allows...",
  "sources": [
    { "title": "Transformer", "url": "...", "text": "...", "score": 0.0312 },
    { "title": "Attention (ML)", "url": "...", "text": "...", "score": 0.0298 }
  ]
}
```

---

## Trình tự bắt buộc

```
CRAWL phải chạy trước INDEX
INDEX phải chạy trước SEARCH

Lý do: SEARCH tìm trong Elasticsearch.
       Elasticsearch chỉ có data nếu INDEX đã chạy.
       INDEX chỉ có data để xử lý nếu CRAWL đã chạy.
```

---

## Các chế độ tìm kiếm (cùng interface, khác thuật toán)

| Chế độ | Nhận vào | Trả ra | Dùng khi nào |
|---|---|---|---|
| `fulltext` | query, top_k | chunks | Tìm từ khoá chính xác |
| `semantic` | query, top_k | chunks | Tìm theo ý nghĩa |
| `hybrid` | query, top_k | chunks | Tốt nhất, kết hợp cả hai |
| `ask` | query | answer + sources | Muốn câu trả lời tự nhiên |

---

## Điều gì xảy ra nếu bỏ qua bước nào?

| Bỏ qua | Hậu quả |
|---|---|
| Không CRAWL | INDEX không có gì để xử lý → "0 articles processed" |
| Không INDEX | SEARCH trả về rỗng → "Không tìm thấy thông tin" |
| Không có OpenAI key | `/search/ask` lỗi, nhưng `/search/hybrid` vẫn chạy được |
