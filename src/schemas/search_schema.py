from pydantic import BaseModel, Field
from typing import List, Optional

class ChunkResult(BaseModel):
    id: str
    score: float
    text: str
    title: str
    url: str
    chunk_index: int

class SearchRequest(BaseModel):
    query: str = Field(..., description="Câu truy vấn")
    top_k: int = Field(default=5, ge=1, le=20, description="Số kết quả trả về")

class SearchResponse(BaseModel):
    query: str
    mode: str
    results: List[ChunkResult]

class AskRequest(BaseModel):
    query: str = Field(..., description="Câu hỏi tự nhiên")
    top_k: int = Field(default=5, ge=1, le=20, description="Số chunks hybrid retrieve")

    # Override LLM params (nếu không truyền → dùng config mặc định)
    model: Optional[str] = Field(
        default=None,
        description=(
            "Override model. Ví dụ: gpt-4o, gemini-2.0-flash, "
            "claude-3-5-haiku-20241022, llama3.2"
        ),
    )
    temperature: Optional[float] = Field(
        default=None, ge=0.0, le=2.0,
        description="Độ sáng tạo (0=deterministic, 1=creative). Mặc định theo config",
    )
    max_tokens: Optional[int] = Field(
        default=None, ge=64, le=8192,
        description="Giới hạn token output. Mặc định theo config",
    )

class LLMUsage(BaseModel):
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None

class AskResponse(BaseModel):
    query: str
    answer: str
    sources: List[ChunkResult]
    model: str
    provider: str
    usage: LLMUsage = LLMUsage()
