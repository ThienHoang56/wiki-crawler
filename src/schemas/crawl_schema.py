from pydantic import BaseModel, Field, field_validator
import re

LANG_DESCRIPTION = 'Ngôn ngữ Wikipedia (en, vi, ja, zh, fr, de, ...). Mặc định theo CRAWLER_WIKI_LANG trong config.'

class SearchTitlesRequest(BaseModel):
    keyword: str = Field(..., description="Từ khóa tìm kiếm trên Wikipedia")
    limit: int = Field(default=10, ge=1, le=50)
    lang: str = Field(default=None, description=LANG_DESCRIPTION)

class SearchTitlesResponse(BaseModel):
    keyword: str
    lang: str
    titles: list[str]

class FetchArticleRequest(BaseModel):
    title: str = Field(..., description="Tiêu đề bài viết Wikipedia cần fetch")
    lang: str = Field(default=None, description=LANG_DESCRIPTION)

class FetchArticleResponse(BaseModel):
    article_id: int
    title: str
    url: str
    lang: str = "en"
    created: bool = Field(description="True nếu mới lưu, False nếu đã tồn tại trước đó")

class CrawlTopicRequest(BaseModel):
    keyword: str = Field(..., description="Từ khóa chủ đề cần cào")
    limit: int = Field(default=5, ge=1, le=50)
    lang: str = Field(default=None, description=LANG_DESCRIPTION)

class CrawlTopicResponse(BaseModel):
    keyword: str
    pages_found: int
    pages_saved: int
    failed: int
    articles: list[FetchArticleResponse]

# ── Mới: Crawl từ danh sách URL ────────────────────────────────────────────

class CrawlUrlsRequest(BaseModel):
    urls: list[str] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Danh sách Wikipedia URLs hoặc tiêu đề (tối đa 100)",
    )

    @field_validator("urls")
    @classmethod
    def validate_wikipedia_urls(cls, urls):
        for url in urls:
            if url.startswith("http") and "wikipedia.org/wiki/" not in url:
                raise ValueError(f"URL không hợp lệ: {url} (phải là Wikipedia URL)")
        return urls

class CrawlUrlsResponse(BaseModel):
    total_input: int
    pages_saved: int
    failed: int
    articles: list[FetchArticleResponse]
    errors: list[dict]

# ── Mới: Crawl nhiều keyword song song ─────────────────────────────────────

class CrawlKeywordsRequest(BaseModel):
    keywords: list[str] = Field(
        ...,
        min_length=1,
        max_length=20,
        description="Danh sách từ khóa cần cào (tối đa 20 keyword)",
    )
    limit_per_keyword: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Số bài tìm thấy tối đa cho mỗi keyword",
    )
    lang: str = Field(default=None, description=LANG_DESCRIPTION)

class CrawlKeywordsResponse(BaseModel):
    total_keywords: int
    pages_found: int
    pages_saved: int
    failed: int
    articles: list[FetchArticleResponse]
    errors: list[dict]
