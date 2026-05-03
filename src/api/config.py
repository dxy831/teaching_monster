"""
配置管理模块
支持环境变量和配置文件
"""

import os
import json
import pathlib
from typing import List, Optional
from dataclasses import dataclass, field


@dataclass
class Settings:
    """应用配置"""
    
    # API 配置
    api_keys: List[str] = field(default_factory=list)
    api_host: str = "0.0.0.0"
    api_port: int = 8080
    
    # Redis 配置
    redis_url: str = "redis://localhost:6379/0"
    
    # Celery 配置
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/0"
    
    # 并发配置
    max_workers: Optional[int] = None  # None 表示自动检测
    
    # 文件存储配置
    output_dir: str = "data/outputs"
    video_dir: str = "data/outputs/videos"
    metadata_dir: str = "data/outputs/metadata"

    # OSS 配置
    oss_enabled: bool = False
    oss_endpoint: str = ""
    oss_bucket_name: str = ""
    oss_access_key_id: str = ""
    oss_access_key_secret: str = ""
    oss_key_prefix: str = "competition-outputs"
    oss_url_expire_seconds: int = 172800
    
    # LLM API 配置
    default_api: str = "claude"
    
    # 视频生成默认配置
    default_duration: int = 5
    default_language: str = "Python"
    
    # 调试模式
    debug: bool = False
    
    def __post_init__(self):
        """从环境变量加载配置"""
        # API Keys (逗号分隔)
        api_keys_env = os.getenv("API_KEYS", "")
        if api_keys_env:
            self.api_keys = [k.strip() for k in api_keys_env.split(",") if k.strip()]
        
        # 如果没有配置 API Keys，使用默认的开发密钥
        if not self.api_keys:
            self.api_keys = ["dev-api-key-12345"]
        
        # Redis
        self.redis_url = os.getenv("REDIS_URL", self.redis_url)
        self.celery_broker_url = os.getenv("CELERY_BROKER_URL", self.redis_url)
        self.celery_result_backend = os.getenv("CELERY_RESULT_BACKEND", self.redis_url)
        
        # 并发
        max_workers_env = os.getenv("MAX_WORKERS")
        if max_workers_env:
            self.max_workers = int(max_workers_env)
        
        # 文件存储
        self.output_dir = os.getenv("OUTPUT_DIR", self.output_dir)
        self.video_dir = os.getenv("VIDEO_DIR", os.path.join(self.output_dir, "videos"))
        self.metadata_dir = os.getenv("METADATA_DIR", os.path.join(self.output_dir, "metadata"))

        # OSS
        self.oss_enabled = os.getenv("OSS_ENABLED", "false").lower() in ("true", "1", "yes")
        self.oss_endpoint = os.getenv("OSS_ENDPOINT", self.oss_endpoint)
        self.oss_bucket_name = os.getenv("OSS_BUCKET_NAME", self.oss_bucket_name)
        self.oss_access_key_id = os.getenv("OSS_ACCESS_KEY_ID", self.oss_access_key_id)
        self.oss_access_key_secret = os.getenv("OSS_ACCESS_KEY_SECRET", self.oss_access_key_secret)
        self.oss_key_prefix = os.getenv("OSS_KEY_PREFIX", self.oss_key_prefix).strip("/")
        self.oss_url_expire_seconds = int(os.getenv("OSS_URL_EXPIRE_SECONDS", str(self.oss_url_expire_seconds)))
        
        # LLM API
        self.default_api = os.getenv("DEFAULT_API", self.default_api)
        
        # 调试模式
        self.debug = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")
        
        # 确保目录存在
        self._ensure_directories()
    
    def _ensure_directories(self):
        """确保必要的目录存在"""
        for dir_path in [self.output_dir, self.video_dir, self.metadata_dir]:
            pathlib.Path(dir_path).mkdir(parents=True, exist_ok=True)
    
    def is_valid_api_key(self, api_key: str) -> bool:
        """验证 API Key 是否有效"""
        return api_key in self.api_keys


# 全局配置实例
settings = Settings()
