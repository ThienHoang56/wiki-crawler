from fastapi import APIRouter
from src.controller.search_controller import SearchController
from src.schemas.search_schema import SearchRequest, SearchResponse, AskRequest, AskResponse

router = APIRouter(prefix="/api/v1/search", tags=["4. Search & RAG"])
controller = SearchController()

@router.post("/fulltext", response_model=SearchResponse)
def fulltext_search(req: SearchRequest):
    """Full-text search (BM25) — tìm theo từ khoá chính xác."""
    return controller.fulltext(req)

@router.post("/semantic", response_model=SearchResponse)
def semantic_search(req: SearchRequest):
    """Semantic search (Vector/Cosine) — tìm theo ngữ nghĩa."""
    return controller.semantic(req)

@router.post("/hybrid", response_model=SearchResponse)
def hybrid_search(req: SearchRequest):
    """Hybrid search (BM25 + Vector + RRF Fusion) — trả về chunks, không qua LLM."""
    return controller.hybrid(req)

@router.post("/ask", response_model=AskResponse)
def ask(req: AskRequest):
    """
    Full RAG pipeline: Hybrid Search → Rerank → LLM Generation.
    Trả về câu trả lời tự nhiên kèm nguồn trích dẫn.
    """
    return controller.ask(req)
