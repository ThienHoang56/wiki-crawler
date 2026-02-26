from typing import List, Dict, Any
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk
from src.core.config import settings

class VectorDBClient:
    _client: Elasticsearch = None

    @property
    def client(self) -> Elasticsearch:
        """Lazy init: chỉ kết nối ES khi thực sự cần dùng, không crash lúc import."""
        if self._client is None:
            self._client = Elasticsearch(
                hosts=[settings.ES_HOST],
                basic_auth=(settings.ES_USER, settings.ES_PASSWORD) if settings.ES_USER else None,
            )
        return self._client

    @property
    def index_name(self) -> str:
        return settings.INDEX_NAME

    # Mapping ngôn ngữ → ES built-in analyzer
    # ES có sẵn analyzer cho các ngôn ngữ châu Âu và một số châu Á.
    # Tiếng Việt/Nhật/Trung dùng "icu_analyzer" (cần plugin ICU) hoặc fallback "standard".
    _LANG_ANALYZER: dict[str, str] = {
        "en": "english",
        "fr": "french",
        "de": "german",
        "es": "spanish",
        "it": "italian",
        "pt": "portuguese",
        "ru": "russian",
        "ar": "arabic",
        "zh": "cjk",     # Chinese/Japanese/Korean — ES built-in CJK analyzer
        "ja": "cjk",
        "ko": "cjk",
        "vi": "standard", # Không có vi analyzer built-in, standard là tốt nhất hiện có
    }

    def _get_analyzer(self) -> str:
        return self._LANG_ANALYZER.get(settings.CRAWLER_WIKI_LANG, "standard")

    def create_index_if_not_exists(self):
        """Tạo index với mapping cho cả Full-text và Dense Vector (Hybrid Search)."""
        if not self.client.indices.exists(index=self.index_name):
            analyzer = self._get_analyzer()
            self.client.indices.create(
                index=self.index_name,
                mappings={
                    "properties": {
                        # Full-text search (BM25) — dùng language-aware analyzer
                        "text":  {"type": "text", "analyzer": analyzer},
                        "title": {"type": "text", "analyzer": analyzer},
                        # Dense vector search (Cosine)
                        # dims lấy từ config để đồng bộ với EMBEDDING_MODEL
                        "embedding": {
                            "type": "dense_vector",
                            "dims": settings.EMBEDDING_DIMS,
                            "index": True,
                            "similarity": "cosine",
                        },
                        # Metadata fields
                        "url":         {"type": "keyword"},
                        "chunk_index": {"type": "integer"},
                        "lang":        {"type": "keyword"},
                    }
                },
            )

    def index_document(
        self,
        text: str,
        embedding: List[float],
        title: str = "",
        url: str = "",
        chunk_index: int = 0,
    ):
        """Lưu một chunk vào Elasticsearch (dùng cho test/debug, production dùng bulk)."""
        doc = {
            "text": text,
            "embedding": embedding,
            "title": title,
            "url": url,
            "chunk_index": chunk_index,
        }
        return self.client.index(index=self.index_name, document=doc)

    def bulk_index_documents(self, docs: List[Dict[str, Any]]) -> int:
        """
        Lưu nhiều chunks cùng lúc bằng ES Bulk API.
        Nhanh hơn ~10-20x so với index từng doc một.
        Trả về số docs đã index thành công.
        """
        actions = [
            {
                "_index": self.index_name,
                "_source": {
                    "text": d["text"],
                    "embedding": d["embedding"],
                    "title": d.get("title", ""),
                    "url": d.get("url", ""),
                    "chunk_index": d.get("chunk_index", 0),
                    "lang": d.get("lang", settings.CRAWLER_WIKI_LANG),
                },
            }
            for d in docs
        ]
        success, _ = bulk(self.client, actions, chunk_size=500, request_timeout=120)
        return success

    def search_bm25(self, query: str, size: int = 20) -> List[Dict]:
        """Full-text search sử dụng BM25."""
        resp = self.client.search(
            index=self.index_name,
            query={"multi_match": {"query": query, "fields": ["text", "title"]}},
            size=size,
        )
        return resp["hits"]["hits"]

    def search_vector(self, query_embedding: List[float], k: int = 20) -> List[Dict]:
        """Semantic search sử dụng Dense Vector (Cosine Similarity)."""
        resp = self.client.search(
            index=self.index_name,
            knn={
                "field": "embedding",
                "query_vector": query_embedding,
                "k": k,
                "num_candidates": k * 5,
            },
            size=k,
        )
        return resp["hits"]["hits"]

    def hybrid_search(self, query: str, query_embedding: List[float], top_k: int = 5) -> List[Dict]:
        """
        Hybrid Search = BM25 + Vector Search kết hợp bằng RRF Fusion.
        Trả về Top-K chunks sắp xếp theo điểm RRF tổng hợp.
        """
        pool = settings.SEARCH_CANDIDATE_POOL
        bm25_hits = self.search_bm25(query, size=pool)
        vector_hits = self.search_vector(query_embedding, k=pool)

        rrf_scores: Dict[str, float] = {}
        hit_sources: Dict[str, Dict] = {}
        k_rrf = settings.RRF_K

        for rank, hit in enumerate(bm25_hits):
            doc_id = hit["_id"]
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + 1.0 / (k_rrf + rank + 1)
            hit_sources[doc_id] = hit["_source"]

        for rank, hit in enumerate(vector_hits):
            doc_id = hit["_id"]
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + 1.0 / (k_rrf + rank + 1)
            hit_sources[doc_id] = hit["_source"]

        sorted_ids = sorted(rrf_scores, key=lambda x: rrf_scores[x], reverse=True)[:top_k]

        results = []
        for doc_id in sorted_ids:
            source = hit_sources[doc_id]
            results.append({
                "id": doc_id,
                "score": round(rrf_scores[doc_id], 6),
                "text": source.get("text", ""),
                "title": source.get("title", ""),
                "url": source.get("url", ""),
                "chunk_index": source.get("chunk_index", 0),
            })
        return results

    def _hits_to_chunks(self, hits: List[Dict], score_key: str = "_score") -> List[Dict]:
        """Chuẩn hóa ES hits thành format chunk thống nhất."""
        return [
            {
                "id": h["_id"],
                "score": round(h.get(score_key, 0.0), 6),
                "text": h["_source"].get("text", ""),
                "title": h["_source"].get("title", ""),
                "url": h["_source"].get("url", ""),
                "chunk_index": h["_source"].get("chunk_index", 0),
            }
            for h in hits
        ]

    def search_bm25_normalized(self, query: str, top_k: int = 5) -> List[Dict]:
        """BM25 search trả về format chuẩn."""
        hits = self.search_bm25(query, size=top_k)
        return self._hits_to_chunks(hits)

    def search_vector_normalized(self, query_embedding: List[float], top_k: int = 5) -> List[Dict]:
        """Vector search trả về format chuẩn."""
        hits = self.search_vector(query_embedding, k=top_k)
        return self._hits_to_chunks(hits)

    def get_stats(self) -> Dict:
        """Thống kê Elasticsearch index."""
        try:
            stats = self.client.indices.stats(index=self.index_name)
            total = stats["indices"][self.index_name]["total"]["docs"]["count"]
            size_bytes = stats["indices"][self.index_name]["total"]["store"]["size_in_bytes"]
            return {
                "index_name": self.index_name,
                "total_chunks": total,
                "size_bytes": size_bytes,
                "exists": True,
            }
        except Exception:
            return {"index_name": self.index_name, "total_chunks": 0, "size_bytes": 0, "exists": False}

    def reset_index(self):
        """Xóa toàn bộ index và tạo lại."""
        if self.client.indices.exists(index=self.index_name):
            self.client.indices.delete(index=self.index_name)
        self.create_index_if_not_exists()

# Singleton instance (lazy — không kết nối ES cho đến khi được gọi)
vector_db = VectorDBClient()
