"""
视频生成路由
"""

import asyncio
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request, status

from ..auth import verify_api_key
from ..config import settings
from ..schemas.request import (
    CompetitionGenerateRequest,
    CompetitionGenerateResponse,
    VideoGenerateRequest,
    VideoGenerateResponse,
)
from ..tasks.video_tasks import run_video_generation
from ..utils.file_utils import get_file_size, get_video_path

router = APIRouter(prefix="/api/v1", tags=["视频生成"])
_generation_semaphore = asyncio.Semaphore(1)
MAX_SUPPLEMENTARY_FILES = 5
MAX_AUXILIARY_BYTES = 100 * 1024 * 1024


async def _run_generation(request_data: Dict[str, Any]) -> Dict[str, Any]:
    async with _generation_semaphore:
        return await asyncio.to_thread(run_video_generation, request_data)


def _build_public_file_url(request: Request, filename: str) -> str:
    return str(request.url_for("public_download_file", filename=filename))


def _ensure_downloadable_file(filename: str | None, detail: str) -> str:
    if not filename or not get_video_path(filename):
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=detail)
    return filename


def _collect_auxiliary_files(result: Dict[str, Any]) -> list[str]:
    files: list[str] = []
    subtitle_file = result.get("subtitle_file")
    if subtitle_file:
        files.append(subtitle_file)

    metadata = result.get("metadata") or {}
    supplementary_files = metadata.get("supplementary_files") or []
    for item in supplementary_files:
        if isinstance(item, str) and item not in files:
            files.append(item)
    return files


def _validate_auxiliary_files(result: Dict[str, Any]) -> tuple[str | None, list[str]]:
    subtitle_file = result.get("subtitle_file")
    if subtitle_file:
        _ensure_downloadable_file(subtitle_file, "字幕生成完成但文件不可下载")

    supplementary_files = []
    total_size = 0
    for filename in _collect_auxiliary_files(result):
        path = get_video_path(filename)
        if not path:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"附属文件不可下载: {filename}")
        total_size += get_file_size(path)
        if filename != subtitle_file:
            supplementary_files.append(filename)

    if len(supplementary_files) > MAX_SUPPLEMENTARY_FILES:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="辅助教材数量超过 5 个")
    if total_size > MAX_AUXILIARY_BYTES:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="字幕与辅助教材总大小超过 100MB")

    return subtitle_file, supplementary_files


def _ensure_success(result: Dict[str, Any]) -> Dict[str, Any]:
    if result.get("success"):
        return result
    detail = result.get("error") or "视频生成失败"
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=detail)


@router.post("/generate-video", response_model=VideoGenerateResponse)
async def generate_video(
    request: VideoGenerateRequest,
    raw_request: Request,
    api_key: str = Depends(verify_api_key),
):
    """同步生成教学视频并在文件可下载后返回结果。"""
    request_data = {
        "knowledge_point": request.knowledge_point,
        "age": request.age,
        "gender": request.gender,
        "language": request.language or settings.default_language,
        "duration": request.duration or settings.default_duration,
        "difficulty": request.difficulty.value if request.difficulty else "medium",
        "extra_info": request.extra_info,
        "use_feedback": request.use_feedback,
        "use_assets": request.use_assets,
        "api_model": request.api_model or settings.default_api,
    }

    result = _ensure_success(await _run_generation(request_data))
    video_file = _ensure_downloadable_file(result.get("video_file"), "视频生成完成但文件不可下载")
    subtitle_file, supplementary_files = _validate_auxiliary_files(result)

    data: Dict[str, Any] = {
        "video_file": video_file,
        "video_url": _build_public_file_url(raw_request, video_file),
        "subtitle_file": subtitle_file,
        "subtitle_url": _build_public_file_url(raw_request, subtitle_file) if subtitle_file else None,
        "supplementary_url": [_build_public_file_url(raw_request, filename) for filename in supplementary_files],
        "token_usage": result.get("token_usage"),
        "metadata": result.get("metadata"),
    }

    return VideoGenerateResponse(message="视频生成成功。", data=data)


@router.post("/competition/generate", response_model=CompetitionGenerateResponse)
async def generate_competition_video(
    request: CompetitionGenerateRequest,
    raw_request: Request,
):
    """比赛制式同步视频生成接口。"""
    request_data = {
        "request_id": request.request_id,
        "course_requirement": request.course_requirement,
        "student_persona": request.student_persona,
        "competition_mode": True,
    }

    result = _ensure_success(await _run_generation(request_data))
    video_file = _ensure_downloadable_file(result.get("video_file"), "视频生成完成但文件不可下载")
    subtitle_file, supplementary_files = _validate_auxiliary_files(result)

    response = CompetitionGenerateResponse(
        request_id=request.request_id,
        video_url=_build_public_file_url(raw_request, video_file),
        subtitle_url=_build_public_file_url(raw_request, subtitle_file) if subtitle_file else None,
        supplementary_url=[_build_public_file_url(raw_request, filename) for filename in supplementary_files],
    )
    expires_at = (result.get("metadata") or {}).get("public_link_expires_at")
    if expires_at:
        raw_request.state.public_link_expires_at = expires_at
    return response
