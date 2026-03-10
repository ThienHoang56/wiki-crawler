# Tài liệu kỹ thuật — Wikipedia RAG System

Thư mục này giải thích toàn bộ hệ thống từ góc nhìn người mới tiếp cận.
Tư duy: **blackbox → architecture → data flow → implementation → usage → config**.

---

## Đọc theo thứ tự này

| File | Nội dung | Khi nào đọc |
|---|---|---|
| [00-blackbox.md](./00-blackbox.md) | Hệ thống làm gì? Input/Output của mỗi phần | **Đầu tiên** — hiểu big picture |
| [01-architecture.md](./01-architecture.md) | Tại sao chọn PostgreSQL, ES, hybrid search? | Sau khi hiểu blackbox |
| [02-data-flow.md](./02-data-flow.md) | Một bài viết đi qua hệ thống như thế nào? | Để hiểu pipeline end-to-end |
| [03-pipeline-pseudocode.md](./03-pipeline-pseudocode.md) | Pseudo code cho từng bước xử lý | Trước khi đọc code thực |
| [04-api-guide.md](./04-api-guide.md) | Ví dụ curl cho mọi endpoint | Khi muốn sử dụng/test API |
| [05-config-explained.md](./05-config-explained.md) | Ý nghĩa và trade-off của mọi param `.env` | Khi muốn tune hệ thống |

---

## Câu hỏi thường gặp

**Q: Tại sao search trả về rỗng?**
→ Kiểm tra thứ tự: CRAWL → INDEX → SEARCH. Thiếu bước nào là fail.

**Q: Tại sao `/search/ask` lỗi nhưng `/search/hybrid` vẫn chạy?**
→ `ask` cần OpenAI API key. `hybrid` chỉ cần Elasticsearch.

**Q: Muốn crawl tiếng Việt?**
→ Thêm `"lang": "vi"` vào request, hoặc đổi `CRAWLER_WIKI_LANG=vi` trong `.env`.

**Q: Index job chạy mãi không xong?**
→ Kiểm tra: `GET /api/v1/index/status/{job_id}`. Xem `progress.percent`.

**Q: Muốn đổi embedding model?**
→ Đổi `EMBEDDING_MODEL` và `EMBEDDING_DIMS` trong `.env`, reset ES (`POST /index/reset`), chạy lại index job.
