# Teaching Monster

Teaching Monster 是一个将学习需求同步生成教学视频的后端服务。当前主交付形态是 **Docker 部署的 HTTP JSON API**：请求到达后立即开始生成，只有在视频和相关文件已经落盘、可以下载时才返回结果。

当前能力重点：
- 同步 HTTP 视频生成
- 比赛制式 JSON 接口
- 本地公开下载直链，默认 48 小时有效
- Docker 镜像部署

## 1. 当前推荐运行方式

当前推荐直接运行 API 服务，而不是把 CLI 当成主入口。

主入口文件：
- API 应用入口：[src/api/main.py](src/api/main.py)
- 比赛接口路由：[src/api/routes/video.py](src/api/routes/video.py)
- 文件下载路由：[src/api/routes/files.py](src/api/routes/files.py)
- Docker 镜像定义：[Dockerfile](Dockerfile)
- Compose 编排：[docker-compose.yml](docker-compose.yml)

服务特性：
- **同步执行**：请求生命周期内完成生成
- **JSON 通信**：输入输出均为标准 JSON
- **生成完成后返回**：返回时 `video_url` / `subtitle_url` 已可下载
- **公开下载**：通过 `/api/v1/public/files/{filename}` 暴露下载链接

## 2. API 概览

默认地址：

```text
http://127.0.0.1:8080
```

文档地址：
- Swagger UI: `http://127.0.0.1:8080/docs`
- ReDoc: `http://127.0.0.1:8080/redoc`

除健康检查与公开下载外，接口默认要求请求头携带 API Key：

```text
X-API-Key: your-api-key
```

默认开发 key：

```text
dev-api-key-12345
```

