"""
视频生成 Celery 任务
"""

import sys
from pathlib import Path
from typing import Any, Dict

import redis

current_dir = Path(__file__).resolve().parent
src_dir = current_dir.parent.parent
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from .celery_app import celery_app
from ..config import settings
from ..execution import ExecutionContext, ExecutionHooks, execute_video_generation
from ..utils.sse import SyncTaskProgressCallback


@celery_app.task(bind=True, name="src.api.tasks.video_tasks.generate_video_task")
def generate_video_task(self, request_data: Dict[str, Any], channel_name: str) -> Dict[str, Any]:
    redis_client = redis.from_url(settings.redis_url)
    callback = SyncTaskProgressCallback(redis_client, channel_name)

    hooks = ExecutionHooks(
        on_stage_start=callback.on_stage_start,
        on_stage_finish=callback.on_stage_finish,
        on_stage_failed=callback.on_stage_failed,
        on_result=callback.on_result,
    )

    try:
        return execute_video_generation(
            ExecutionContext(
                request_data=request_data,
                settings_obj=settings,
                src_dir=src_dir,
                output_root=src_dir / "CASES",
                hooks=hooks,
            )
        )
    finally:
        redis_client.close()
