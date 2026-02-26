from sqlalchemy import Column, Integer, Text, String, Boolean, DateTime, func
from src.core.database import Base

class Article(Base):
    """Lưu trữ bài viết Wikipedia thô sau khi Crawler lấy về."""
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(512), nullable=False, index=True)
    url = Column(String(1024), nullable=False, unique=True)
    raw_text = Column(Text, nullable=False)
    is_indexed = Column(Boolean, default=False, nullable=False)  # True sau khi đã đưa vào Elasticsearch
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
