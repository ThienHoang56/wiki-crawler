from fastapi import APIRouter
from src.controller.search_controller import SearchController
from src.schemas.search_schema import SearchRequest, SearchResponse, AskRequest, AskResponse

router = APIRouter(prefix="/api/v1/search", tags=["4. Search & RAG"])
controller = SearchController()

@router.post("/fulltext", response_model=SearchResponse, summary="BM25 full-text search")
def fulltext_search(req: SearchRequest):
    """Tìm theo từ khoá chính xác (BM25). Không qua LLM."""
    return controller.fulltext(req)

@router.post("/semantic", response_model=SearchResponse, summary="Semantic vector search")
def semantic_search(req: SearchRequest):
    """Tìm theo ngữ nghĩa (Dense Vector Cosine). Không qua LLM."""
    return controller.semantic(req)

@router.post("/hybrid", response_model=SearchResponse, summary="Hybrid search (BM25 + Vector + RRF)")
def hybrid_search(req: SearchRequest):
    """
    Kết hợp BM25 + Vector qua RRF Fusion. Chất lượng tốt nhất.
    Trả về chunks, **không qua LLM**.
    """
    return controller.hybrid(req)

@router.post("/ask", response_model=AskResponse, summary="RAG — hỏi đáp bằng LLM")
def ask(req: AskRequest):
    """
    Full RAG pipeline: Hybrid Search → Rerank → LLM Generation.

    **Hỗ trợ nhiều provider** (tự detect từ tên model):
    - **OpenAI:** `gpt-4o`, `gpt-4o-mini`, `o3-mini`
    - **Gemini:** `gemini-2.0-flash`, `gemini-1.5-pro`
    - **Anthropic:** `claude-3-5-haiku-20241022`, `claude-3-5-sonnet-20241022`
    - **Ollama (local):** `llama3.2`, `mistral`, `qwen2.5`, `deepseek-r1`

    Để trống `model` → dùng `LLM_MODEL` trong `.env`.
    """
    return controller.ask(req)
