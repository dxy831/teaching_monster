"""
健康检查路由
"""

from fastapi import APIRouter

from ..config import settings
from ..schemas.request import HealthResponse
from .. import __version__

router = APIRouter(tags=["健康检查"])


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """健康检查接口。"""
    from src.utils import get_optimal_workers

    workers = settings.max_workers or get_optimal_workers()
    return HealthResponse(
        status="ok",
        generation_mode="synchronous",
        workers=workers,
        version=__version__,
    )


@router.get("/")
async def root():
    """根路径。"""
    return {
        "service": "Code2Video API",
        "version": __version__,
        "docs": "/docs",
        "health": "/health",
        "generation_mode": "synchronous",
    }
