"""
Code2Video API 服务主入口

启动方式:
    uvicorn api.main:app --reload --port 8080

或者直接运行:
    python -m api.main
"""

import sys
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

current_dir = Path(__file__).resolve().parent
src_dir = current_dir.parent
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from .config import settings
from .routes import files_router, health_router, video_router
from . import __version__


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"Code2Video API v{__version__} 启动中...")
    print(f"视频存储目录: {settings.video_dir}")
    print(f"API Keys 数量: {len(settings.api_keys)}")
    yield
    print("Code2Video API 关闭")


app = FastAPI(
    title="Code2Video API",
    description="""
## 知识点转视频 API 服务

将学习需求同步生成可下载教学视频的后端服务。

### 主要功能

- **同步生成**: 请求到达后立即开始生成，待文件可下载后返回 JSON 结果
- **比赛接口**: 提供标准 JSON 输入输出的比赛制式接口
- **文件下载**: 支持公开直链与断点续传

### 认证方式

除健康检查与比赛接口 `/api/v1/competition/generate` 外，其他接口都需要在请求头中携带 API Key:

```
X-API-Key: your-api-key
```
    """,
    version=__version__,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "detail": f"服务器内部错误: {str(exc)}",
            "type": type(exc).__name__,
        },
    )


app.include_router(health_router)
app.include_router(video_router)
app.include_router(files_router)


def main():
    import uvicorn

    uvicorn.run(
        "api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
        log_level="info",
    )


if __name__ == "__main__":
    main()