来源见 [src/api/config.py:35-42](src/api/config.py#L35-L42)。

## 3. 快速开始

### 3.1 使用 Docker Compose

在项目根目录执行：

```bash
docker compose up --build
```

后台运行：

```bash
docker compose up -d --build
```

停止服务：

```bash
docker compose down
```

查看日志：

```bash
docker compose logs -f
```

### 3.2 直接构建镜像

```bash
docker build -t fenggwsx/teaching-monster:1.0 .
```

运行镜像：

```bash
docker run --rm -p 8080:8080 \
  -e API_KEYS=dev-api-key-12345 \
  -e DEFAULT_API=claude \
  fenggwsx/teaching-monster:1.0
```

## 4. 镜像发布

如果本地镜像已经打好 tag：

```bash
docker login
docker push fenggwsx/teaching-monster:1.0
```

如果还没有 tag：

```bash
docker build -t fenggwsx/teaching-monster:1.0 .
docker push fenggwsx/teaching-monster:1.0
```

## 5. 健康检查

请求：

```bash
curl http://127.0.0.1:8080/health
```

响应示例字段见 [src/api/schemas/request.py:114-120](src/api/schemas/request.py#L114-L120)，包含：
- `status`
- `generation_mode`
- `workers`
- `version`

## 6. 比赛接口

比赛接口路径：

```text
POST /api/v1/competition/generate
```

请求模型定义见 [src/api/schemas/request.py:61-75](src/api/schemas/request.py#L61-L75)。

### 6.1 请求 JSON

```json
{
  "request_id": "warmup-round-1-cellular-respiration",
  "course_requirement": "Create an AP-level Biology lesson on Cellular Respiration, specifically focusing on Glycolysis as a metabolic pathway. The lesson should explain how cells break down glucose to form ATP, NADH, and pyruvate. Include: (1) the purpose of cellular energetics, (2) step-by-step glycolysis mechanism, (3) energy yield (ATP and NADH), (4) why glycolysis is critical for cellular energy production.",
  "student_persona": "I am a high school AP Biology student preparing for exams. I learn best through concrete examples and visual demonstrations. My schedule is urgent, so I need efficient, quick-paced explanations that focus on key concepts without excessive background details."
}
```

### 6.2 PowerShell 调用示例

```powershell
@'
{
  "request_id": "warmup-round-1-cellular-respiration",
  "course_requirement": "Create an AP-level Biology lesson on Cellular Respiration, specifically focusing on Glycolysis as a metabolic pathway. The lesson should explain how cells break down glucose to form ATP, NADH, and pyruvate. Include: (1) the purpose of cellular energetics, (2) step-by-step glycolysis mechanism, (3) energy yield (ATP and NADH), (4) why glycolysis is critical for cellular energy production.",
  "student_persona": "I am a high school AP Biology student preparing for exams. I learn best through concrete examples and visual demonstrations. My schedule is urgent, so I need efficient, quick-paced explanations that focus on key concepts without excessive background details."
}
'@ > body_competition.json

curl.exe -v -X POST "http://127.0.0.1:8080/api/v1/competition/generate" `
  -H "Content-Type: application/json" `
  -H "X-API-Key: dev-api-key-12345" `
  --data-binary "@body_competition.json"
```

### 6.3 成功响应

响应模型定义见 [src/api/schemas/request.py:78-84](src/api/schemas/request.py#L78-L84)。

```json
{
  "request_id": "warmup-round-1-cellular-respiration",
  "video_url": "http://127.0.0.1:8080/api/v1/public/files/xxxx.mp4",
  "subtitle_url": "http://127.0.0.1:8080/api/v1/public/files/xxxx.srt",
  "supplementary_url": []
}
```

语义保证：
- 请求到达后立即开始生成
- 服务端会一直阻塞到生成完成
- 只有当文件已存在且可下载时才返回响应

对应实现见 [src/api/routes/video.py:123-150](src/api/routes/video.py#L123-L150)。

## 7. 普通生成接口

普通接口路径：

```text
POST /api/v1/generate-video
```

请求模型定义见 [src/api/schemas/request.py:17-59](src/api/schemas/request.py#L17-L59)。

示例：

```bash
curl -X POST "http://127.0.0.1:8080/api/v1/generate-video" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-api-key-12345" \
  -d '{
    "knowledge_point": "binary search",
    "age": 17,
    "gender": "male",
    "language": "Python",
    "duration": 5,
    "difficulty": "medium"
  }'
```

## 8. 下载接口

### 8.1 公开下载

比赛接口返回的文件 URL 来自：

```text
GET /api/v1/public/files/{filename}
HEAD /api/v1/public/files/{filename}
```

实现见 [src/api/routes/files.py:90-117](src/api/routes/files.py#L90-L117) 和 [src/api/routes/files.py:232-260](src/api/routes/files.py#L232-L260)。

行为：
- 检查文件是否存在
- 检查元信息里是否包含有效期
- 超过有效期返回 `410 Gone`
- 支持 `HEAD`
- 支持 Range 请求断点续传

### 8.2 受保护下载

```text
GET /api/v1/files/{filename}
GET /api/v1/files/{filename}/metadata
```

这些接口需要 `X-API-Key`。

## 9. 环境变量

主要环境变量定义见 [src/api/config.py](src/api/config.py)。

### 9.1 API 运行相关

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `API_KEYS` | `dev-api-key-12345` | 逗号分隔的 API Key 列表 |
| `API_HOST` | `0.0.0.0` | 监听地址 |
| `API_PORT` | `8080` | 监听端口 |
| `DEFAULT_API` | `claude` | 默认模型通道 |
| `DEBUG` | `false` | 是否开启调试模式 |
| `MAX_WORKERS` | 空 | 本地生成并发配置 |

### 9.2 产物目录

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `OUTPUT_DIR` | `data/outputs` | 输出根目录 |
| `VIDEO_DIR` | `data/outputs/videos` | 视频与字幕目录 |
| `METADATA_DIR` | `data/outputs/metadata` | 元信息目录 |

### 9.3 OSS 相关

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `OSS_ENABLED` | `false` | 是否启用 OSS |
| `OSS_ENDPOINT` | 空 | OSS Endpoint |
| `OSS_BUCKET_NAME` | 空 | Bucket 名称 |
| `OSS_ACCESS_KEY_ID` | 空 | Access Key ID |
| `OSS_ACCESS_KEY_SECRET` | 空 | Access Key Secret |
| `OSS_KEY_PREFIX` | `competition-outputs` | 对象前缀 |
| `OSS_URL_EXPIRE_SECONDS` | `172800` | 签名 URL 有效期 |

## 10. 输出与约束

当前同步 API 会在返回前检查：
- 视频文件存在
- 字幕文件若存在，也必须可下载
- 字幕与辅助材料总大小不超过 100MB
- 辅助材料数量不超过 5 个

对应逻辑见 [src/api/routes/video.py:56-76](src/api/routes/video.py#L56-L76)。

视频生成执行链中还会做媒体规格校验与元信息写入，核心实现在 [src/api/execution.py](src/api/execution.py)。

## 11. 本地目录说明

运行时会使用这些目录：

```text
data/outputs/
├─ videos/
└─ metadata/
```

Docker 镜像构建时也会预先创建这些目录，见 [Dockerfile:62-71](Dockerfile#L62-L71)。

## 12. 常见问题

### 12.1 为什么接口返回很慢？

因为现在是同步生成模式。请求不会先入队，而是在当前 HTTP 请求里直接完成视频生成，所以耗时会接近真实生成耗时。

### 12.2 为什么收到响应后才能下载？

这是当前接口契约的一部分：只有文件真实存在且可下载时，服务端才返回 `video_url` / `subtitle_url`。

### 12.3 为什么公开链接会失效？

公开下载链接依赖元信息中的过期时间。默认有效期是 48 小时，过期后访问会返回 `410 Gone`。

### 12.4 现在还依赖 Redis、Celery、SSE 吗？

不依赖。当前服务已经收敛为单 HTTP 服务、同步执行、JSON 返回。
