from src.utils.embedder import embedder
from src.core.vector_db import vector_db
from src.core.llm_client import llm_client
from src.core.config import settings
from typing import List, Dict

class SearchService:
    def __init__(self):
        self._system_prompt = (
            "You are an intelligent assistant specialized in answering questions "
            "based on the provided Wikipedia context. "
            "If the answer cannot be found in the context, politely say that you don't know."
        )

    def fulltext(self, query: str, top_k: int = 5) -> List[Dict]:
        """BM25 Full-text Search."""
        return vector_db.search_bm25_normalized(query, top_k=top_k)

    def semantic(self, query: str, top_k: int = 5) -> List[Dict]:
        """Dense Vector (Cosine) Semantic Search."""
        query_embedding = embedder.get_embedding(query)
        return vector_db.search_vector_normalized(query_embedding, top_k=top_k)

    def hybrid(self, query: str, top_k: int = 5) -> List[Dict]:
        """BM25 + Vector + RRF Fusion (không qua LLM)."""
        query_embedding = embedder.get_embedding(query)
        return vector_db.hybrid_search(query=query, query_embedding=query_embedding, top_k=top_k)

    def answer_query(self, query: str) -> Dict:
        """Full RAG pipeline: Hybrid Search → Rerank → LLM Generation."""
        retrieved = self.hybrid(query, top_k=settings.RAG_HYBRID_POOL)
        if not retrieved:
            return {"answer": "Không tìm thấy thông tin phù hợp.", "sources": []}

        # Rerank: sắp xếp theo RRF score, cắt top-N truyền vào LLM
        reranked = sorted(retrieved, key=lambda d: d["score"], reverse=True)[:settings.RAG_TOP_K_CONTEXT]

        context = "\n\n".join(
            f"[{i+1}] {d['title']}\n{d['text']}" for i, d in enumerate(reranked)
        )
        prompt = (
            f"Use the following Wikipedia context to answer the question.\n\n"
            f"--- CONTEXT ---\n{context}\n--- END CONTEXT ---\n\n"
            f"Question: {query}\nAnswer:"
        )
        answer = llm_client.generate_response(prompt, system_prompt=self._system_prompt)
        return {"answer": answer, "sources": reranked}

search_service = SearchService()
