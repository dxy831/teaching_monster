# Code2Video CLI 部署说明

本项目用于将学习需求自动生成教学视频。当前最重要的交付形态是 **CLI 比赛模式**：输入一段 JSON，请求完成后输出可直接下载的 OSS 链接，适合部署到阿里云函数计算这类短生命周期环境。

这份 README 重点说明：
- CLI 怎么调用
- 比赛模式的输入输出契约
- 部署到阿里云函数计算前必须知道的依赖和环境变量
- 常见联调与排查方式

## 1. 当前推荐入口

当前推荐使用 **CLI 入口**，而不是把 API 服务当成比赛主入口。

CLI 比赛模式的特点：
- 同步执行：只有在视频真正生成完成后才返回
- 返回直链：返回的是 OSS 48 小时签名下载链接
- 不依赖本地 HTTP 文件服务持续存活
- 更适合阿里云函数计算部署模型

对应入口定义见：
- CLI 脚本入口：[pyproject.toml:144-146](pyproject.toml#L144-L146)
- 参数解析与比赛模式处理：[src/agent.py:2102-2304](src/agent.py#L2102-L2304)

## 2. CLI 比赛模式契约

### 输入 JSON

CLI 比赛模式接受以下 JSON 字段：

```json
{
  "request_id": "warmup-round-1-cellular-respiration",
  "course_requirement": "Create an AP-level Biology lesson on Cellular Respiration, specifically focusing on Glycolysis as a metabolic pathway. The lesson should explain how cells break down glucose to form ATP, NADH, and pyruvate. Include: (1) the purpose of cellular energetics, (2) step-by-step glycolysis mechanism, (3) energy yield (ATP and NADH), (4) why glycolysis is critical for cellular energy production.",
  "student_persona": "I am a high school AP Biology student preparing for exams. I learn best through concrete examples and visual demonstrations. My schedule is urgent, so I need efficient, quick-paced explanations that focus on key concepts without excessive background details."
}
```

字段说明：
- `request_id`: 请求唯一标识，用于追踪本次任务，也会参与 OSS 对象路径构造
- `course_requirement`: 学习需求原文
- `student_persona`: 学生背景描述

### 输出 JSON

成功时输出：

```json
{
  "request_id": "warmup-round-1-cellular-respiration",
  "video_url": "https://...oss...signed-url...",
  "subtitle_url": "https://...oss...signed-url...",
  "supplementary_url": []
}
```

其中：
- `video_url`: MP4 文件下载链接
- `subtitle_url`: 可选，字幕文件下载链接；若没有字幕则为 `null`
- `supplementary_url`: 当前返回空数组

实现位置：
- 比赛模式输入读取：[src/agent.py:2156-2199](src/agent.py#L2156-L2199)
- 比赛模式输出组装：[src/agent.py:2267-2304](src/agent.py#L2267-L2304)

## 3. 比赛模式保证了什么

当前 CLI 比赛模式已经补齐以下约束：

1. **生成完成后才返回**
   - 先执行完整生成链路
   - 再校验产物
   - 再上传到 OSS
   - 最后才输出 `video_url` / `subtitle_url`

2. **输出文件规格校验**
   - 视频必须为 MP4
   - 分辨率至少 1280x720
   - 音频采样率至少 16 kHz
   - 文件大小和时长也会一起校验

3. **下载链接 48 小时有效**
   - 通过 OSS 签名 URL 控制有效期
   - 默认有效期 `172800` 秒，即 48 小时

实现位置：
- 视频校验与 metadata 写入：[src/api/execution.py:542-624](src/api/execution.py#L542-L624)
- OSS 配置读取：[src/api/config.py:37-89](src/api/config.py#L37-L89)
- OSS 上传与签名：[src/api/utils/oss_utils.py](src/api/utils/oss_utils.py)
- CLI 中上传 OSS 并返回链接：[src/agent.py:2220-2289](src/agent.py#L2220-L2289)

## 4. 安装

### 4.1 Python 版本

项目要求：
- Python >= 3.11

定义位置：
- [pyproject.toml:1-18](pyproject.toml#L1-L18)

### 4.2 安装依赖

如果你使用 `uv`：

```bash
uv sync
```

如果你使用 `pip`：

```bash
pip install -e .
```

安装完成后可验证 OSS SDK 是否可用：

```bash
python -c "import oss2; print(oss2.__version__)"
```

## 5. CLI 用法

### 5.1 普通模式

普通模式用于本地按知识点生成，不是比赛交付主入口。

示例：

```bash
python src/agent.py \
  --knowledge-point "二分搜索" \
  --duration 5 \
  --api-model claude \
  --json
```

### 5.2 比赛模式：推荐用 stdin JSON

这是当前最推荐的调用方式。

```bash
cat <<'EOF' | python src/agent.py --competition --json --api-model claude
{
  "request_id": "warmup-round-1-cellular-respiration",
  "course_requirement": "Create an AP-level Biology lesson on Cellular Respiration, specifically focusing on Glycolysis as a metabolic pathway. The lesson should explain how cells break down glucose to form ATP, NADH, and pyruvate. Include: (1) the purpose of cellular energetics, (2) step-by-step glycolysis mechanism, (3) energy yield (ATP and NADH), (4) why glycolysis is critical for cellular energy production.",
  "student_persona": "I am a high school AP Biology student preparing for exams. I learn best through concrete examples and visual demonstrations. My schedule is urgent, so I need efficient, quick-paced explanations that focus on key concepts without excessive background details."
}
EOF
```

### 5.3 比赛模式：也可直接传参数

```bash
python src/agent.py \
  --competition \
  --json \
  --api-model claude \
  --request-id "warmup-round-1-cellular-respiration" \
  --course-requirement "讲解细胞呼吸的基本过程，重点解释有氧呼吸三个阶段及 ATP 的产生逻辑。" \
  --student-persona "我是高中一年级学生，学过基础生物，但对细胞内具体反应过程不熟。"
```

### 5.4 常用参数

常用参数定义见：[src/agent.py:2102-2144](src/agent.py#L2102-L2144)

比赛模式最常用参数：
- `--competition`: 启用比赛模式
- `--json`: 以 JSON 格式输出
- `--api-model`: 选择使用的模型渠道
- `--duration`: 目标视频时长（分钟）
- `--output-dir`: 指定输出目录
- `--render-quality`: 指定 Manim 渲染质量

## 6. 环境变量

### 6.1 OSS 必填环境变量

部署阿里云函数计算时，比赛模式至少需要以下环境变量：

| 变量 | 必填 | 说明 |
|------|------|------|
| `OSS_ENABLED` | 是 | 必须设为 `true` |
| `OSS_ENDPOINT` | 是 | OSS Endpoint |
| `OSS_BUCKET_NAME` | 是 | Bucket 名称 |
| `OSS_ACCESS_KEY_ID` | 是 | 阿里云 Access Key ID |
| `OSS_ACCESS_KEY_SECRET` | 是 | 阿里云 Access Key Secret |
| `OSS_KEY_PREFIX` | 否 | OSS 前缀，默认 `competition-outputs` |
| `OSS_URL_EXPIRE_SECONDS` | 否 | 签名 URL 有效期，默认 `172800` |

定义位置：
- [src/api/config.py:37-89](src/api/config.py#L37-L89)

推荐示例：

```bash
export OSS_ENABLED=true
export OSS_ENDPOINT="https://oss-cn-hangzhou.aliyuncs.com"
export OSS_BUCKET_NAME="your-bucket-name"
export OSS_ACCESS_KEY_ID="your-ak"
export OSS_ACCESS_KEY_SECRET="your-sk"
export OSS_KEY_PREFIX="competition-outputs"
export OSS_URL_EXPIRE_SECONDS=172800
```

### 6.2 其他常用环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DEFAULT_API` | 默认模型渠道 | `claude` |
| `OUTPUT_DIR` | 本地产物根目录 | `data/outputs` |
| `VIDEO_DIR` | 视频目录 | `data/outputs/videos` |
| `METADATA_DIR` | 元数据目录 | `data/outputs/metadata` |
| `MAX_WORKERS` | 最大并发 worker 数 | 自动检测 |
| `DEBUG` | 调试模式 | `false` |

## 7. OSS 存储规则

比赛模式会先在本地生成产物，再上传到 OSS。

默认对象路径规则：

```text
competition-outputs/{request_id}/{filename}
```

示例：

```text
competition-outputs/warmup-round-1-cellular-respiration/6d3f...c2.mp4
competition-outputs/warmup-round-1-cellular-respiration/6d3f...c2.srt
```

相关实现：
- 对象 key 构造：[src/api/utils/oss_utils.py:31-36](src/api/utils/oss_utils.py#L31-L36)

## 8. 阿里云函数计算部署要点

### 8.1 为什么当前方案适合函数计算

当前不是“生成完后返回本地文件名”，也不是“生成完后依赖本地 HTTP 服务继续提供下载”。

而是：
- 函数实例内完成生成
- 函数实例内完成 OSS 上传
- 返回 OSS 签名下载链接

所以即使函数实例随后释放，下载链接仍然有效。

### 8.2 部署前必须确认的系统依赖

函数计算镜像或运行环境里，需要保证以下依赖可用：
- Python 3.11+
- ffmpeg
- ffprobe
- Manim 运行所需系统库
- Cairo / Pango / OpenGL 相关依赖

如果这些底层依赖不完整，最常见后果是：
- 渲染失败
- 无法读取视频分辨率
- 无法读取音频采样率
- 合成阶段失败

### 8.3 资源配置建议

教学视频生成是重任务，不建议按普通 Web Handler 的资源规格理解。

部署时至少确认：
- 超时时间足够长
- 内存足够渲染和合成
- 临时磁盘空间足够保存中间文件和最终视频
- 并发策略不会导致多个大任务互相抢占资源

建议部署同学重点评估：
- 单次生成最长耗时
- 中间文件峰值磁盘占用
- 最终 MP4 体积
- 模型调用链路的外网访问能力

### 8.4 环境变量注入

函数计算里必须把 OSS 变量和模型相关变量一起注入。最少要保证：
- OSS 相关变量齐全
- 默认模型渠道配置正确
- 对应模型所需密钥已经注入运行环境

### 8.5 输出目录

即使最终产物会上传到 OSS，运行时仍需要可写本地目录，因为生成过程会先落本地文件。

相关配置：
- `OUTPUT_DIR`
- `VIDEO_DIR`
- `METADATA_DIR`

## 9. 建议的联调流程

### 9.1 本地联调

先在本地或 WSL 验证：

1. 依赖安装完成
2. OSS 环境变量已配置
3. 运行一条比赛模式命令
4. 拿到返回 JSON
5. 立即访问 `video_url` / `subtitle_url`
6. 确认文件可以直接下载

### 9.2 部署后联调

部署到阿里云函数计算后，至少验证一次完整真链路：

1. 发送一份真实比赛 JSON
2. 等待返回结果
3. 检查是否返回 OSS 签名链接
4. 检查 OSS 中是否已有对应对象
5. 直接下载视频
6. 确认视频能播放、字幕能打开
7. 确认视频规格符合要求

## 10. 常见问题

### 10.1 为什么比赛模式不再返回本地文件路径

因为比赛要求的是“回包后平台立刻下载”。
返回本地文件名并不等于可下载地址，也不适合函数计算实例的生命周期。

### 10.2 为什么不推荐依赖 API 公共文件服务

因为 CLI 作为比赛主入口时，不应该依赖另一个持续运行的 HTTP 文件服务来兜底下载。
函数计算场景下，更合理的是直接上传到 OSS，再返回签名链接。

### 10.3 为什么我拿到链接后下载失败

优先检查：
- OSS 配置是否正确
- Bucket 是否存在
- Access Key 权限是否足够
- Endpoint 是否和 Bucket 所在地域一致
- 生成返回后对象是否真的上传成功

### 10.4 为什么会报 OSS 配置缺失

比赛模式下，如果开启 OSS 上传但缺少必要环境变量，会直接报错而不是退回本地链接。
这是刻意设计，用来避免错误交付。

相关实现：
- [src/api/utils/oss_utils.py:13-28](src/api/utils/oss_utils.py#L13-L28)

## 11. API 入口说明

项目仍然保留 FastAPI / Celery 相关代码，适合内部平台或调试使用。
但如果你的目标是 **比赛交付** 或 **阿里云函数计算部署**，优先理解和使用本文档中的 CLI 比赛模式。

API 脚本入口仍保留在：
- [pyproject.toml:145-146](pyproject.toml#L145-L146)
