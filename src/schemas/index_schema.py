from pydantic import BaseModel, Field
from typing import Optional
from src.core.job_store import JobStatus

class IndexRunRequest(BaseModel):
    batch_size: int = Field(default=100, ge=1, le=1000, description="Số bài xử lý mỗi batch")

class IndexRunResponse(BaseModel):
    """Trả về ngay lập tức khi submit job. Poll /index/status/{job_id} để xem tiến trình."""
    job_id: str
    status: JobStatus
    message: str

class JobProgressResponse(BaseModel):
    job_id: str
    job_type: str
    status: JobStatus
    params: dict
    progress: dict
    result: Optional[dict] = None
    error: Optional[str] = None
    created_at: float
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    elapsed_seconds: Optional[float] = None

class JobListResponse(BaseModel):
    jobs: list[JobProgressResponse]

class IndexStatsResponse(BaseModel):
    index_name: str
    total_chunks: int
    size_bytes: int
    exists: bool

class IndexResetResponse(BaseModel):
    message: str
