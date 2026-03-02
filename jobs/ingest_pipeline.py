"""
Offline Indexing Job — Tầng RAG INDEXING trong kiến trúc.

Luồng: PostgreSQL (unindexed articles) → Clean → Chunk → Embed → Elasticsearch

Chạy bằng lệnh:
    make index
hoặc trực tiếp:
    python -m jobs.ingest_pipeline
"""

import sys
import os

# Đảm bảo root project nằm trong sys.path khi chạy trực tiếp
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.database import SessionLocal
from src.core.vector_db import vector_db
from src.repository.article_repository import article_repository
from src.utils.cleaner import cleaner
from src.utils.chunker import chunker
from src.utils.embedder import embedder


def run(batch_size: int = 50):
    """Đọc bài viết chưa index từ PostgreSQL và đẩy vào Elasticsearch."""

    print("[Pipeline] Đang khởi tạo Elasticsearch index...")
    vector_db.create_index_if_not_exists()

    db = SessionLocal()
    try:
        articles = article_repository.get_unindexed(db, limit=batch_size)

        if not articles:
            print("[Pipeline] Không có bài viết nào chờ index.")
            return

        print(f"[Pipeline] Bắt đầu index {len(articles)} bài viết...")

        total_chunks = 0
        for article in articles:
            # 1. Clean
            clean_text = cleaner.clean_text(article.raw_text)
            if not clean_text:
                article_repository.mark_indexed(db, article.id)
                continue

            # 2. Chunk
            chunks = chunker.chunk_data(clean_text)
            if not chunks:
                article_repository.mark_indexed(db, article.id)
                continue

            # 3. Embed (batch)
            embeddings = embedder.get_embeddings_batch(chunks)

            # 4. Index vào Elasticsearch
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                vector_db.index_document(
                    text=chunk,
                    embedding=embedding,
                    title=article.title,
                    url=article.url,
                    chunk_index=i,
                )

            # 5. Đánh dấu đã index
            article_repository.mark_indexed(db, article.id)

            total_chunks += len(chunks)
            print(f"  ✓ [{article.id}] {article.title} — {len(chunks)} chunks")

        print(f"\n[Pipeline] Hoàn tất. Tổng {total_chunks} chunks đã được index.")

    finally:
        db.close()


if __name__ == "__main__":
    run()
