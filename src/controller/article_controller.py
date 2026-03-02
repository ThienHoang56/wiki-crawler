from fastapi import HTTPException
from sqlalchemy.orm import Session
from src.services.article_service import article_service
from src.schemas.article_schema import (
    ArticleOut, ArticleListResponse, ArticleStatsResponse, DeleteResponse
)

class ArticleController:
    def list(self, db: Session, page: int, limit: int) -> ArticleListResponse:
        data = article_service.list(db, page=page, limit=limit)
        return ArticleListResponse(
            total=data["total"],
            page=data["page"],
            limit=data["limit"],
            items=[ArticleOut.model_validate(a) for a in data["items"]],
        )

    def get_by_id(self, db: Session, article_id: int) -> ArticleOut:
        article = article_service.get_by_id(db, article_id)
        if not article:
            raise HTTPException(status_code=404, detail=f"Không tìm thấy article id={article_id}")
        return ArticleOut.model_validate(article)

    def get_stats(self, db: Session) -> ArticleStatsResponse:
        return ArticleStatsResponse(**article_service.get_stats(db))

    def delete(self, db: Session, article_id: int) -> DeleteResponse:
        success = article_service.delete(db, article_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"Không tìm thấy article id={article_id}")
        return DeleteResponse(success=True, message=f"Đã xóa article id={article_id}.")
