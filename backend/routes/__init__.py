"""Rotas da API."""

from fastapi import APIRouter

from .agent import router as agent_router
from .detect import router as detect_router
from .history import router as history_router
from .jobs import router as jobs_router
from .point import router as point_router

api_router = APIRouter(prefix="/api/v1", tags=["api"])

api_router.include_router(agent_router, prefix="/agent", tags=["agent"])
api_router.include_router(history_router, prefix="/history", tags=["history"])
api_router.include_router(jobs_router, prefix="/jobs", tags=["jobs"])
api_router.include_router(point_router, prefix="/point", tags=["point"])
api_router.include_router(detect_router, prefix="/detect", tags=["detect"])
