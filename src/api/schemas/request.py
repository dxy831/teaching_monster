"""
请求和响应模型定义
"""

from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class DifficultyLevel(str, Enum):
    """难度等级枚举"""
    SIMPLE = "simple"
    MEDIUM = "medium"
    HARD = "hard"


class VideoGenerateRequest(BaseModel):
    """视频生成请求模型"""

    knowledge_point: str = Field(
        ...,
        description="要生成视频的知识点",
        examples=["二分搜索", "快速排序", "递归"],
    )
    age: Optional[int] = Field(None, ge=1, le=120, description="用户年龄")
    gender: Optional[str] = Field(None, description="用户性别", examples=["男", "女"])
    language: Optional[str] = Field("Python", description="编程语言", examples=["Python", "Java", "C++", "JavaScript"])
    duration: Optional[int] = Field(5, ge=1, le=30, description="视频时长（分钟）")
    difficulty: Optional[DifficultyLevel] = Field(
        DifficultyLevel.MEDIUM,
        description="内容难度等级（simple/medium/hard）",
        examples=["simple", "medium", "hard"],
    )
    extra_info: Optional[str] = Field(
        None,
        description="额外的用户信息描述（自然语言）",
        examples=["目标是利用暑假成功入门Python,完成一个自己的小项目,目前已有的知识储备是Python的输入输出语法和最基础的函数的语法"],
    )
    use_feedback: Optional[bool] = Field(True, description="是否使用 MLLM 反馈优化")
    use_assets: Optional[bool] = Field(True, description="是否使用外部素材")
    api_model: Optional[str] = Field(
        None,
        description="指定使用的 LLM API 模型",
        examples=["claude", "gpt-4o", "gpt-5", "Gemini"],
    )

    class Config:
        json_schema_extra = {
            "example": {
                "knowledge_point": "二分搜索",
                "age": 20,
                "gender": "男",
                "language": "Python",
                "duration": 5,
                "difficulty": "medium",
                "extra_info": "我是大学生，有一定编程基础，想深入理解算法",
            }
        }


class CompetitionGenerateRequest(BaseModel):
    """比赛制式的视频生成请求"""

    request_id: str = Field(..., description="请求唯一标识")
    course_requirement: str = Field(..., description="课程需求与学习目标")
    student_persona: str = Field(..., description="学生背景自述")

    class Config:
        json_schema_extra = {
            "example": {
                "request_id": "req-001",
                "course_requirement": "Create an AP-level computer science lesson on binary search, including intuition, step-by-step trace, complexity, and a final review.",
                "student_persona": "I am a high school student with basic programming experience but I have never learned binary search before.",
            }
        }


class CompetitionGenerateResponse(BaseModel):
    """比赛制式的视频生成响应"""

    request_id: str = Field(..., description="请求唯一标识")
    video_url: str = Field(..., description="生成视频的公开下载直链")
    subtitle_url: Optional[str] = Field(None, description="字幕文件公开下载直链")
    supplementary_url: List[str] = Field(default_factory=list, description="辅助材料下载直链列表")


class VideoGenerateResponse(BaseModel):
    """同步视频生成结果响应"""

    message: str = Field(..., description="结果消息")
    data: Dict[str, Any] = Field(..., description="结果数据")

    class Config:
        json_schema_extra = {
            "example": {
                "message": "视频生成成功。",
                "data": {
                    "video_file": "a1b2c3d4e5f6.mp4",
                    "video_url": "https://example.com/api/v1/public/files/a1b2c3d4e5f6.mp4",
                    "subtitle_file": "a1b2c3d4e5f6.srt",
                    "subtitle_url": "https://example.com/api/v1/public/files/a1b2c3d4e5f6.srt",
                    "supplementary_url": [],
                    "token_usage": {
                        "prompt_tokens": 10000,
                        "completion_tokens": 5000,
                        "total_tokens": 15000,
                    },
                    "metadata": {},
                },
            }
        }


class HealthResponse(BaseModel):
    """健康检查响应"""

    status: str = Field(..., description="服务状态")
    generation_mode: str = Field(..., description="生成模式")
    workers: int = Field(..., description="生成并发配置")
    version: str = Field(..., description="API 版本")
