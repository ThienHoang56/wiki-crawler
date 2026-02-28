import httpx
import asyncio
import re
from typing import Optional
from urllib.parse import urlparse, unquote
from src.core.config import settings

def _wiki_api_url(lang: str) -> str:
    return f"https://{lang}.wikipedia.org/w/api.php"

def _wiki_page_url(lang: str, title: str) -> str:
    return f"https://{lang}.wikipedia.org/wiki/{title.replace(' ', '_')}"

class WikiCrawler:
    def __init__(self):
        self.headers = {"User-Agent": settings.CRAWLER_USER_AGENT}

    # ── Helpers ────────────────────────────────────────────────────────────────

    def extract_title_from_url(self, url: str) -> tuple[str, str]:
        """
        Chuyển Wikipedia URL → (lang, title).
        VD: https://vi.wikipedia.org/wiki/Máy_học → ("vi", "Máy học")
        """
        parsed = urlparse(url)
        # Lấy lang từ subdomain: vi.wikipedia.org → "vi"
        lang = parsed.netloc.split(".")[0] if ".wikipedia.org" in parsed.netloc else settings.CRAWLER_WIKI_LANG
        raw = parsed.path.split("/wiki/")[-1]
        return lang, unquote(raw).replace("_", " ")

    def is_wikipedia_url(self, text: str) -> bool:
        return bool(re.match(r"https?://([\w-]+\.)?wikipedia\.org/wiki/", text))

    # ── Core fetch (có retry, multilingual) ───────────────────────────────────

    async def fetch_page(
        self,
        title: str,
        lang: str = None,
    ) -> Optional[dict]:
        """
        Lấy nội dung plain-text 1 bài Wikipedia (có retry + exponential backoff).
        lang: ngôn ngữ Wikipedia (en, vi, ja, ...). Mặc định lấy từ config.
        """
        lang = lang or settings.CRAWLER_WIKI_LANG
        api_url = _wiki_api_url(lang)
        params = {
            "action": "query",
            "titles": title,
            "prop": "extracts|info",
            "explaintext": True,
            "exsectionformat": "wiki",
            "inprop": "url",
            "format": "json",
            "redirects": 1,
        }
        retries = settings.CRAWLER_RETRY_COUNT
        backoff = settings.CRAWLER_RETRY_BACKOFF
        last_exc: Exception = None
        for attempt in range(retries):
            try:
                async with httpx.AsyncClient(
                    headers=self.headers,
                    timeout=settings.CRAWLER_TIMEOUT_SECONDS,
                ) as client:
                    resp = await client.get(api_url, params=params)
                    resp.raise_for_status()
                    data = resp.json()

                pages = data.get("query", {}).get("pages", {})
                page = next(iter(pages.values()))
                if "missing" in page:
                    return None

                return {
                    "title": page.get("title", title),
                    "url": page.get("fullurl", _wiki_page_url(lang, title)),
                    "text": page.get("extract", ""),
                    "lang": lang,
                }
            except Exception as exc:
                last_exc = exc
                if attempt < retries - 1:
                    await asyncio.sleep(backoff * (attempt + 1))

        raise RuntimeError(f"Failed to fetch '{title}' after {retries} retries: {last_exc}")

    async def fetch_by_url(self, url: str) -> Optional[dict]:
        """Fetch bài viết từ Wikipedia URL trực tiếp (tự detect ngôn ngữ từ URL)."""
        lang, title = self.extract_title_from_url(url)
        return await self.fetch_page(title, lang=lang)

    # ── Search ─────────────────────────────────────────────────────────────────

    async def search_titles(self, keyword: str, limit: int = 10, lang: str = None) -> list[str]:
        """Tìm kiếm tiêu đề bài viết theo từ khoá."""
        lang = lang or settings.CRAWLER_WIKI_LANG
        params = {
            "action": "query",
            "list": "search",
            "srsearch": keyword,
            "srlimit": limit,
            "format": "json",
        }
        async with httpx.AsyncClient(
            headers=self.headers,
            timeout=settings.CRAWLER_TIMEOUT_SECONDS,
        ) as client:
            resp = await client.get(_wiki_api_url(lang), params=params)
            resp.raise_for_status()
            data = resp.json()
        return [r["title"] for r in data.get("query", {}).get("search", [])]

    # ── Parallel batch fetch ───────────────────────────────────────────────────

    async def fetch_pages_parallel(
        self,
        titles: list[str],
        concurrency: int = None,
        lang: str = None,
    ) -> tuple[list[dict], list[dict]]:
        """
        Fetch nhiều bài song song, kiểm soát số request đồng thời bằng Semaphore.
        - concurrency: số request đồng thời tối đa (mặc định từ config).
        - Rate limit vẫn được giữ qua sleep trong mỗi task.
        """
        if concurrency is None:
            concurrency = settings.CRAWLER_CONCURRENCY

        semaphore = asyncio.Semaphore(concurrency)

        async def fetch_with_limit(title: str) -> Optional[dict]:
            async with semaphore:
                result = await self.fetch_page(title, lang=lang)
                await asyncio.sleep(settings.CRAWLER_RATE_LIMIT_SECONDS / concurrency)
                return result

        tasks = [fetch_with_limit(t) for t in titles]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        pages = []
        errors = []
        for title, r in zip(titles, results):
            if isinstance(r, Exception):
                errors.append({"title": title, "error": str(r)})
            elif r and r.get("text"):
                pages.append(r)

        return pages, errors

    # ── High-level pipelines ───────────────────────────────────────────────────

    async def crawl_topic(
        self,
        keyword: str,
        limit: int = 5,
        lang: str = None,
    ) -> tuple[list[dict], list[dict]]:
        """Search theo keyword → fetch song song."""
        lang = lang or settings.CRAWLER_WIKI_LANG
        titles = await self.search_titles(keyword, limit=limit, lang=lang)
        return await self.fetch_pages_parallel(titles, lang=lang)

    async def crawl_urls(self, urls: list[str]) -> tuple[list[dict], list[dict]]:
        """
        Fetch danh sách Wikipedia URLs song song.
        Tự detect ngôn ngữ từ URL (vi.wikipedia.org → lang="vi").
        """
        # Nhóm theo lang để fetch đúng endpoint
        lang_title_pairs: list[tuple[str, str]] = []
        for u in urls:
            if self.is_wikipedia_url(u):
                lang_title_pairs.append(self.extract_title_from_url(u))
            else:
                lang_title_pairs.append((settings.CRAWLER_WIKI_LANG, u))

        concurrency = settings.CRAWLER_CONCURRENCY
        semaphore = asyncio.Semaphore(concurrency)

        async def fetch_one(lang: str, title: str) -> Optional[dict]:
            async with semaphore:
                result = await self.fetch_page(title, lang=lang)
                await asyncio.sleep(settings.CRAWLER_RATE_LIMIT_SECONDS / concurrency)
                return result

        tasks = [fetch_one(lang, title) for lang, title in lang_title_pairs]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        pages, errors = [], []
        for (lang, title), r in zip(lang_title_pairs, results):
            if isinstance(r, Exception):
                errors.append({"title": title, "lang": lang, "error": str(r)})
            elif r and r.get("text"):
                pages.append(r)
        return pages, errors

    async def crawl_keywords(
        self,
        keywords: list[str],
        limit_per_keyword: int = 5,
        lang: str = None,
    ) -> tuple[list[dict], list[dict]]:
        """
        Crawl nhiều keyword cùng lúc (search song song → fetch song song).
        Deduplicate theo URL.
        """
        lang = lang or settings.CRAWLER_WIKI_LANG
        all_errors: list[dict] = []

        search_tasks = [self.search_titles(kw, limit=limit_per_keyword, lang=lang) for kw in keywords]
        search_results = await asyncio.gather(*search_tasks, return_exceptions=True)

        all_titles: list[str] = []
        for kw, result in zip(keywords, search_results):
            if isinstance(result, Exception):
                all_errors.append({"keyword": kw, "error": str(result)})
            else:
                all_titles.extend(result)

        unique_titles = list(dict.fromkeys(all_titles))
        pages, errors = await self.fetch_pages_parallel(unique_titles, lang=lang)
        all_errors.extend(errors)

        seen_urls: set[str] = set()
        deduped = []
        for p in pages:
            if p["url"] not in seen_urls:
                seen_urls.add(p["url"])
                deduped.append(p)

        return deduped, all_errors

wiki_crawler = WikiCrawler()
