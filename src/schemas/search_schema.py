from pydantic import BaseModel, Field
from typing import List

class ChunkResult(BaseModel):
    id: str
    score: float
    text: str
    title: str
    url: str
    chunk_index: int

class SearchRequest(BaseModel):
    query: str
    top_k: int = Field(default=5, ge=1, le=20)

class SearchResponse(BaseModel):
    query: str
    mode: str
    results: List[ChunkResult]

class AskRequest(BaseModel):
    query: str

class AskResponse(BaseModel):
    query: str
    answer: str
    sources: List[ChunkResult]
