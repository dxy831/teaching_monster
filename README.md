# Code2Video API 接入文档

> **编程知识点讲解视频自动生成服务** — 传入知识点和用户信息，自动生成 Manim 动画讲解视频。

---

## 📌 基本信息

| 项目 | 值 |
|------|-----|
| **Base URL** | `http://{server}:8080` |
| **协议** | HTTP |
| **数据格式** | JSON |
| **认证方式** | 请求头 `X-API-Key` |
| **API 文档** | `http://{server}:8080/docs`（Swagger UI） |

---

## 🔑 认证

所有 `/api/v1/*` 接口需要在请求头中携带 API Key：

```bash
X-API-Key: dev-api-key-12345
```

如果没有设置环境变量 `API_KEYS`，服务会默认使用 `dev-api-key-12345` 作为开发密钥。

> 生产环境请使用安全的 API Key，不要使用默认开发密钥。

---

## 📋 接口总览

| 接口 | 方法 | 认证 | 说明 |
|------|------|:----:|------|
| `/` | GET | ❌ | 服务信息 |
| `/health` | GET | ❌ | 健康检查 |
| `/docs` | GET | ❌ | Swagger API 文档 |
| `/api/v1/generate-video` | POST | ✅ | 生成视频（SSE 流式返回） |
| `/api/v1/competition/generate` | POST | ✅ | 比赛模式同步生成视频 |
| `/api/v1/tasks/{task_id}` | GET | ✅ | 查询任务状态 |
| `/api/v1/files/{filename}` | GET | ✅ | 下载文件（支持 Range） |
| `/api/v1/files/{filename}` | HEAD | ✅ | 获取文件信息 |
| `/api/v1/files/{filename}/metadata` | GET | ✅ | 获取视频元信息 |
| `/api/v1/public/files/{filename}` | GET | ❌ | 公共直链下载（比赛直链） |
| `/api/v1/public/files/{filename}` | HEAD | ❌ | 公共直链 HEAD 请求 |

---

## 🎬 核心接口：生成视频

### `POST /api/v1/generate-video`

提交知识点和用户配置，服务端异步生成教学视频，并通过 **SSE（Server-Sent Events）** 实时返回进度。

### 请求格式

**Content-Type**: `application/json`

**请求体字段说明**：

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|:----:|--------|------|
| `knowledge_point` | string | ✅ | - | 要生成视频的知识点 |
| `age` | int | ❌ | null | 用户年龄（1-120） |
| `gender` | string | ❌ | null | 用户性别 |
| `language` | string | ❌ | `Python` | 编程语言 |
| `duration` | int | ❌ | `5` | 视频时长，单位：分钟（1-30） |
| `difficulty` | string | ❌ | `medium` | 难度：`simple` / `medium` / `hard` |
| `extra_info` | string | ❌ | null | 用户补充信息 |
| `use_feedback` | bool | ❌ | `true` | 是否启用 MLLM 反馈优化 |
| `use_assets` | bool | ❌ | `true` | 是否使用外部素材 |
| `api_model` | string | ❌ | 服务端默认 | 指定 LLM 模型，如 `claude`、`gpt-4o`、`gpt-5`、`Gemini` |

### 示例请求

```bash
curl -N -X POST http://localhost:8080/api/v1/generate-video -H "Content-Type: application/json" -H "X-API-Key: dev-api-key-12345" -d '{"knowledge_point":"二分搜索","age":20,"gender":"男","language":"Python","duration":5,"difficulty":"medium","extra_info":"我是大学生，有一定编程基础，想深入理解算法"}'
```

```bash
curl -N -X POST http://localhost:8080/api/v1/generate-video -H "Content-Type: application/json" -H "X-API-Key: dev-api-key-12345" -d '{"knowledge_point":"冒泡排序"}'
```

### SSE 响应格式

响应为 `text/event-stream`，前端可使用 EventSource 或 fetch + ReadableStream 处理。

**事件类型**：

| 事件类型 | 说明 |
|----------|------|
| `running` | 任务正在执行 |
| `finished` | 某个子步骤完成 |
| `failed` | 任务失败 |
| `result` | 生成完成，包含最终结果 |

**响应示例**：

```
event: running
data: {"task_id":"uuid-xxx","message":"正在解析用户画像。"}

event: finished
data: {"task_id":"uuid-xxx","message":"用户画像解析成功。"}

event: running
data: {"task_id":"uuid-xxx","message":"正在生成视频大纲..."}

event: finished
data: {"task_id":"uuid-xxx","message":"大纲生成成功。"}

event: running
data: {"task_id":"uuid-xxx","message":"正在生成 Manim 代码..."}

event: running
data: {"task_id":"uuid-xxx","message":"正在渲染视频..."}

event: result
data: {"message":"视频生成成功。","data":{"video_file":"a1b2c3d4e5f6...sha256.mp4"}}
```

**失败示例**：

```
event: failed
data: {"task_id":"uuid-xxx","message":"视频渲染失败: 内存不足"}
```

### 重要说明

- SSE 响应会返回 `X-Task-ID` 头，可用于断线重连。
- 服务端会发送心跳 `: heartbeat`，前端无需处理。

---

## 🔍 查询任务状态

### `GET /api/v1/tasks/{task_id}`

用于断线重连后查询 Celery 任务状态。

```bash
curl -H "X-API-Key: dev-api-key-12345" http://localhost:8080/api/v1/tasks/{task_id}
```

**响应示例**：

```json
{
  "task_id": "abc123-def456-...",
  "status": "SUCCESS",
  "result": {
    "video_file": "a1b2c3d4e5f6...sha256.mp4"
  },
  "error": null
}
```

**状态说明**：

