"""
In-memory job store cho background tasks.
Lưu trạng thái tiến trình của các jobs đang chạy / đã xong.

Với production scale, đổi sang Redis:
  HSET job:{id} status running progress 50 ...
"""
from __future__ import annotations
import uuid
import time
from enum import Enum
from typing import Optional

class JobStatus(str, Enum):
    PENDING  = "pending"
    RUNNING  = "running"
    DONE     = "done"
    FAILED   = "failed"

class Job:
    def __init__(self, job_type: str, params: dict):
        self.id         = str(uuid.uuid4())
        self.job_type   = job_type
        self.params     = params
        self.status     = JobStatus.PENDING
        self.created_at = time.time()
        self.started_at: Optional[float] = None
        self.finished_at: Optional[float] = None
        self.progress: dict = {}   # {"articles_processed": 0, "chunks_indexed": 0, ...}
        self.result: Optional[dict] = None
        self.error: Optional[str]   = None

    def to_dict(self) -> dict:
        return {
            "job_id":          self.id,
            "job_type":        self.job_type,
            "status":          self.status,
            "params":          self.params,
            "progress":        self.progress,
            "result":          self.result,
            "error":           self.error,
            "created_at":      self.created_at,
            "started_at":      self.started_at,
            "finished_at":     self.finished_at,
            "elapsed_seconds": round(
                (self.finished_at or time.time()) - (self.started_at or self.created_at), 2
            ) if self.started_at else None,
        }


class JobStore:
    """Thread-safe in-memory store cho jobs."""
    _jobs: dict[str, Job] = {}

    def create(self, job_type: str, params: dict) -> Job:
        job = Job(job_type, params)
        self._jobs[job.id] = job
        return job

    def get(self, job_id: str) -> Optional[Job]:
        return self._jobs.get(job_id)

    def list_recent(self, limit: int = 20) -> list[Job]:
        jobs = sorted(self._jobs.values(), key=lambda j: j.created_at, reverse=True)
        return jobs[:limit]


job_store = JobStore()
