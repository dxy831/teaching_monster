"""
视频生成路由
"""

import asyncio
from uuid import uuid4
from typing import AsyncGenerator

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import StreamingResponse
import redis.asyncio as aioredis

from ..auth import verify_api_key
from ..config import settings
from ..schemas.request import (
    VideoGenerateRequest,
    CompetitionGenerateRequest,
    CompetitionGenerateResponse,
    EventType,
)
from ..tasks.celery_app import celery_app
from ..tasks.video_tasks import generate_video_task
from ..utils.file_utils import get_video_path

router = APIRouter(prefix="/api/v1", tags=["视频生成"])


async def _wait_for_task_result(task_id: str, timeout: int = 1800, interval: float = 2.0):
    """等待任务完成（比赛规范：30 分钟内）"""
    start_time = asyncio.get_event_loop().time()
    while True:
        result = AsyncResult(task_id, app=celery_app)
        if result.ready():
            if result.successful():
                return result.result
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(result.result)
            )

        if asyncio.get_event_loop().time() - start_time > timeout:
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="比赛任务超时"
            )

        await asyncio.sleep(interval)


def _build_public_file_url(request: Request, filename: str) -> str:
    return str(request.url_for("public_download_file", filename=filename))


async def sse_event_generator(channel_name: str) -> AsyncGenerator[str, None]:
    """
    SSE 事件生成器
    
    从 Redis 订阅频道读取事件并生成 SSE 流
    
    Args:
        channel_name: Redis 频道名称
        
    Yields:
        SSE 格式的事件字符串
    """
    # 创建异步 Redis 客户端
    redis_client = await aioredis.from_url(settings.redis_url)
    pubsub = redis_client.pubsub()
    
    try:
        await pubsub.subscribe(channel_name)
        
        # 设置超时时间（比赛规范：30 分钟）
        timeout = 1800
        start_time = asyncio.get_event_loop().time()
        
        while True:
            # 检查超时
            if asyncio.get_event_loop().time() - start_time > timeout:
                yield f"event: {EventType.FAILED.value}\ndata: {{\"message\": \"任务超时\"}}\n\n"
                break
            
            # 获取消息（非阻塞，带超时）
            try:
                message = await asyncio.wait_for(
                    pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0),
                    timeout=5.0
                )
            except asyncio.TimeoutError:
                # 发送心跳保持连接
                yield ": heartbeat\n\n"
                continue
            
            if message is None:
                # 发送心跳保持连接
                yield ": heartbeat\n\n"
                await asyncio.sleep(0.1)
                continue
            
            data = message.get("data")
            if data:
                # 解码消息
                if isinstance(data, bytes):
                    data = data.decode("utf-8")
                
                # 检查结束信号
                if data == "__END__":
                    break
                
                # 直接转发 SSE 事件
                yield data
                
                # 如果是 result 事件，结束流
                if "event: result" in data:
                    break
    
    except Exception as e:
        yield f"event: {EventType.FAILED.value}\ndata: {{\"message\": \"流式传输错误: {str(e)}\"}}\n\n"
    
    finally:
        await pubsub.unsubscribe(channel_name)
        await pubsub.close()
        await redis_client.close()


@router.post("/generate-video")
async def generate_video(
    request: VideoGenerateRequest,
    api_key: str = Depends(verify_api_key)
):
    """
    生成教学视频
    
    接收知识点和用户配置，异步生成教学视频，通过 SSE 流式返回进度。
    
    **请求示例**:
    ```json
    {
        "knowledge_point": "二分搜索",
        "age": 20,
        "gender": "男",
        "language": "Python",
        "duration": 5,
        "extra_info": "我是大学生，有一定编程基础"
    }
    ```
    
    **响应格式** (SSE):
    ```
    event: running
    data: {"task_id":"uuid","message":"正在解析用户画像。"}
    
    event: finished
    data: {"task_id":"uuid","message":"用户画像解析成功。"}
    
    event: result
    data: {"message":"视频生成成功。","data":{"video_file":"sha256.mp4"}}
    ```
    """
    # 生成唯一的频道名称
    channel_name = f"video_task_{uuid4().hex}"
    
    # 准备请求数据
    request_data = {
        "knowledge_point": request.knowledge_point,
        "age": request.age,
        "gender": request.gender,
        "language": request.language or settings.default_language,
        "duration": request.duration or settings.default_duration,
        "extra_info": request.extra_info,
        "use_feedback": request.use_feedback,
        "use_assets": request.use_assets,
        "api_model": request.api_model or settings.default_api,
    }
    
    # 提交 Celery 任务
    try:
        task = generate_video_task.delay(request_data, channel_name)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"任务队列不可用: {str(e)}"
        )
    
    # 返回 SSE 流
    return StreamingResponse(
        sse_event_generator(channel_name),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 Nginx 缓冲
            "X-Task-ID": task.id,  # 返回 Celery 任务 ID
        }
    )


@router.post("/competition/generate", response_model=CompetitionGenerateResponse)
async def generate_competition_video(
    request: CompetitionGenerateRequest,
    raw_request: Request,
    api_key: str = Depends(verify_api_key)
):
    """比赛制式同步视频生成接口。"""
    channel_name = f"competition_video_task_{uuid4().hex}"
    request_data = {
        "request_id": request.request_id,
        "course_requirement": request.course_requirement,
        "student_persona": request.student_persona,
        "competition_mode": True,
    }

    try:
        task = generate_video_task.delay(request_data, channel_name)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"任务队列不可用: {str(e)}"
        )

    result = await _wait_for_task_result(task.id)

    video_file = result.get("video_file")
    if not video_file or not get_video_path(video_file):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="视频生成完成但文件不可下载"
        )

    subtitle_file = result.get("subtitle_file")
    subtitle_url = None
    if subtitle_file and get_video_path(subtitle_file):
        subtitle_url = _build_public_file_url(raw_request, subtitle_file)

    response = CompetitionGenerateResponse(
        request_id=request.request_id,
        video_url=_build_public_file_url(raw_request, video_file),
        subtitle_url=subtitle_url,
        supplementary_url=[],
    )
    expires_at = (result.get("metadata") or {}).get("public_link_expires_at")
    if expires_at:
        raw_request.state.public_link_expires_at = expires_at
    return response


@router.get("/tasks/{task_id}")
async def get_task_status(
    task_id: str,
    api_key: str = Depends(verify_api_key)
):
    """
    查询任务状态
    
    用于断线重连后查询任务的最终状态。
    
    **注意**: 此接口返回的是 Celery 任务的状态，不是实时进度。
    实时进度请使用 SSE 流。
    """
    from celery.result import AsyncResult
    from ..tasks.celery_app import celery_app
    
    result = AsyncResult(task_id, app=celery_app)
    
    response = {
        "task_id": task_id,
        "status": result.status,
        "result": None,
        "error": None,
    }
    
    if result.ready():
        if result.successful():
            response["result"] = result.result
        else:
            response["error"] = str(result.result)
    
    return response
