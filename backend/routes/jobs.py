"""Rotas para acompanhar jobs (RQ)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from services.queue_service import get_queue

router = APIRouter()


@router.get(
    "/{job_id}",
    summary="Status de um job de análise",
    description="Retorna queued|processing|done|failed e, quando done, o payload do resultado.",
)
def job_status(job_id: str) -> dict:
    q = get_queue()
    job = q.fetch_job(job_id)
    if not job:
        raise HTTPException(404, "Job não encontrado")

    if job.is_finished:
        return {"job_id": job.id, "status": "done", "result": job.result}
    if job.is_failed:
        err = (job.exc_info or "").strip()
        if err:
            err = err.splitlines()[-1].strip()[:180]
        return {"job_id": job.id, "status": "failed", "error": err or None}

    return {
        "job_id": job.id,
        "status": "processing" if job.started_at else "queued",
    }

