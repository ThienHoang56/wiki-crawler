import threading
from fastapi import HTTPException
from sqlalchemy.orm import Session
from src.core.job_store import job_store
from src.services.index_service import index_service
from src.schemas.index_schema import (
    IndexRunRequest, IndexRunResponse,
    IndexStatsResponse, IndexResetResponse,
    JobProgressResponse, JobListResponse,
)

class IndexController:
    def run(self, req: IndexRunRequest) -> IndexRunResponse:
        """
        Tạo background job, trả về job_id ngay lập tức.
        Chạy indexing trong thread riêng để không block API.
        """
        job = job_store.create(
            job_type="index_run",
            params={"batch_size": req.batch_size},
        )

        def _run():
            index_service.run_background(job, batch_size=req.batch_size)

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()

        return IndexRunResponse(
            job_id=job.id,
            status=job.status,
            message=f"Job đã được tạo. Poll GET /api/v1/index/status/{job.id} để theo dõi tiến trình.",
        )

    def get_job_status(self, job_id: str) -> JobProgressResponse:
        job = job_store.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail=f"Không tìm thấy job '{job_id}'")
        return JobProgressResponse(**job.to_dict())

    def list_jobs(self) -> JobListResponse:
        jobs = job_store.list_recent(limit=20)
        return JobListResponse(jobs=[JobProgressResponse(**j.to_dict()) for j in jobs])

    def get_stats(self) -> IndexStatsResponse:
        return IndexStatsResponse(**index_service.get_stats())

    def reset(self, db: Session) -> IndexResetResponse:
        try:
            return IndexResetResponse(**index_service.reset(db))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
