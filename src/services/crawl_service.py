from sqlalchemy.orm import Session
from src.core.config import settings
from src.utils.crawler import wiki_crawler
from src.repository.article_repository import article_repository

def _effective_lang(lang: str | None) -> str:
    return lang or settings.CRAWLER_WIKI_LANG

class CrawlService:
    async def search_titles(self, keyword: str, limit: int, lang: str = None) -> dict:
        effective = _effective_lang(lang)
        titles = await wiki_crawler.search_titles(keyword, limit=limit, lang=effective)
        return {"titles": titles, "lang": effective}

    async def fetch_and_save(self, db: Session, title: str, lang: str = None) -> dict:
        effective = _effective_lang(lang)
        page = await wiki_crawler.fetch_page(title, lang=effective)
        if not page or not page["text"]:
            return None
        article, created = article_repository.save(
            db=db, title=page["title"], url=page["url"], raw_text=page["text"],
        )
        return {"article": article, "created": created, "lang": page.get("lang", effective)}

    async def crawl_topic(self, db: Session, keyword: str, limit: int, lang: str = None) -> dict:
        effective = _effective_lang(lang)
        pages, errors = await wiki_crawler.crawl_topic(keyword, limit=limit, lang=effective)
        results = []
        for page in pages:
            article, created = article_repository.save(
                db=db, title=page["title"], url=page["url"], raw_text=page["text"],
            )
            results.append({"article": article, "created": created, "lang": page.get("lang", effective)})
        return {"pages_found": limit, "results": results, "errors": errors, "lang": effective}

    async def crawl_urls(self, db: Session, urls: list[str]) -> dict:
        """Fetch song song, tự detect lang từ URL (vi.wikipedia.org → lang=vi)."""
        pages, errors = await wiki_crawler.crawl_urls(urls)
        results = []
        for page in pages:
            article, created = article_repository.save(
                db=db, title=page["title"], url=page["url"], raw_text=page["text"],
            )
            results.append({"article": article, "created": created, "lang": page.get("lang", "en")})
        return {"total_input": len(urls), "results": results, "errors": errors}

    async def crawl_keywords(
        self,
        db: Session,
        keywords: list[str],
        limit_per_keyword: int,
        lang: str = None,
    ) -> dict:
        effective = _effective_lang(lang)
        pages, errors = await wiki_crawler.crawl_keywords(
            keywords, limit_per_keyword=limit_per_keyword, lang=effective,
        )
        results = []
        for page in pages:
            article, created = article_repository.save(
                db=db, title=page["title"], url=page["url"], raw_text=page["text"],
            )
            results.append({"article": article, "created": created, "lang": page.get("lang", effective)})
        return {
            "total_keywords": len(keywords),
            "pages_found": len(pages) + len(errors),
            "results": results,
            "errors": errors,
            "lang": effective,
        }

crawl_service = CrawlService()
