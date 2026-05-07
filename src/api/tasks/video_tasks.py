"""
视频生成执行入口
"""

import sys
from pathlib import Path
from typing import Any, Dict

current_dir = Path(__file__).resolve().parent
src_dir = current_dir.parent.parent
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from ..config import settings
from ..execution import ExecutionContext, execute_video_generation


def run_video_generation(request_data: Dict[str, Any]) -> Dict[str, Any]:
    return execute_video_generation(
        ExecutionContext(
            request_data=request_data,
            settings_obj=settings,
            src_dir=src_dir,
            output_root=src_dir / "CASES",
        )
    )
