import time
from sqlalchemy.orm import Session
from src.core.vector_db import vector_db
from src.core.job_store import job_store, JobStatus, Job
from src.core.database import SessionLocal
from src.repository.article_repository import article_repository
from src.utils.cleaner import cleaner
from src.utils.chunker import chunker
from src.utils.embedder import embedder

class IndexService:

    def run_sync(self, db: Session, batch_size: int = 100) -> dict:
        """
        Chạy đồng bộ (dùng cho test / gọi trực tiếp).
        """
        vector_db.create_index_if_not_exists()
        articles = article_repository.get_unindexed(db, limit=batch_size)
        if not articles:
            return {"articles_processed": 0, "chunks_indexed": 0}

        bulk_docs, processed_ids = [], []
        for article in articles:
            clean_text = cleaner.clean_text(article.raw_text)
            if not clean_text:
                article_repository.mark_indexed(db, article.id)
                continue
            chunks = chunker.chunk_data(clean_text)
            if not chunks:
                article_repository.mark_indexed(db, article.id)
                continue
            embeddings = embedder.get_embeddings_batch(chunks)
            for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
                bulk_docs.append({
                    "text": chunk, "embedding": emb,
                    "title": article.title, "url": article.url,
                    "chunk_index": i,
                })
            processed_ids.append(article.id)

        indexed_count = vector_db.bulk_index_documents(bulk_docs) if bulk_docs else 0
        for aid in processed_ids:
            article_repository.mark_indexed(db, aid)

        return {"articles_processed": len(processed_ids), "chunks_indexed": indexed_count}

    def run_background(self, job: Job, batch_size: int = 100):
        """
        Chạy trong background thread — cập nhật tiến trình vào Job liên tục.
        Dùng session riêng (không share với request thread).
        """
        db = SessionLocal()
        try:
            job.status = JobStatus.RUNNING
            job.started_at = time.time()
            job.progress = {"articles_processed": 0, "chunks_indexed": 0, "total_unindexed": 0}

            vector_db.create_index_if_not_exists()

            # Đếm tổng số bài cần xử lý để hiển thị % tiến trình
            total = article_repository.count_unindexed(db)
            job.progress["total_unindexed"] = total

            total_processed = 0
            total_chunks = 0

            while True:
                articles = article_repository.get_unindexed(db, limit=batch_size)
                if not articles:
                    break

                bulk_docs, processed_ids = [], []
                for article in articles:
                    clean_text = cleaner.clean_text(article.raw_text)
                    if not clean_text:
                        article_repository.mark_indexed(db, article.id)
                        continue
                    chunks = chunker.chunk_data(clean_text)
                    if not chunks:
                        article_repository.mark_indexed(db, article.id)
                        continue
                    embeddings = embedder.get_embeddings_batch(chunks)
                    for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
                        bulk_docs.append({
                            "text": chunk, "embedding": emb,
                            "title": article.title, "url": article.url, "chunk_index": i,
                        })
                    processed_ids.append(article.id)

                indexed = vector_db.bulk_index_documents(bulk_docs) if bulk_docs else 0
                for aid in processed_ids:
                    article_repository.mark_indexed(db, aid)

                total_processed += len(processed_ids)
                total_chunks += indexed

                # Cập nhật tiến trình để /index/status có thể poll
                job.progress = {
                    "articles_processed": total_processed,
                    "chunks_indexed": total_chunks,
                    "total_unindexed": total,
                    "percent": round(total_processed / total * 100, 1) if total else 100,
                }

            job.status = JobStatus.DONE
            job.finished_at = time.time()
            job.result = {
                "articles_processed": total_processed,
                "chunks_indexed": total_chunks,
            }

        except Exception as exc:
            job.status = JobStatus.FAILED
            job.finished_at = time.time()
            job.error = str(exc)
        finally:
            db.close()

    def get_stats(self) -> dict:
        return vector_db.get_stats()

    def reset(self, db: Session) -> dict:
        vector_db.reset_index()
        article_repository.reset_indexed_flag(db)
        return {"message": "Đã reset Elasticsearch index và cờ is_indexed trong PostgreSQL."}

index_service = IndexService()
