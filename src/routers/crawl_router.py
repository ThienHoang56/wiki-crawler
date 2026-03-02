from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from src.core.database import get_db
from src.controller.crawl_controller import CrawlController
from src.schemas.crawl_schema import (
    SearchTitlesRequest, SearchTitlesResponse,
    FetchArticleRequest, FetchArticleResponse,
    CrawlTopicRequest, CrawlTopicResponse,
    CrawlUrlsRequest, CrawlUrlsResponse,
    CrawlKeywordsRequest, CrawlKeywordsResponse,
)

router = APIRouter(prefix="/api/v1/crawl", tags=["1. Crawl"])
controller = CrawlController()

@router.post(
    "/search-titles",
    response_model=SearchTitlesResponse,
    summary="Tìm tiêu đề Wikipedia theo keyword",
)
async def search_titles(req: SearchTitlesRequest):
    """Tìm kiếm tiêu đề bài viết trên Wikipedia theo từ khoá. **Không lưu gì vào DB.**"""
    return await controller.search_titles(req)

@router.post(
    "/fetch",
    response_model=FetchArticleResponse,
    summary="Fetch 1 bài theo tiêu đề",
)
async def fetch_article(req: FetchArticleRequest, db: Session = Depends(get_db)):
    """Fetch nội dung 1 bài Wikipedia theo tiêu đề và lưu vào PostgreSQL."""
    return await controller.fetch_article(req, db)

@router.post(
    "/topic",
    response_model=CrawlTopicResponse,
    summary="Crawl theo 1 chủ đề (song song)",
)
async def crawl_topic(req: CrawlTopicRequest, db: Session = Depends(get_db)):
    """
    Tìm + fetch nhiều bài theo 1 keyword. Fetch **song song** với rate limit.
    Tối đa `limit` bài (mặc định 5, tối đa 50).
    """
    return await controller.crawl_topic(req, db)

@router.post(
    "/urls",
    response_model=CrawlUrlsResponse,
    summary="Crawl từ danh sách URL (song song)",
)
async def crawl_urls(req: CrawlUrlsRequest, db: Session = Depends(get_db)):
    """
    Nhận danh sách Wikipedia URLs hoặc tiêu đề, fetch **song song**, lưu vào PostgreSQL.
    - Tự động extract tiêu đề từ URL.
    - Tối đa 100 URLs mỗi request.
    - Tự động bỏ qua URL đã có trong DB.

    **Ví dụ (mix ngôn ngữ):**
    ```json
    {
      "urls": [
        "https://en.wikipedia.org/wiki/Machine_learning",
        "https://vi.wikipedia.org/wiki/Học_máy",
        "https://ja.wikipedia.org/wiki/機械学習"
      ]
    }
    ```
    Lang tự động detect từ subdomain URL.
    """
    return await controller.crawl_urls(req, db)

@router.post(
    "/keywords",
    response_model=CrawlKeywordsResponse,
    summary="Crawl nhiều keyword cùng lúc (song song)",
)
async def crawl_keywords(req: CrawlKeywordsRequest, db: Session = Depends(get_db)):
    """
    Nhận nhiều keyword, search + fetch **tất cả song song**, deduplicate, lưu PostgreSQL.
    - Tối đa 20 keyword mỗi request.
    - `limit_per_keyword`: số bài tìm cho mỗi keyword (mặc định 5).
    - Tự động loại bỏ bài trùng giữa các keyword.

    **Ví dụ:**
    ```json
    {
      "keywords": ["Machine learning", "Deep learning", "NLP", "Transformer"],
      "limit_per_keyword": 3
    }
    ```
    """
    return await controller.crawl_keywords(req, db)
