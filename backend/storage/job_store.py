"""
Job Store — async upload tracking.
Holds in-memory state for background upload jobs.
Jobs expire after 1 hour.
"""

import time
import uuid
from dataclasses import dataclass, field

JOB_TTL = 3600  # seconds

@dataclass
class UploadJob:
    job_id:     str
    filename:   str
    status:     str         = "processing"  # processing | done | failed
    result:     dict | None = None
    error:      str  | None = None
    created_at: float       = field(default_factory=time.time)


_jobs: dict[str, UploadJob] = {}


def create_job(filename: str) -> str:
    _evict()
    job_id = str(uuid.uuid4())
    _jobs[job_id] = UploadJob(job_id=job_id, filename=filename)
    return job_id


def get_job(job_id: str) -> UploadJob | None:
    return _jobs.get(job_id)


def complete_job(job_id: str, result: dict):
    if job_id in _jobs:
        _jobs[job_id].status = "done"
        _jobs[job_id].result = result


def fail_job(job_id: str, error: str):
    if job_id in _jobs:
        _jobs[job_id].status = "failed"
        _jobs[job_id].error  = error


def _evict():
    cutoff = time.time() - JOB_TTL
    stale  = [jid for jid, j in _jobs.items() if j.created_at < cutoff]
    for jid in stale:
        del _jobs[jid]
