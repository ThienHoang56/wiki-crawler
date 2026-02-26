from fastapi import FastAPI
from src.routers import crawl_router, article_router, index_router, search_router

app = FastAPI(
    title="Wikipedia RAG API",
    description=(
        "Hệ thống RAG từ Wikipedia.\n\n"
        "**Luồng sử dụng:**\n"
        "1. `/crawl` — Cào bài viết Wikipedia → lưu vào PostgreSQL\n"
        "2. `/articles` — Xem và quản lý bài viết đã cào\n"
        "3. `/index` — Index bài viết vào Elasticsearch (Offline Pipeline)\n"
        "4. `/search` — Tìm kiếm và hỏi đáp RAG với LLM"
    ),
    version="1.0.0",
)

app.include_router(crawl_router.router)
app.include_router(article_router.router)
app.include_router(index_router.router)
app.include_router(search_router.router)

@app.get("/", tags=["Health"])
def health_check():
    return {"status": "ok", "message": "Wikipedia RAG API đang hoạt động!"}
