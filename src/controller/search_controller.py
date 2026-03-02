from fastapi import HTTPException
from src.services.search_service import search_service
from src.schemas.search_schema import (
    SearchRequest, SearchResponse, ChunkResult,
    AskRequest, AskResponse,
)

class SearchController:
    def fulltext(self, req: SearchRequest) -> SearchResponse:
        try:
            results = search_service.fulltext(req.query, top_k=req.top_k)
            return SearchResponse(query=req.query, mode="fulltext", results=results)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    def semantic(self, req: SearchRequest) -> SearchResponse:
        try:
            results = search_service.semantic(req.query, top_k=req.top_k)
            return SearchResponse(query=req.query, mode="semantic", results=results)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    def hybrid(self, req: SearchRequest) -> SearchResponse:
        try:
            results = search_service.hybrid(req.query, top_k=req.top_k)
            return SearchResponse(query=req.query, mode="hybrid", results=results)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    def ask(self, req: AskRequest) -> AskResponse:
        try:
            result = search_service.answer_query(req.query)
            return AskResponse(
                query=req.query,
                answer=result["answer"],
                sources=[ChunkResult(**s) for s in result["sources"]],
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
