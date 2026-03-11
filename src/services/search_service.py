import logging
from src.utils.embedder import embedder
from src.core.vector_db import vector_db
from src.core.llm_client import llm_client
from src.core.config import settings
from typing import List, Dict, Optional

logger = logging.getLogger("wiki-rag")

SYSTEM_PROMPT = (
    "You are an intelligent assistant specialized in answering questions "
    "based on the provided Wikipedia context. "
    "Answer clearly and concisely using only the context provided. "
    "If the answer cannot be found in the context, politely say that you don't know."
)

class SearchService:
    def fulltext(self, query: str, top_k: int = 5) -> List[Dict]:
        return vector_db.search_bm25_normalized(query, top_k=top_k)

    def semantic(self, query: str, top_k: int = 5) -> List[Dict]:
        query_embedding = embedder.get_embedding(query)
        return vector_db.search_vector_normalized(query_embedding, top_k=top_k)

    def hybrid(self, query: str, top_k: int = 5) -> List[Dict]:
        query_embedding = embedder.get_embedding(query)
        return vector_db.hybrid_search(query=query, query_embedding=query_embedding, top_k=top_k)

    def answer_query(
        self,
        query: str,
        top_k: int = 5,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Dict:
        """
        Full RAG pipeline: Hybrid Search → Rerank → LLM Generation.
        Trả về answer + sources + metadata (model, provider, token usage).
        """
        retrieved = self.hybrid(query, top_k=settings.RAG_HYBRID_POOL)
        if not retrieved:
            return {
                "answer": "Không tìm thấy thông tin phù hợp trong cơ sở dữ liệu.",
                "sources": [],
                "model": model or settings.LLM_MODEL,
                "provider": "",
                "usage": {},
            }

        # Rerank theo RRF score, lấy top-N truyền vào LLM
        reranked = sorted(retrieved, key=lambda d: d["score"], reverse=True)[:settings.RAG_TOP_K_CONTEXT]

        context = "\n\n".join(
            f"[Source {i+1}] {d['title']}\n{d['text']}"
            for i, d in enumerate(reranked)
        )
        prompt = (
            f"Use the following Wikipedia context to answer the question.\n\n"
            f"--- CONTEXT ---\n{context}\n--- END CONTEXT ---\n\n"
            f"Question: {query}\nAnswer:"
        )

        try:
            result = llm_client.generate_response(
                prompt=prompt,
                system_prompt=SYSTEM_PROMPT,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except Exception as exc:
            logger.error("LLM generate_response failed: %s", exc, exc_info=True)
            raise

        return {
            "answer":   result["answer"],
            "sources":  reranked,
            "model":    result["model"],
            "provider": result["provider"],
            "usage":    result.get("usage", {}),
        }

search_service = SearchService()
