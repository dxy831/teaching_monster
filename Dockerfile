# ============================================================================
# Code2Video Docker 镜像
# 基于 Python 3.11 + Manim 依赖（LaTeX, ffmpeg, cairo, pango, 英文字体）
# ============================================================================

FROM python:3.11-slim AS base

ENV DEBIAN_FRONTEND=noninteractive

RUN sed -i 's|deb.debian.org|mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list.d/debian.sources 2>/dev/null || \
    sed -i 's|deb.debian.org|mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list 2>/dev/null || true

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libcairo2-dev \
    libpango1.0-dev \
    pkg-config \
    libegl1 \
    libgl1 \
    libgles2 \
    fonts-noto-core \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN apt-get update && \
    for i in 1 2 3; do \
        apt-get install -y --no-install-recommends --fix-missing \
            texlive-latex-base \
            texlive-latex-extra \
            texlive-fonts-recommended \
        && break || (echo "=== Retry $i ===" && sleep 5 && apt-get update); \
    done && \
    for i in 1 2 3; do \
        apt-get install -y --no-install-recommends --fix-missing \
            texlive-fonts-extra \
        && break || (echo "=== Retry $i ===" && sleep 5 && apt-get update); \
    done && \
    for i in 1 2 3; do \
        apt-get install -y --no-install-recommends --fix-missing \
            texlive-science \
        && break || (echo "=== Retry $i ===" && sleep 5 && apt-get update); \
    done && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml ./

RUN pip install --no-cache-dir --upgrade pip \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --timeout 120 --retries 5 && \
    pip install --no-cache-dir . \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --timeout 120 --retries 5

COPY src/ ./src/
COPY prompts/ ./prompts/

RUN mkdir -p data/outputs/videos data/outputs/metadata src/CASES

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    API_HOST=0.0.0.0 \
    API_PORT=8080 \
    STORAGE_ROOT=data/outputs

EXPOSE 8080

CMD ["python", "-m", "uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8080"]
