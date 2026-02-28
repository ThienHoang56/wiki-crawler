from sqlalchemy.orm import Session
from src.repository.article_repository import article_repository
from src.models.article import Article
from typing import Optional

class ArticleService:
    def list(self, db: Session, page: int = 1, limit: int = 20) -> dict:
        items, total = article_repository.list(db, page=page, limit=limit)
        return {"total": total, "page": page, "limit": limit, "items": items}

    def get_by_id(self, db: Session, article_id: int) -> Optional[Article]:
        return article_repository.get_by_id(db, article_id)

    def get_stats(self, db: Session) -> dict:
        indexed = article_repository.count_indexed(db)
        unindexed = article_repository.count_unindexed(db)
        return {"total": indexed + unindexed, "indexed": indexed, "unindexed": unindexed}

    def delete(self, db: Session, article_id: int) -> bool:
        return article_repository.delete(db, article_id)

article_service = ArticleService()
