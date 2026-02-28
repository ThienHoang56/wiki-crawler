from pydantic import BaseModel
from datetime import datetime

class ArticleOut(BaseModel):
    id: int
    title: str
    url: str
    is_indexed: bool
    created_at: datetime

    model_config = {"from_attributes": True}

class ArticleListResponse(BaseModel):
    total: int
    page: int
    limit: int
    items: list[ArticleOut]

class ArticleStatsResponse(BaseModel):
    total: int
    indexed: int
    unindexed: int

class DeleteResponse(BaseModel):
    success: bool
    message: str
