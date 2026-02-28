from __future__ import annotations

from sqlalchemy.orm import Session
from sqlalchemy import select, func
from src.models.article import Article
from typing import Optional

class ArticleRepository:
    def save(self, db: Session, title: str, url: str, raw_text: str) -> tuple[Article, bool]:
        """
        Lưu bài viết mới. Trả về (article, created).
        created=False nếu URL đã tồn tại.
        """
        existing = db.scalar(select(Article).where(Article.url == url))
        if existing:
            return existing, False

        article = Article(title=title, url=url, raw_text=raw_text)
        db.add(article)
        db.commit()
        db.refresh(article)
        return article, True

    def get_by_id(self, db: Session, article_id: int) -> Optional[Article]:
        return db.get(Article, article_id)

    def list(self, db: Session, page: int = 1, limit: int = 20) -> tuple[list[Article], int]:
        """Trả về (danh sách bài, tổng số bài)."""
        offset = (page - 1) * limit
        total = db.scalar(select(func.count()).select_from(Article))
        items = list(db.scalars(
            select(Article).order_by(Article.created_at.desc()).offset(offset).limit(limit)
        ))
        return items, total

    def count_unindexed(self, db: Session) -> int:
        return db.scalar(select(func.count()).select_from(Article).where(Article.is_indexed == False))

    def count_indexed(self, db: Session) -> int:
        return db.scalar(select(func.count()).select_from(Article).where(Article.is_indexed == True))

    def delete(self, db: Session, article_id: int) -> bool:
        """Xóa bài viết. Trả về True nếu thành công."""
        article = db.get(Article, article_id)
        if not article:
            return False
        db.delete(article)
        db.commit()
        return True

    def get_unindexed(self, db: Session, limit: int = 100) -> list[Article]:
        return list(db.scalars(
            select(Article).where(Article.is_indexed == False).limit(limit)
        ))

    def mark_indexed(self, db: Session, article_id: int):
        article = db.get(Article, article_id)
        if article:
            article.is_indexed = True
            db.commit()

    def reset_indexed_flag(self, db: Session):
        """Đặt lại is_indexed=False cho tất cả bài viết (dùng khi reset ES index)."""
        db.query(Article).update({"is_indexed": False})
        db.commit()

article_repository = ArticleRepository()