| 状态 | 含义 |
|------|------|
| `PENDING` | 等待执行 |
| `STARTED` | 正在执行 |
| `SUCCESS` | 执行成功 |
| `FAILURE` | 执行失败 |

---

## 📥 下载文件

### `GET /api/v1/files/{filename}`

下载生成的视频或资源文件。支持 `Range` 请求。

```bash
curl -H "X-API-Key: dev-api-key-12345" http://localhost:8080/api/v1/files/a1b2c3...sha256.mp4 -o video.mp4
```

```bash
curl -H "X-API-Key: dev-api-key-12345" -H "Range: bytes=0-1048575" http://localhost:8080/api/v1/files/a1b2c3...sha256.mp4 -o video_part.mp4
```

**状态码**：

| 状态码 | 含义 |
|--------|------|
| 200 | 返回完整文件 |
| 206 | 返回部分内容 |
| 404 | 文件不存在 |
| 416 | Range 范围无效 |

---

## 📄 获取文件信息

### `HEAD /api/v1/files/{filename}`

获取文件信息，不返回内容。

```bash
curl -I -H "X-API-Key: dev-api-key-12345" http://localhost:8080/api/v1/files/a1b2c3...sha256.mp4
```

**响应头示例**：

```
Content-Type: video/mp4
Content-Length: 12345678
Accept-Ranges: bytes
```

---

## 📄 获取视频元信息

### `GET /api/v1/files/{filename}/metadata`

获取视频元信息，包括知识点、生成参数和 Token 使用情况。

```bash
curl -H "X-API-Key: dev-api-key-12345" http://localhost:8080/api/v1/files/a1b2c3...sha256.mp4/metadata
```

**响应示例**：

```json
{
  "knowledge_point": "二分搜索",
  "language": "Python",
  "duration": 5,
  "token_usage": {
    "prompt_tokens": 10000,
    "completion_tokens": 5000,
    "total_tokens": 15000
  },
  "created_at": "2024-01-01T12:00:00"
}
```

---

## ❤️ 健康检查

### `GET /health`

无需认证，用于监控服务是否正常。

```bash
curl http://localhost:8080/health
```

**响应示例**：

```json
{
  "status": "ok",
  "redis": "connected",
  "workers": 4,
  "version": "1.0.0"
}
```

---

## 🖥️ 前端接入指南

### 完整调用流程

```
┌──────────┐                           ┌──────────────┐
│  前端     │                           │  Code2Video API │
│          │   POST /api/v1/generate-video     │              │
│          │ ─────────────────────────> │              │
│          │                           │
│          │   SSE: event: running      │              │
│          │ <───────────────────────── │  正在解析...  │
│          │                           │
│          │   SSE: event: finished     │              │
│          │ <───────────────────────── │  大纲完成     │
│          │                           │
│          │   SSE: event: running      │              │
│          │ <───────────────────────── │  渲染中...    │
│          │                           │
│          │   SSE: event: result       │              │
│          │ <───────────────────────── │  视频完成!    │
│          │                           │
│          │   GET /api/v1/files/{filename}    │              │
│          │ ─────────────────────────> │              │
│          │                           │
│          │   video/mp4 文件           │              │
│          │ <───────────────────────── │              │
└──────────┘                           └──────────────┘
```

### 断线重连处理

如果 SSE 连接断开，可通过 `X-Task-ID` 查询任务状态：

```javascript
async function checkTaskStatus(taskId) {
  const response = await fetch(`http://localhost:8080/api/v1/tasks/${taskId}`, {
    headers: { 'X-API-Key': 'dev-api-key-12345' },
  });
  const result = await response.json();
  
  if (result.status === 'SUCCESS') {
    downloadVideo(result.result.video_file);
  } else if (result.status === 'FAILURE') {
    console.error('任务失败:', result.error);
  } else {
    setTimeout(() => checkTaskStatus(taskId), 5000);
  }
}
```

---

## ⚠️ 注意事项

1. **视频生成耗时较长**：5 分钟视频通常需要几分钟生成，请做好 UI 提示。
2. **SSE 连接保活**：服务端会发送心跳 `: heartbeat`。
3. **SSE 超时**：长时间未完成会触发超时。
4. **文件存储**：视频文件保存在服务端，建议前端完成下载后不要长期依赖服务端存储。
5. **并发限制**：当前 Worker 使用单进程模式，多个请求可能排队执行。

---

## 🔧 后端部署参考

### 前置要求

- Docker 20.10+
- Docker Compose 2.0+
- 至少 4GB 内存
- 至少 10GB 磁盘空间

### 快速启动

```bash
git clone https://github.com/dxy831/code2video.git
cd code2video

cp .env.example .env
# 编辑 .env 修改 API_KEYS、DEFAULT_API 等配置

docker-compose up -d --build
```

### 验证服务

```bash
curl http://localhost:8080/health
```

### LLM API 密钥配置

可在 `src/api_config.json` 中配置 LLM 服务参数和密钥，也可以在 `docker-compose.yml` 中通过挂载该文件实现外部配置。

### 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `API_KEYS` | API 认证密钥（逗号分隔） | `dev-api-key-12345` |
| `DEFAULT_API` | 默认 LLM 类型 | `claude` |
| `API_PORT` | API 端口 | `8080` |
| `REDIS_PORT` | Redis 端口 | `6379` |
| `MAX_WORKERS` | 最大并发 Worker | - |
| `DEBUG` | 调试模式 | `false` |

### Docker Compose 说明

- `api`: FastAPI 服务，监听 `8080`
- `worker`: Celery 后台任务执行器
- `redis`: Redis 队列与结果存储

### 运行与维护

```bash
docker-compose ps
docker-compose logs -f
docker-compose logs -f api
docker-compose logs -f worker
docker-compose restart
docker-compose down
docker-compose down -v
```
