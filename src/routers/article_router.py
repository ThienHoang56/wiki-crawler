from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from src.core.database import get_db
from src.controller.article_controller import ArticleController
from src.schemas.article_schema import ArticleOut, ArticleListResponse, ArticleStatsResponse, DeleteResponse

router = APIRouter(prefix="/api/v1/articles", tags=["2. Articles (PostgreSQL)"])
controller = ArticleController()

@router.get("/stats", response_model=ArticleStatsResponse)
def get_stats(db: Session = Depends(get_db)):
    """Thống kê số bài viết: tổng, đã index, chưa index."""
    return controller.get_stats(db)

@router.get("/", response_model=ArticleListResponse)
def list_articles(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Danh sách tất cả bài viết đã cào, hỗ trợ phân trang."""
    return controller.list(db, page=page, limit=limit)

@router.get("/{article_id}", response_model=ArticleOut)
def get_article(article_id: int, db: Session = Depends(get_db)):
    """Xem chi tiết một bài viết theo ID."""
    return controller.get_by_id(db, article_id)

@router.delete("/{article_id}", response_model=DeleteResponse)
def delete_article(article_id: int, db: Session = Depends(get_db)):
    """Xóa bài viết khỏi PostgreSQL (không ảnh hưởng Elasticsearch)."""
    return controller.delete(db, article_id)
