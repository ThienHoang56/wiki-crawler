from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from src.core.database import get_db
from src.controller.index_controller import IndexController
from src.schemas.index_schema import (
    IndexRunRequest, IndexRunResponse,
    IndexStatsResponse, IndexResetResponse,
    JobProgressResponse, JobListResponse,
)

router = APIRouter(prefix="/api/v1/index", tags=["3. Index"])
controller = IndexController()

@router.get(
    "/stats",
    response_model=IndexStatsResponse,
    summary="Thống kê Elasticsearch index",
)
def get_stats():
    return controller.get_stats()

@router.post(
    "/run",
    response_model=IndexRunResponse,
    summary="Chạy indexing pipeline (async, trả về job_id ngay)",
)
def run_index(req: IndexRunRequest = IndexRunRequest()):
    """
    Submit indexing job. **Không block** — trả về `job_id` ngay lập tức.

    Pipeline: PostgreSQL (unindexed) → Clean → Chunk → Embed → Elasticsearch Bulk.

    Theo dõi tiến trình qua `GET /api/v1/index/status/{job_id}`.
    """
    return controller.run(req)

@router.get(
    "/status/{job_id}",
    response_model=JobProgressResponse,
    summary="Kiểm tra tiến trình của một job",
)
def get_job_status(job_id: str):
    """
    Poll endpoint để theo dõi tiến trình indexing job.

    **Trạng thái có thể có:**
    - `pending` — đã tạo, chưa chạy
    - `running` — đang chạy, xem `progress.percent`
    - `done` — hoàn thành, xem `result`
    - `failed` — thất bại, xem `error`
    """
    return controller.get_job_status(job_id)

@router.get(
    "/jobs",
    response_model=JobListResponse,
    summary="Danh sách các jobs gần đây",
)
def list_jobs():
    """Xem tối đa 20 jobs gần nhất (mọi trạng thái)."""
    return controller.list_jobs()

@router.post(
    "/reset",
    response_model=IndexResetResponse,
    summary="Reset toàn bộ Elasticsearch index",
)
def reset_index(db: Session = Depends(get_db)):
    """**Cẩn thận:** Xóa toàn bộ dữ liệu ES và reset cờ `is_indexed` trong PostgreSQL."""
    return controller.reset(db)
