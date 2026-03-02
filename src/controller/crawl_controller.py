from fastapi import HTTPException
from sqlalchemy.orm import Session
from src.services.crawl_service import crawl_service
from src.schemas.crawl_schema import (
    SearchTitlesRequest, SearchTitlesResponse,
    FetchArticleRequest, FetchArticleResponse,
    CrawlTopicRequest, CrawlTopicResponse,
    CrawlUrlsRequest, CrawlUrlsResponse,
    CrawlKeywordsRequest, CrawlKeywordsResponse,
)

def _to_fetch_response(r: dict) -> FetchArticleResponse:
    a = r["article"]
    return FetchArticleResponse(
        article_id=a.id,
        title=a.title,
        url=a.url,
        lang=r.get("lang", "en"),
        created=r["created"],
    )

class CrawlController:
    async def search_titles(self, req: SearchTitlesRequest) -> SearchTitlesResponse:
        try:
            data = await crawl_service.search_titles(req.keyword, req.limit, req.lang)
            return SearchTitlesResponse(keyword=req.keyword, lang=data["lang"], titles=data["titles"])
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    async def fetch_article(self, req: FetchArticleRequest, db: Session) -> FetchArticleResponse:
        try:
            result = await crawl_service.fetch_and_save(db, req.title, req.lang)
            if not result:
                raise HTTPException(status_code=404, detail=f"Không tìm thấy bài '{req.title}'.")
            return _to_fetch_response(result)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    async def crawl_topic(self, req: CrawlTopicRequest, db: Session) -> CrawlTopicResponse:
        try:
            data = await crawl_service.crawl_topic(db, req.keyword, req.limit, req.lang)
            articles = [_to_fetch_response(r) for r in data["results"]]
            return CrawlTopicResponse(
                keyword=req.keyword,
                pages_found=data["pages_found"],
                pages_saved=sum(1 for r in data["results"] if r["created"]),
                failed=len(data["errors"]),
                articles=articles,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    async def crawl_urls(self, req: CrawlUrlsRequest, db: Session) -> CrawlUrlsResponse:
        try:
            data = await crawl_service.crawl_urls(db, req.urls)
            articles = [_to_fetch_response(r) for r in data["results"]]
            return CrawlUrlsResponse(
                total_input=data["total_input"],
                pages_saved=sum(1 for r in data["results"] if r["created"]),
                failed=len(data["errors"]),
                articles=articles,
                errors=data["errors"],
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    async def crawl_keywords(self, req: CrawlKeywordsRequest, db: Session) -> CrawlKeywordsResponse:
        try:
            data = await crawl_service.crawl_keywords(
                db, req.keywords, req.limit_per_keyword, req.lang,
            )
            articles = [_to_fetch_response(r) for r in data["results"]]
            return CrawlKeywordsResponse(
                total_keywords=data["total_keywords"],
                pages_found=data["pages_found"],
                pages_saved=sum(1 for r in data["results"] if r["created"]),
                failed=len(data["errors"]),
                articles=articles,
                errors=data["errors"],
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
