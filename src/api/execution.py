import json
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from .config import Settings, settings
from .utils.file_utils import save_related_file, save_video_with_hash, validate_video_output
from prompts.user_profile import create_profile_from_text, parse_profile_with_ai_sync
from src.audio_steps import save_srt
from src.gpt_request import (
    request_claude_token,
    request_gemini_token,
    request_gpt41_token,
    request_gpt4o_token,
    request_gpt5_token,
    request_o4mini_token,
)

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

course_requirement:
{course_requirement}

student_persona:
{student_persona}
""".strip()


@dataclass
class ExecutionHooks:
    on_stage_start: Optional[Callable[[str, str], Any]] = None
    on_stage_finish: Optional[Callable[[Any, str], None]] = None
    on_stage_failed: Optional[Callable[[Any, str], None]] = None
    on_result: Optional[Callable[[str, Dict[str, Any]], None]] = None


@dataclass
class ExecutionContext:
    request_data: Dict[str, Any]
    settings_obj: Settings = field(default_factory=lambda: settings)
    src_dir: Optional[Path] = None
    output_root: Optional[Path] = None
    hooks: Optional[ExecutionHooks] = None


API_MAPPING = {
    "claude": request_claude_token,
    "gpt4o": request_gpt4o_token,
    "gpt-4o": request_gpt4o_token,
    "gpt5": request_gpt5_token,
    "gpt-5": request_gpt5_token,
    "gpt-41": request_gpt41_token,
    "gpt-o4mini": request_o4mini_token,
    "gemini": request_gemini_token,
    "Gemini": request_gemini_token,
}


def _extract_response_text(response: Any) -> str:
    try:
        return response.candidates[0].content.parts[0].text
    except Exception:
        try:
            return response.choices[0].message.content
        except Exception:
            return str(response)


def _slug_to_title(text: str) -> str:
    import re

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


def _request_competition_normalization(course_requirement: str, student_persona: str, api_func):
    from src.utils import extract_json_from_markdown

    prompt = COMPETITION_NORMALIZATION_PROMPT.format(
        course_requirement=course_requirement,
        student_persona=student_persona,
    )

    for _ in range(SUBJECT_DETERMINATION_MAX_RETRIES):
        try:
            response, _ = api_func(prompt, max_tokens=1200)
            content = _extract_response_text(response)
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
    import re

    text = (course_requirement or "").strip()
    if not text:
        return "Competition Lesson"

    quoted = re.findall(r'"([^"]+)"|\'([^\']+)\'', text)
    for pair in quoted:
        candidate = next((item for item in pair if item), "")
        if candidate:
            return _slug_to_title(candidate)

    markers = ["on ", "about ", "for ", "teach ", "lesson on ", "lesson about ", "video on ", "video about "]
    lowered = text.lower()
    for marker in markers:
        idx = lowered.find(marker)
        if idx != -1:
            tail = text[idx + len(marker) :]
            candidate = re.split(r"[,.，。；\n]", tail, maxsplit=1)[0]
            return _slug_to_title(candidate)

    candidate = re.split(r"[,.，。；\n]", text, maxsplit=1)[0]
    return _slug_to_title(candidate)


def normalize_competition_request(request_data: Dict[str, Any], api_func) -> Dict[str, Any]:
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
        normalized.update(
            {
                "subject": parsed.get("subject") or normalized["subject"],
                "knowledge_point": parsed.get("knowledge_point") or normalized["knowledge_point"],
                "language": parsed.get("language"),
                "difficulty": parsed.get("difficulty") or normalized["difficulty"],
                "extra_info": parsed.get("extra_info") or normalized["extra_info"],
            }
        )

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


def build_profile_text(*, age: Optional[Any], gender: Optional[str], language: Optional[str], difficulty_desc: str, extra_info: str, subject: str) -> str:
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


def collect_subtitles(agent, merged_section_ids: Optional[set[str]] = None) -> list[dict]:
    from src.audio_steps import build_section_subtitles

    subtitles = []
    current_offset = 0.0
    for section in agent.sections or []:
        if merged_section_ids is not None and section.id not in merged_section_ids:
            continue
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


def _call_stage_start(hooks: Optional[ExecutionHooks], stage: str, message: str):
    if hooks and hooks.on_stage_start:
        return hooks.on_stage_start(stage, message)
    return stage


def _call_stage_finish(hooks: Optional[ExecutionHooks], token: Any, message: str):
    if hooks and hooks.on_stage_finish:
        hooks.on_stage_finish(token, message)


def _call_stage_failed(hooks: Optional[ExecutionHooks], token: Any, message: str):
    if hooks and hooks.on_stage_failed:
        hooks.on_stage_failed(token, message)


def _call_result(hooks: Optional[ExecutionHooks], message: str, data: Dict[str, Any]):
    if hooks and hooks.on_result:
        hooks.on_result(message, data)


def resolve_api_func(api_model: Optional[str]):
    return API_MAPPING.get(api_model or settings.default_api, request_claude_token)


def execute_video_generation(context: ExecutionContext) -> Dict[str, Any]:
    import time

    from src.agent import RunConfig, TeachingVideoAgent

    request_data = dict(context.request_data)
    settings_obj = context.settings_obj
    src_root = context.src_dir or Path(__file__).resolve().parents[1]
    output_root = context.output_root or (src_root / "CASES")
    hooks = context.hooks

    result = {
        "success": False,
        "video_file": None,
        "subtitle_file": None,
        "error": None,
        "token_usage": None,
        "traceback": None,
        "metadata": None,
    }

    task_start_time = time.time()
    task_timeout_seconds = 1800

    def check_task_timeout():
        elapsed = time.time() - task_start_time
        if elapsed > task_timeout_seconds:
            raise TimeoutError(f"比赛任务超时：耗时 {elapsed:.0f}秒 (上限 {task_timeout_seconds}秒)")

    try:
        competition_mode = bool(request_data.get("competition_mode"))
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
        api_model = request_data.get("api_model", settings_obj.default_api)
        subject = request_data.get("subject", "computer_science")
        render_quality = request_data.get("render_quality")

        api_func = resolve_api_func(api_model)

        if competition_mode:
            normalized_request = normalize_competition_request(request_data, api_func)
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

        token = _call_stage_start(hooks, "parse_profile", "正在解析用户画像。")
        try:
            check_task_timeout()
            difficulty_level_map = {"simple": "beginner", "medium": "intermediate", "hard": "advanced"}
            forced_difficulty_level = difficulty
            profile_difficulty_level = difficulty_level_map.get(difficulty, "intermediate")
            difficulty_desc_map = {
                "simple": "Content difficulty is beginner-friendly and introductory",
                "medium": "Content difficulty is intermediate",
                "hard": "Content difficulty is advanced",
            }
            difficulty_desc = difficulty_desc_map.get(difficulty, "Content difficulty is intermediate")
            profile_text = build_profile_text(
                age=age,
                gender=gender,
                language=language,
                difficulty_desc=difficulty_desc,
                extra_info=extra_info,
                subject=subject,
            )
            user_profile = create_profile_from_text(profile_text, subject=subject)
            parsed_profile = parse_profile_with_ai_sync(profile_text, api_func, subject=subject)
            if parsed_profile:
                parsed_profile.setdefault("user_summary", {})
                parsed_profile["user_summary"]["difficulty_preference"] = profile_difficulty_level
                parsed_profile["user_summary"]["target_language"] = language or "Not applicable"
                user_profile.update_with_parsed_profile(parsed_profile)
            _call_stage_finish(hooks, token, "用户画像解析成功。")
        except Exception as exc:
            _call_stage_failed(hooks, token, f"用户画像解析失败: {str(exc)}")
            raise

        cfg = RunConfig(
            api=api_func,
            use_feedback=use_feedback,
            use_assets=use_assets,
            duration=duration,
            max_video_seconds=660,
            pipeline_budget_seconds=1800,
            render_timeout_seconds=600,
            user_profile=user_profile,
            forced_difficulty_level=forced_difficulty_level,
            subject=subject,
            render_quality=render_quality,
            max_code_token_length=50000,
            max_fix_bug_tries=3,
            max_regenerate_tries=3,
            max_feedback_gen_code_tries=2,
            max_mllm_fix_bugs_tries=2,
            feedback_rounds=2,
        )

        folder_path = Path(request_data.get("output_dir") or (output_root / f"API_{api_model}"))
        folder_path.mkdir(parents=True, exist_ok=True)
        agent = TeachingVideoAgent(idx=0, knowledge_point=knowledge_point, folder=str(folder_path), cfg=cfg)

        token = _call_stage_start(hooks, "generate_outline", "正在生成教学大纲。")
        try:
            check_task_timeout()
            agent.generate_outline()
            outline_file = Path(agent.output_dir) / "outline.json"
            if outline_file.exists():
                with open(outline_file, "r", encoding="utf-8") as f:
                    outline_data = json.load(f)
                outline_data["difficulty_level"] = forced_difficulty_level
                with open(outline_file, "w", encoding="utf-8") as f:
                    json.dump(outline_data, f, ensure_ascii=False, indent=2)
            _call_stage_finish(hooks, token, "教学大纲生成成功。")
        except Exception as exc:
            _call_stage_failed(hooks, token, f"教学大纲生成失败: {str(exc)}")
            raise

        token = _call_stage_start(hooks, "generate_storyboard", "正在生成分镜脚本。")
        try:
            check_task_timeout()
            agent.generate_storyboard()
            _call_stage_finish(hooks, token, "分镜脚本生成成功。")
        except Exception as exc:
            _call_stage_failed(hooks, token, f"分镜脚本生成失败: {str(exc)}")
            raise

        token = _call_stage_start(hooks, "inject_overview", "正在注入概述。")
        try:
            check_task_timeout()
            agent.inject_overview_section()
            _call_stage_finish(hooks, token, "概述注入成功。")
        except Exception as exc:
            _call_stage_failed(hooks, token, f"概述注入失败: {str(exc)}")
            raise

        token = _call_stage_start(hooks, "generate_codes", "正在生成 Manim 代码。")
        try:
            check_task_timeout()
            agent.generate_codes()
            agent._trim_sections_by_actual_tts_duration()
            _call_stage_finish(hooks, token, "Manim 代码生成成功。")
        except Exception as exc:
            _call_stage_failed(hooks, token, f"Manim 代码生成失败: {str(exc)}")
            raise

        token = _call_stage_start(hooks, "render_videos", "正在渲染视频片段。")
        pivot_deadline = task_start_time + 1785
        fallback_mode = False
        merged_section_ids: set[str] = set()
        try:
            check_task_timeout()
            elapsed_before_render = time.time() - task_start_time
            remaining_budget = max(120.0, float(cfg.pipeline_budget_seconds) - elapsed_before_render)
            section_timeout = max(60, min(cfg.render_timeout_seconds, int(remaining_budget * 0.8)))
            agent.render_all_sections(section_timeout=section_timeout, deadline=pivot_deadline)
            fallback_mode = time.time() >= pivot_deadline
            if fallback_mode:
                scanned_section_videos = agent._discover_fallback_section_videos()
                agent.section_videos = dict(scanned_section_videos)
                _call_stage_finish(hooks, token, "已到 29 分 45 秒保底截止，停止等待剩余片段并进入合并。")
            else:
                scanned_section_videos = agent._discover_completed_section_videos()
                if scanned_section_videos:
                    agent.section_videos.update(scanned_section_videos)
                _call_stage_finish(hooks, token, "视频片段渲染成功。")
        except Exception as exc:
            _call_stage_failed(hooks, token, f"视频片段渲染失败: {str(exc)}")
            raise

        token = _call_stage_start(hooks, "merge_videos", "正在合并视频。")
        try:
            if not agent.section_videos:
                raise Exception("视频合并失败，未生成任何可用片段")
            merged_section_ids = set(agent.section_videos.keys())
            final_video_path = agent.merge_videos()
            if not final_video_path:
                raise Exception("视频合并失败，未生成最终视频")
            _call_stage_finish(hooks, token, "视频合并成功。")
        except Exception as exc:
            _call_stage_failed(hooks, token, f"视频合并失败: {str(exc)}")
            raise

        token = _call_stage_start(hooks, "save_video", "正在保存视频文件。")
        try:
            validation_result = validate_video_output(
                str(final_video_path),
                max_duration=1800,
                min_width=1280,
                min_height=720,
                max_size_gb=3.0,
            )
            if not validation_result["valid"]:
                error_messages = "\n".join(validation_result["errors"])
                raise ValueError(f"生成的视频不符合比赛规范:\n{error_messages}")

            video_specs = {
                "duration_seconds": validation_result["duration_seconds"],
                "resolution": validation_result["resolution"],
                "audio_sample_rate": validation_result["audio_sample_rate"],
                "file_size_bytes": validation_result["file_size_bytes"],
                "file_size_gb": validation_result["file_size_gb"],
                "validated_at": datetime.now().isoformat(),
            }
            public_link_expires_at = (datetime.now() + timedelta(hours=48)).isoformat()
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
                "public_link_expires_at": public_link_expires_at,
                "video_specs": video_specs,
                "merged_section_ids": sorted(merged_section_ids),
            }
            if competition_mode:
                metadata.update(
                    {
                        "request_id": request_id,
                        "course_requirement": course_requirement,
                        "student_persona": student_persona,
                    }
                )

            video_filename = save_video_with_hash(final_video_path, metadata)
            result["success"] = True
            result["video_file"] = video_filename
            result["token_usage"] = agent.token_usage
            result["metadata"] = metadata

            _call_stage_finish(hooks, token, "视频文件保存成功。")
            _call_result(
                hooks,
                "视频生成成功。",
                {"video_file": video_filename, "subtitle_file": result.get("subtitle_file"), "token_usage": agent.token_usage},
            )

            subtitle_filename = None
            subtitle_file_hash = Path(video_filename).stem
            subtitles = collect_subtitles(agent, merged_section_ids)
            if subtitles and not fallback_mode:
                subtitle_path = Path(final_video_path).with_suffix(".srt")
                save_srt(subtitles, subtitle_path)
                subtitle_filename = save_related_file(subtitle_file_hash, subtitle_path, extension=".srt")
                metadata["subtitle_file"] = subtitle_filename
                metadata["subtitle_count"] = len(subtitles)
                metadata["subtitle_created_at"] = datetime.now().isoformat()
                result["subtitle_file"] = subtitle_filename
        except Exception as exc:
            _call_stage_failed(hooks, token, f"视频文件保存失败: {str(exc)}")
            raise

    except Exception as exc:
        error_msg = f"视频生成失败: {str(exc)}"
        result["error"] = error_msg
        result["traceback"] = traceback.format_exc()
        _call_result(hooks, error_msg, {"error": str(exc)})

    return result
