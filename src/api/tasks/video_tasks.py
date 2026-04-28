"""
视频生成 Celery 任务
"""

import sys
import os
import json
import traceback
import re
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

import redis

# 添加项目根目录到 sys.path
current_dir = Path(__file__).resolve().parent
src_dir = current_dir.parent.parent  # code2video/src
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from .celery_app import celery_app
from ..config import settings
from ..utils.file_utils import save_video_with_hash, save_related_file
from ..utils.sse import SyncTaskProgressCallback


SUBJECT_ALIASES = {
    "computer science": "computer_science",
    "cs": "computer_science",
    "computing": "computer_science",
    "programming": "computer_science",
    "informatics": "computer_science",
    "physics": "physics",
    "biology": "biology",
    "biological": "biology",
    "math": "math",
    "mathematics": "math",
    "algebra": "math",
    "geometry": "math",
    "calculus": "math",
    "general": "general",
}
VALID_SUBJECTS = {"physics", "biology", "computer_science", "math", "general"}
SUBJECT_DETERMINATION_MAX_RETRIES = 3

CS_LANGUAGE_KEYWORDS = [
    "python",
    "java",
    "javascript",
    "typescript",
    "c++",
    "cpp",
    "c#",
    "csharp",
    "go",
    "golang",
    "rust",
    "swift",
    "kotlin",
    "php",
    "ruby",
    "scala",
    "sql",
]

COMPETITION_NORMALIZATION_PROMPT = """
You normalize a contest request for an educational video generator.
Return JSON only, with no markdown fences or extra text.

Allowed subjects: physics, biology, computer_science, math, general.
If the request cannot be clearly classified as physics, biology, computer_science, or math, return general.
For computer_science, detect the programming language if explicitly requested; otherwise return Python.
For non-computer-science subjects, return language as null.
Choose a short, concrete `knowledge_point` title in English.
Choose a concise `difficulty` from: simple, medium, hard.

## ⚠️⚠️⚠️ JSON Output Format Requirements (MUST STRICTLY FOLLOW) ⚠️⚠️⚠️

**🚨 Key Rules:**
1. **Output pure JSON only**, do not add any explanatory text, markdown markers, or comments
2. **Escape quotes in strings**: If string content contains double quotes `"`, must write as `\\"`
3. **Escape newlines in strings**: Use `\\n` instead of actual newlines
4. **No comma after last array element**
5. **All strings must use double quotes**, not single quotes
6. **Ensure JSON can be correctly parsed by Python's json.loads()**
7. **Please output JSON directly, do not wrap with ```json ```**

Output schema:
{{
  "subject": "physics | biology | computer_science | math | general",
  "knowledge_point": "short English topic title",
  "language": "Python or other language name, or null",
  "difficulty": "simple | medium | hard",
  "extra_info": "one-paragraph English summary of the teaching requirements and student persona"
}}

**❌ Common Errors (will cause parsing failure):**
- Comma after last array element: `["a", "b",]` ❌
- Unescaped quotes in strings: `"say\"hello\""` ❌ should be `"say\"hello\""`
- Using single quotes: `'title'` ❌ JSON must use double quotes
- Comma after last object field: `{{"id": "1",}}` ❌
- Returning markdown fences like ```json ... ``` ❌

course_requirement:
{course_requirement}

student_persona:
{student_persona}
""".strip()


def _extract_response_text(response: Any) -> str:
    try:
        return response.candidates[0].content.parts[0].text
    except Exception:
        try:
            return response.choices[0].message.content
        except Exception:
            return str(response)


