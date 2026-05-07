"""
Pydantic 模型定义
"""

from .request import (
    CompetitionGenerateRequest,
    CompetitionGenerateResponse,
    HealthResponse,
    VideoGenerateRequest,
    VideoGenerateResponse,
)

__all__ = [
    "CompetitionGenerateRequest",
    "CompetitionGenerateResponse",
    "HealthResponse",
    "VideoGenerateRequest",
    "VideoGenerateResponse",
]
