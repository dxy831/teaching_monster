"""
配置管理模块
支持环境变量和配置文件
"""

import os
import pathlib
from typing import List, Optional
from dataclasses import dataclass, field


@dataclass
class Settings:
    """应用配置"""

    api_keys: List[str] = field(default_factory=list)
    api_host: str = "0.0.0.0"
    api_port: int = 8080
    max_workers: Optional[int] = None
    storage_root: str = "data/outputs"
    video_dir: str = "data/outputs/videos"
    metadata_dir: str = "data/outputs/metadata"
    storage_base_url: str = ""
    oss_enabled: bool = False
    oss_endpoint: str = ""
    oss_bucket_name: str = ""
    oss_access_key_id: str = ""
    oss_access_key_secret: str = ""
    oss_key_prefix: str = "competition-outputs"
    oss_url_expire_seconds: int = 172800
    default_api: str = "claude"
    default_duration: int = 5
    default_language: str = "Python"
    debug: bool = False

    def __post_init__(self):
        api_keys_env = os.getenv("API_KEYS", "")
        if api_keys_env:
            self.api_keys = [k.strip() for k in api_keys_env.split(",") if k.strip()]

        if not self.api_keys:
            self.api_keys = ["dev-api-key-12345"]

        max_workers_env = os.getenv("MAX_WORKERS")
        if max_workers_env:
            self.max_workers = int(max_workers_env)

        self.storage_root = os.getenv("STORAGE_ROOT", self.storage_root)
        self.video_dir = os.path.join(self.storage_root, "videos")
        self.metadata_dir = os.path.join(self.storage_root, "metadata")
        self.storage_base_url = os.getenv("STORAGE_BASE_URL", self.storage_base_url).rstrip("/")

        self.oss_enabled = os.getenv("OSS_ENABLED", "false").lower() in ("true", "1", "yes")
        self.oss_endpoint = os.getenv("OSS_ENDPOINT", self.oss_endpoint)
        self.oss_bucket_name = os.getenv("OSS_BUCKET_NAME", self.oss_bucket_name)
        self.oss_access_key_id = os.getenv("OSS_ACCESS_KEY_ID", self.oss_access_key_id)
        self.oss_access_key_secret = os.getenv("OSS_ACCESS_KEY_SECRET", self.oss_access_key_secret)
        self.oss_key_prefix = os.getenv("OSS_KEY_PREFIX", self.oss_key_prefix).strip("/")
        self.oss_url_expire_seconds = int(os.getenv("OSS_URL_EXPIRE_SECONDS", str(self.oss_url_expire_seconds)))
        self.default_api = os.getenv("DEFAULT_API", self.default_api)
        self.debug = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")
        self._ensure_directories()

    def _ensure_directories(self):
        for dir_path in [self.storage_root, self.video_dir, self.metadata_dir]:
            pathlib.Path(dir_path).mkdir(parents=True, exist_ok=True)

    def is_valid_api_key(self, api_key: str) -> bool:
        return api_key in self.api_keys


settings = Settings()