def _slug_to_title(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", (text or "").strip())
    if not cleaned:
        return "Competition Lesson"
    cleaned = re.sub(r"^[\-–—:：\s]+|[\-–—:：\s]+$", "", cleaned)
    if not cleaned:
        return "Competition Lesson"
    words = cleaned.split(" ")[:12]
    return " ".join(words)


def _infer_subject_fallback(text: str) -> Optional[str]:
    lowered = (text or "").lower()
    for alias, subject in SUBJECT_ALIASES.items():
        if alias in lowered:
            return subject
    return None


def _normalize_subject_value(subject: Optional[str]) -> Optional[str]:
    if subject is None:
        return None
    return SUBJECT_ALIASES.get(str(subject).strip().lower(), str(subject).strip().lower())


def _determine_subject_with_retry(initial_subject: Optional[str], combined_text: str) -> str:
    subject = _normalize_subject_value(initial_subject)
    if subject in VALID_SUBJECTS:
        return subject

    inferred_subject = _infer_subject_fallback(combined_text)
    if inferred_subject in VALID_SUBJECTS:
        return inferred_subject

    return "general"


def _request_competition_normalization(
    course_requirement: str,
    student_persona: str,
    api_func,
) -> Optional[Dict[str, Any]]:
    prompt = COMPETITION_NORMALIZATION_PROMPT.format(
        course_requirement=course_requirement,
        student_persona=student_persona,
    )

    for _ in range(SUBJECT_DETERMINATION_MAX_RETRIES):
        try:
            response, _ = api_func(prompt, max_tokens=1200)
            content = _extract_response_text(response)
            from src.utils import extract_json_from_markdown

            parsed = json.loads(extract_json_from_markdown(content))
            if isinstance(parsed, dict):
                subject = _normalize_subject_value(parsed.get("subject"))
                if subject in VALID_SUBJECTS:
                    parsed["subject"] = subject
                    return parsed
                if subject is None:
                    continue
                parsed["subject"] = subject
                return parsed
        except Exception:
            continue

    return None


def _infer_language_fallback(text: str) -> Optional[str]:
    lowered = (text or "").lower()
    for keyword in CS_LANGUAGE_KEYWORDS:
        if keyword in lowered:
            if keyword == "cpp":
                return "C++"
            if keyword == "csharp":
                return "C#"
            if keyword == "golang":
                return "Go"
            return keyword.upper() if keyword == "sql" else keyword.title()
    return None


def _infer_difficulty_fallback(text: str) -> str:
    lowered = (text or "").lower()
    if any(token in lowered for token in ["advanced", "hard", "challenging", "olympiad", "expert"]):
        return "hard"
    if any(token in lowered for token in ["beginner", "intro", "introduction", "easy", "basic"]):
        return "simple"
    return "medium"


def _infer_knowledge_point_fallback(course_requirement: str) -> str:
    text = (course_requirement or "").strip()
    if not text:
        return "Competition Lesson"

    quoted = re.findall(r'"([^"]+)"|\'([^\']+)\'', text)
    for pair in quoted:
        candidate = next((item for item in pair if item), "")
        if candidate:
            return _slug_to_title(candidate)

    markers = [
        "on ",
        "about ",
        "for ",
        "teach ",
        "lesson on ",
        "lesson about ",
        "video on ",
        "video about ",
    ]
    lowered = text.lower()
    for marker in markers:
        idx = lowered.find(marker)
        if idx != -1:
            tail = text[idx + len(marker):]
            candidate = re.split(r"[,.，。;；\n]", tail, maxsplit=1)[0]
            return _slug_to_title(candidate)

    candidate = re.split(r"[,.，。;；\n]", text, maxsplit=1)[0]
    return _slug_to_title(candidate)


def _normalize_competition_request(request_data: Dict[str, Any], api_func) -> Dict[str, Any]:
    course_requirement = request_data.get("course_requirement", "")
    student_persona = request_data.get("student_persona", "")
    combined_text = f"{course_requirement}\n{student_persona}".strip()

    normalized = {
        "subject": None,
        "knowledge_point": _infer_knowledge_point_fallback(course_requirement),
        "language": None,
        "difficulty": _infer_difficulty_fallback(combined_text),
        "extra_info": f"Course requirement: {course_requirement}\nStudent persona: {student_persona}".strip(),
    }

    parsed = _request_competition_normalization(course_requirement, student_persona, api_func)
    if parsed:
        normalized.update({
            "subject": parsed.get("subject") or normalized["subject"],
            "knowledge_point": parsed.get("knowledge_point") or normalized["knowledge_point"],
            "language": parsed.get("language"),
            "difficulty": parsed.get("difficulty") or normalized["difficulty"],
            "extra_info": parsed.get("extra_info") or normalized["extra_info"],
        })

    normalized["subject"] = _determine_subject_with_retry(normalized.get("subject"), combined_text)

    normalized["difficulty"] = str(normalized.get("difficulty") or "medium").strip().lower()
    if normalized["difficulty"] not in {"simple", "medium", "hard"}:
        normalized["difficulty"] = _infer_difficulty_fallback(combined_text)

    normalized["knowledge_point"] = _slug_to_title(normalized.get("knowledge_point"))

    if normalized["subject"] == "computer_science":
        normalized["language"] = normalized.get("language") or _infer_language_fallback(combined_text) or "Python"
    else:
        normalized["language"] = None

    return normalized


def _build_profile_text(
    *,
    age: Optional[Any],
    gender: Optional[str],
    language: Optional[str],
    difficulty_desc: str,
    extra_info: str,
    subject: str,
) -> str:
    profile_parts = []
    if age:
        profile_parts.append(f"我是{age}岁")
    if gender:
        profile_parts.append(f"性别{gender}")
    if subject == "computer_science" and language:
        profile_parts.append(f"选择的编程语言是{language}")
    else:
        profile_parts.append(f"学习主题属于{subject}")
    profile_parts.append(difficulty_desc)
    if extra_info:
        profile_parts.append(extra_info)
    return "，".join(profile_parts)


def _collect_subtitles(agent) -> list[dict]:
    from src.audio_steps import build_section_subtitles

    subtitles = []
    current_offset = 0.0
    ordered_sections = agent.sections or []
    for section in ordered_sections:
        section_steps = agent.section_steps.get(section.id)
        if not section_steps:
            continue
        code_path = agent.output_dir / f"{section.id}.py"
        if not code_path.exists():
            continue
        section_subtitles = build_section_subtitles(section_steps, code_path, start_offset=current_offset)
        if section_subtitles:
            subtitles.extend(section_subtitles)
            current_offset = max(current_offset, max(item["end"] for item in section_subtitles))
    return subtitles


@celery_app.task(bind=True, name="src.api.tasks.video_tasks.generate_video_task")
def generate_video_task(
    self,
    request_data: Dict[str, Any],
    channel_name: str
) -> Dict[str, Any]:
    """
    视频生成 Celery 任务
    
    Args:
        request_data: 请求数据
        channel_name: Redis 发布频道名称
        
    Returns:
        任务结果
    """
    # 创建 Redis 客户端用于发布进度
    redis_client = redis.from_url(settings.redis_url)
    callback = SyncTaskProgressCallback(redis_client, channel_name)
    
    result = {
        "success": False,
        "video_file": None,
        "subtitle_file": None,
        "error": None,
        "token_usage": None,
    }
    
    # 📍 任务总耗时跟踪（比赛规范：30 分钟内完成）
    import time
    task_start_time = time.time()
    TASK_TIMEOUT_SECONDS = 1800
    
    def check_task_timeout():
        """检查是否超过任务时限"""
        elapsed = time.time() - task_start_time
        if elapsed > TASK_TIMEOUT_SECONDS:
            raise TimeoutError(
                f"比赛任务超时：耗时 {elapsed:.0f}秒 (上限 {TASK_TIMEOUT_SECONDS}秒)"
            )
    
    try:
        # 导入必要的模块（延迟导入，避免循环依赖）
        from src.agent import TeachingVideoAgent, RunConfig
        from src.gpt_request import (
            request_claude_token,
            request_gpt4o_token,
            request_gpt5_token,
            request_gemini_token,
            request_o4mini_token,
            request_gpt41_token,
        )
        from prompts.user_profile import (
            UserProfile,
            create_profile_from_text,
            parse_profile_with_ai_sync,
        )
        from src.audio_steps import save_srt
        from src.utils import get_optimal_workers

        competition_mode = bool(request_data.get("competition_mode"))

        # 解析请求参数
        request_id = request_data.get("request_id")
        course_requirement = request_data.get("course_requirement", "")
        student_persona = request_data.get("student_persona", "")
        knowledge_point = request_data.get("knowledge_point")
        age = request_data.get("age")
        gender = request_data.get("gender")
        language = request_data.get("language")
        duration = request_data.get("duration", 5)
        difficulty = request_data.get("difficulty", "medium")
        extra_info = request_data.get("extra_info", "")
        use_feedback = request_data.get("use_feedback", True)
        use_assets = request_data.get("use_assets", True)
        api_model = request_data.get("api_model", settings.default_api)
        subject = request_data.get("subject", "computer_science")
        render_quality = request_data.get("render_quality")

        # 获取 API 函数（键名与 api_config.json 一致）
        api_mapping = {
            "claude": request_claude_token,
            "gpt4o": request_gpt4o_token,
            "gpt5": request_gpt5_token,
            "gpt-41": request_gpt41_token,
            "gpt-o4mini": request_o4mini_token,
            "gemini": request_gemini_token,
        }
        api_func = api_mapping.get(api_model, request_claude_token)

        if competition_mode:
            normalized_request = _normalize_competition_request(request_data, api_func)
            knowledge_point = normalized_request["knowledge_point"]
            subject = normalized_request["subject"]
            language = normalized_request["language"]
            difficulty = normalized_request["difficulty"]
            extra_info = normalized_request["extra_info"]
            duration = request_data.get("duration", 5)
            render_quality = render_quality or "-qh"
        else:
            language = language or "Python"
            render_quality = render_quality or "-ql"
        
        # ========== 阶段 1: 解析用户画像 ==========
        task_id = callback.on_stage_start("parse_profile", "正在解析用户画像。")
        
        try:            
            check_task_timeout()  # 模宗            
            # difficulty is stored in metadata as simple/medium/hard
            # internal profile difficulty uses beginner/intermediate/advanced
            difficulty_level_map = {
                "simple": "beginner",
                "medium": "intermediate",
                "hard": "advanced",
            }
            forced_difficulty_level = difficulty
            profile_difficulty_level = difficulty_level_map.get(difficulty, "intermediate")

            # 难度映射为自然语言描述
            difficulty_desc_map = {
                "simple": "Content difficulty is beginner-friendly and introductory",
                "medium": "Content difficulty is intermediate",
                "hard": "Content difficulty is advanced",
            }
            difficulty_desc = difficulty_desc_map.get(difficulty, "Content difficulty is intermediate")
            
            # 构建用户画像文本
            profile_text = _build_profile_text(
                age=age,
                gender=gender,
                language=language,
                difficulty_desc=difficulty_desc,
                extra_info=extra_info,
                subject=subject,
            )

            user_profile = create_profile_from_text(profile_text, subject=subject)
            # 使用 AI 解析用户画像
            parsed_profile = parse_profile_with_ai_sync(profile_text, api_func, subject=subject)
            if parsed_profile:
                # 强制覆盖难度偏好，确保严格与请求 difficulty 一致
                parsed_profile.setdefault("user_summary", {})
                parsed_profile["user_summary"]["difficulty_preference"] = profile_difficulty_level
                parsed_profile["user_summary"]["target_language"] = language or "Not applicable"
                user_profile.update_with_parsed_profile(parsed_profile)
            
            callback.on_stage_finish(task_id, "用户画像解析成功。")
        except Exception as e:
            callback.on_stage_failed(task_id, f"用户画像解析失败: {str(e)}")
            raise
        
        # ========== 阶段 2: 创建 Agent 并生成视频 ==========
        # 配置
        cfg = RunConfig(
            api=api_func,
            use_feedback=use_feedback,
            use_assets=use_assets,
            duration=duration,
            user_profile=user_profile,
            forced_difficulty_level=forced_difficulty_level,
            subject=subject,
            render_quality=render_quality,
            max_code_token_length=50000,  # 提高 token 上限，避免分镜脚本被截断
            max_fix_bug_tries=10,
            max_regenerate_tries=10,
            max_feedback_gen_code_tries=5,
            max_mllm_fix_bugs_tries=5,
            feedback_rounds=2,
        )
        
        # 创建输出目录
        folder_path = src_dir / "CASES" / f"API_{api_model}"
        folder_path.mkdir(parents=True, exist_ok=True)
        
        # 创建 Agent
        agent = TeachingVideoAgent(
            idx=0,
            knowledge_point=knowledge_point,
            folder=str(folder_path),
            cfg=cfg,
        )
        
        # ========== 阶段 3: 生成大纲 ==========
        task_id = callback.on_stage_start("generate_outline", "正在生成教学大纲。")
        try:            
            check_task_timeout()  # 模宗            
            agent.generate_outline()

            # 强制覆盖大纲中的 difficulty_level，确保与请求参数完全一致
            outline_file = Path(agent.output_dir) / "outline.json"
            if outline_file.exists():
                with open(outline_file, "r", encoding="utf-8") as f:
                    outline_data = json.load(f)
                outline_data["difficulty_level"] = forced_difficulty_level
                with open(outline_file, "w", encoding="utf-8") as f:
                    json.dump(outline_data, f, ensure_ascii=False, indent=2)

            callback.on_stage_finish(task_id, "教学大纲生成成功。")
        except Exception as e:
            callback.on_stage_failed(task_id, f"教学大纲生成失败: {str(e)}")
            raise
        
        # ========== 阶段 4: 生成分镜 ==========
        task_id = callback.on_stage_start("generate_storyboard", "正在生成分镜脚本。")
        try:            
            check_task_timeout()  # 模宗            
            agent.generate_storyboard()
            callback.on_stage_finish(task_id, "分镜脚本生成成功。")
        except Exception as e:
            callback.on_stage_failed(task_id, f"分镜脚本生成失败: {str(e)}")
            raise
        
        # ========== 阶段 5: 注入封面 + 概述 ==========
        task_id = callback.on_stage_start("inject_cover_overview", "正在注入封面与课程导览。")
        try:            
            check_task_timeout()  # 模宗            
            agent.inject_overview_section()
            agent.inject_cover_section()
            callback.on_stage_finish(task_id, "封面与课程导览注入成功。")
        except Exception as e:
            callback.on_stage_failed(task_id, f"封面与课程导览注入失败: {str(e)}")
            raise
        
        # ========== 阶段 6: 生成代码 ==========
        task_id = callback.on_stage_start("generate_codes", "正在生成 Manim 代码。")
        try:            
            check_task_timeout()  # 模宗            
            agent.generate_codes()
            callback.on_stage_finish(task_id, "Manim 代码生成成功。")
        except Exception as e:
            callback.on_stage_failed(task_id, f"Manim 代码生成失败: {str(e)}")
            raise
        
        # ========== 阶段 7: 渲染视频 ==========
        task_id = callback.on_stage_start("render_videos", "正在渲染视频片段。")
        try:            
            check_task_timeout()  # 模宗            
            agent.render_all_sections()
            callback.on_stage_finish(task_id, "视频片段渲染成功。")
        except Exception as e:
            callback.on_stage_failed(task_id, f"视频片段渲染失败: {str(e)}")
            raise
        
        # ========== 阶段 8: 合并视频 ==========
        task_id = callback.on_stage_start("merge_videos", "正在合并视频。")
        try:            
            check_task_timeout()  # 模宗            
            final_video_path = agent.merge_videos()
            if not final_video_path:
                raise Exception("视频合并失败，未生成最终视频")
            callback.on_stage_finish(task_id, "视频合并成功。")
        except Exception as e:
            callback.on_stage_failed(task_id, f"视频合并失败: {str(e)}")
            raise
        
        # ========== 阶段 9: 保存视频 ==========
        task_id = callback.on_stage_start("save_video", "正在保存视频文件。")
        try:
            # 📍 新增：检查任务超时 + 校验输出规格
            check_task_timeout()
            
            from ..utils.file_utils import validate_video_output
            
            validation_result = validate_video_output(
                str(final_video_path),
                max_duration=1800,      # 30 分钟
                min_width=1280,
                min_height=720,
                max_size_gb=3.0
            )
            
            if not validation_result["valid"]:
                error_messages = "\n".join(validation_result["errors"])
                raise ValueError(
                    f"生成的视频不符合比赛规范:\n{error_messages}"
                )
            
            # 📍 保存规格信息到元数据
            video_specs = {
                "duration_seconds": validation_result["duration_seconds"],
                "resolution": validation_result["resolution"],
                "file_size_bytes": validation_result["file_size_bytes"],
                "file_size_gb": validation_result["file_size_gb"],
                "validated_at": datetime.now().isoformat(),
            }
            
            subtitles = _collect_subtitles(agent)
            subtitle_filename = None
            subtitle_file_hash = None

            # 准备元信息
            metadata = {
                "knowledge_point": knowledge_point,
                "subject": subject,
                "language": language,
                "duration": duration,
                "difficulty": difficulty,
                "age": age,
                "gender": gender,
                "extra_info": extra_info,
                "api_model": api_model,
                "outline": agent.outline.__dict__ if agent.outline else None,
                "token_usage": agent.token_usage,
                "created_at": datetime.now().isoformat(),
                "video_specs": video_specs,  # 📍 新增：规格信息
            }
            if competition_mode:
                metadata.update({
                    "request_id": request_id,
                    "course_requirement": course_requirement,
                    "student_persona": student_persona,
                })

            # 保存视频并获取哈希文件名
            video_filename = save_video_with_hash(final_video_path, metadata)
            subtitle_file_hash = Path(video_filename).stem

            if subtitles:
                subtitle_path = Path(final_video_path).with_suffix(".srt")
                save_srt(subtitles, subtitle_path)
                subtitle_filename = save_related_file(subtitle_file_hash, subtitle_path, extension=".srt")
                metadata["subtitle_file"] = subtitle_filename
                metadata["subtitle_count"] = len(subtitles)
                metadata["subtitle_created_at"] = datetime.now().isoformat()
                result["subtitle_file"] = subtitle_filename

                metadata_path = Path(settings.metadata_dir) / f"{subtitle_file_hash}.json"
                with open(metadata_path, "w", encoding="utf-8") as f:
                    json.dump(metadata, f, ensure_ascii=False, indent=2)

            callback.on_stage_finish(task_id, "视频文件保存成功。")

            result["success"] = True
            result["video_file"] = video_filename
            result["token_usage"] = agent.token_usage

        except Exception as e:
            callback.on_stage_failed(task_id, f"视频文件保存失败: {str(e)}")
            raise

        # ========== 发送最终结果 ==========
        callback.on_result("视频生成成功。", {
            "video_file": video_filename,
            "subtitle_file": result.get("subtitle_file"),
            "token_usage": agent.token_usage,
        })
        
    except Exception as e:
        error_msg = f"视频生成失败: {str(e)}"
        result["error"] = error_msg
        result["traceback"] = traceback.format_exc()
        
        # 发送失败结果
        callback.on_result(error_msg, {"error": str(e)})
    
    finally:
        redis_client.close()
    
    return result
