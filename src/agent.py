import sys
import os
import imageio_ffmpeg

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 安全地设置编码（兼容 Celery Worker 环境）
try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass  # 在 Celery Worker 中可能会失败，忽略即可

# Ensure ffmpeg is in PATH for Manim and other subprocesses
FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()
FFMPEG_DIR = os.path.dirname(FFMPEG_PATH)
if FFMPEG_DIR not in os.environ["PATH"]:
    os.environ["PATH"] = FFMPEG_DIR + os.pathsep + os.environ["PATH"]

import re
import ast
import argparse
import json
import time
import random
import subprocess
import shutil
from typing import List, Dict, Any, Optional, Tuple, Callable
from dataclasses import dataclass
from pathlib import Path
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, ThreadPoolExecutor, as_completed, wait
from src.gpt_request import *
from prompts import *
from src.utils import *
from src.scope_refine import *
from src.external_assets import process_storyboard_with_assets
from src.audio_steps import (
    build_section_steps,
    save_section_steps,
    build_section_narration_track,
    remux_video_with_audio,
)
from src.overview_scene import (
    build_overview_lecture_lines,
    generate_overview_manim_code,
    _merge_section_titles_with_ai,
)
from src.cover_scene import generate_cover_manim_code

LECTURE_LINE_MAX_CHARS = 43
LECTURE_LINE_SPLIT_MAX_RETRIES = 2
LECTURE_LINE_SPLIT_PROMPT = """
You rewrite educational lecture lines for on-screen display.
Return JSON only, with no markdown fences or extra text.

Task:
- Split each input lecture line into one or more shorter on-screen lines.
- Preserve the original meaning and original order.
- Keep the wording natural and readable for an educational video.
- Each output line must contain at most {max_chars} characters, counting letters, punctuation, digits, and spaces.
- If an input line already has {max_chars} characters or fewer, keep it unchanged.
- Split by semantic meaning, not by arbitrary fixed chunks.
- Do not merge two different input lines together.
- Do not drop information.
- Do not paraphrase unless a tiny wording adjustment is needed to make the split natural.

Output schema:
{{
  "lines": [
    {{"source_index": 0, "parts": ["short line one", "short line two"]}},
    {{"source_index": 1, "parts": ["another short line"]}}
  ]
}}

Input lecture lines:
{lecture_lines_json}
""".strip()

# Cover title heuristics
COVER_TITLE_WORD_THRESHOLD = 6
COVER_TITLE_FONT_SIZE = 48
COVER_TITLE_MAX_WIDTH = 15.0
COVER_SUBTITLE_MAX_WORDS = 15
COVER_SHORT_TITLE_MAX_WORDS = 4


@dataclass
class Section:
    id: str
    title: str
    lecture_lines: List[str]
    animations: List[str]
    estimated_duration: Optional[int] = None  # 预计时长（秒）
    highlight_groups: Optional[List[List[int]]] = None
    evidence_lines_indices: Optional[List[int]] = None
    intro_transition_spoken: Optional[str] = None
    outro_transition_spoken: Optional[str] = None
    new_terms_introduced: Optional[List[str]] = None


@dataclass
class TeachingOutline:
    topic: str
    target_audience: str
    sections: List[Dict[str, Any]]
    factuality_anchor_checklist: Optional[List[str]] = None
    scaffold_map: Optional[List[Dict[str, Any]]] = None
    difficulty_level: Optional[str] = None


@dataclass
class VideoFeedback:
    section_id: str
    video_path: str
    has_issues: bool
    suggested_improvements: List[str]
    raw_response: Optional[str] = None
    is_good_enough: bool = False
    good_enough_reason: Optional[str] = None
    evaluation_scores: Optional[Dict[str, float]] = None


@dataclass
class RunConfig:
    use_feedback: bool = True
    use_assets: bool = True
    api: Callable = None
    feedback_rounds: int = 2
    iconfinder_api_key: str = ""
    max_code_token_length: int = 30000
    max_fix_bug_tries: int = 3
    max_regenerate_tries: int = 3
    max_feedback_gen_code_tries: int = 2
    max_mllm_fix_bugs_tries: int = 2
    duration: int = 5
    max_video_seconds: int = 660
    pipeline_budget_seconds: int = 1800
    render_timeout_seconds: int = 600
    # 用户个性化配置
    user_profile: Optional[UserProfile] = None
    # 强制大纲难度（simple/medium/hard），若为空则由画像推断
    forced_difficulty_level: Optional[str] = None
    subject: str = "computer_science"
    render_quality: str = "-ql"


class TeachingVideoAgent:
    def __init__(
        self,
        idx,
        knowledge_point,
        folder="CASES",
        cfg: Optional[RunConfig] = None,
        outline_data: Optional[Dict[str, Any]] = None,
    ):
        """1. Global parameter"""
        self.learning_topic = knowledge_point
        self.idx = idx
        self.cfg = cfg or RunConfig()
        self.folder = folder  # 修复：保存 folder 路径，供 get_serializable_state 使用

        if not self.cfg.api:
            raise ValueError(f"❌ 错误: TeachingVideoAgent 初始化失败。必须在 RunConfig 中提供有效的 'api' 回调函数。")

        self.use_feedback = cfg.use_feedback
        self.use_assets = cfg.use_assets
        self.API = cfg.api
        self.feedback_rounds = cfg.feedback_rounds
        self.iconfinder_api_key = cfg.iconfinder_api_key
        self.max_code_token_length = cfg.max_code_token_length
        self.max_fix_bug_tries = cfg.max_fix_bug_tries
        self.max_regenerate_tries = cfg.max_regenerate_tries
        self.max_feedback_gen_code_tries = cfg.max_feedback_gen_code_tries
        self.max_mllm_fix_bugs_tries = cfg.max_mllm_fix_bugs_tries
        self.forced_difficulty_level = cfg.forced_difficulty_level
        self.duration = cfg.duration
        self.max_video_seconds = cfg.max_video_seconds
        self.pipeline_budget_seconds = cfg.pipeline_budget_seconds
        self.render_timeout_seconds = cfg.render_timeout_seconds
        self.subject = cfg.subject or "computer_science"
        self.render_quality = cfg.render_quality or "-ql"
        self.use_assets = cfg.use_assets
        self.API = cfg.api
        self.feedback_rounds = cfg.feedback_rounds
        self.iconfinder_api_key = cfg.iconfinder_api_key
        self.max_code_token_length = cfg.max_code_token_length
        self.max_fix_bug_tries = cfg.max_fix_bug_tries
        self.max_regenerate_tries = cfg.max_regenerate_tries
        self.max_feedback_gen_code_tries = cfg.max_feedback_gen_code_tries
        self.max_mllm_fix_bugs_tries = cfg.max_mllm_fix_bugs_tries
        
        # 用户个性化配置
        self.user_profile = cfg.user_profile or get_default_profile(self.subject)

        """2. Path for output"""
        self.output_dir = get_output_dir(idx=idx, knowledge_point=self.learning_topic, base_dir=folder)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.assets_dir = Path(*self.output_dir.parts[: self.output_dir.parts.index("CASES")]) / "assets" / "icon"
        self.assets_dir.mkdir(exist_ok=True)

        """3. ScopeRefine & Anchor Visual"""
        self.scope_refine_fixer = ScopeRefineFixer(self.API, self.max_code_token_length)
        self.extractor = GridPositionExtractor()

        """4. External Database"""
        knowledge_ref_mapping_path = (
            Path(*self.output_dir.parts[: self.output_dir.parts.index("CASES")]) / "json_files" / "long_video_ref_mapping.json"
        )
        with open(knowledge_ref_mapping_path) as f:
            self.KNOWLEDGE2PATH = json.load(f)
        self.knowledge_ref_img_folder = (
            Path(*self.output_dir.parts[: self.output_dir.parts.index("CASES")]) / "assets" / "reference"
        )
        self.GRID_IMG_PATH = self.knowledge_ref_img_folder / "GRID.png"

        """5. Data structure"""
        self.outline = None
        if outline_data is not None:
            self.outline = TeachingOutline(
                topic=outline_data["topic"],
                target_audience=outline_data["target_audience"],
                sections=outline_data["sections"],
                factuality_anchor_checklist=outline_data.get("factuality_anchor_checklist"),
                scaffold_map=outline_data.get("scaffold_map"),
                difficulty_level=outline_data.get("difficulty_level"),
            )
        self.enhanced_storyboard = None
        self.sections = []
        self.section_codes = {}
        self.section_steps = {}
        self.section_videos = {}
        self.video_feedbacks = {}
        self.section_feedback_stop_flags = {}
        self.section_feedback_stop_reasons = {}

        """6. For Efficiency"""
        self.token_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    def _request_api_and_track_tokens(self, prompt, max_tokens=20000):
        """packages API requests and automatically accumulates token usage"""
        response, usage = self.API(prompt, max_tokens=max_tokens)
        if usage:
            self.token_usage["prompt_tokens"] += usage.get("prompt_tokens", 0)
            self.token_usage["completion_tokens"] += usage.get("completion_tokens", 0)
            self.token_usage["total_tokens"] += usage.get("total_tokens", 0)
        return response

    def _extract_response_text(self, response) -> str:
        if isinstance(response, str):
            return response
        try:
            return extract_answer_from_response(response)
        except Exception:
            return str(response)

    def _normalize_cover_text(self, text: str) -> str:
        normalized = (text or "").strip()
        if len(normalized) >= 2 and ((normalized[0] == '"' and normalized[-1] == '"') or (normalized[0] == "'" and normalized[-1] == "'")):
            normalized = normalized[1:-1].strip()
        return normalized

    def _titles_are_duplicate(self, title1: str, title2: str) -> bool:
        return title1.strip().lower() == title2.strip().lower()

    def _does_text_fit_in_cover(self, text: str) -> bool:
        if not text:
            return False
        try:
            from manim import Text

            rendered = Text(text, font="Noto Sans", font_size=COVER_TITLE_FONT_SIZE)
            return rendered.width <= COVER_TITLE_MAX_WIDTH
        except Exception as e:
            # Fallback to a conservative heuristic when Manim font metrics are unavailable
            return len(text) <= 40

    def _generate_cover_subtitle(self, title: str) -> str:
        prompt = f"""
You are a concise, user-centered educational video cover copywriter.
Learner profile:
{self.user_profile.get_stage2_prompt()}

Main title: {title}

Produce a single subtitle phrase in the same language as the title.
Requirements:
- No more than {COVER_SUBTITLE_MAX_WORDS} words.
- Keep it descriptive and aligned to the learner profile.
- Do not include quotes or extra explanation.
"""
        response = self._request_api_and_track_tokens(prompt, max_tokens=80)
        subtitle = self._extract_response_text(response)
        return self._normalize_cover_text(subtitle)

    def _generate_short_cover_title(self, topic: str) -> str:
        prompt = f"""
You are a concise educational cover headline writer.
Learner profile:
{self.user_profile.get_stage2_prompt()}

Original topic title: {topic}

Generate a short main cover title of {COVER_SHORT_TITLE_MAX_WORDS} words or fewer that preserves the core concept.
Do not include quotes or extra explanation.
"""
        response = self._request_api_and_track_tokens(prompt, max_tokens=60)
        short_title = self._normalize_cover_text(self._extract_response_text(response))
        if not short_title:
            return topic
        if len(short_title.split()) > COVER_SHORT_TITLE_MAX_WORDS:
            short_title = " ".join(short_title.split()[:COVER_SHORT_TITLE_MAX_WORDS])
        return short_title

    def _resolve_cover_title_pair(self) -> tuple[str, str]:
        self._ensure_outline()
        main_title = self.learning_topic
        subtitle = self.outline.topic
        if self._titles_are_duplicate(main_title, subtitle):
            if len(main_title.split()) <= COVER_TITLE_WORD_THRESHOLD and self._does_text_fit_in_cover(main_title):
                generated_subtitle = self._generate_cover_subtitle(main_title)
                if not generated_subtitle or self._titles_are_duplicate(generated_subtitle, main_title):
                    generated_subtitle = f"Learn about {main_title}"
                return main_title, generated_subtitle
            short_title = self._generate_short_cover_title(main_title)
            return short_title, subtitle
        return main_title, subtitle

    def _request_video_api_and_track_tokens(self, prompt, video_path):
        """Wraps video API requests and accumulates token usage automatically"""
        response, usage = request_gemini_video_img_token(prompt=prompt, video_path=video_path, image_path=self.GRID_IMG_PATH)

        if usage:
            self.token_usage["prompt_tokens"] += usage.get("prompt_tokens", 0)
            self.token_usage["completion_tokens"] += usage.get("completion_tokens", 0)
            self.token_usage["total_tokens"] += usage.get("total_tokens", 0)
        return response

    def _video_has_audio_stream(self, video_path: Path) -> bool:
        video_path = Path(video_path)
        ffprobe_path = shutil.which("ffprobe")
        if not ffprobe_path or not video_path.exists():
            return False

        result = subprocess.run(
            [
                ffprobe_path,
                "-v",
                "error",
                "-select_streams",
                "a",
                "-show_entries",
                "stream=index",
                "-of",
                "json",
                str(video_path),
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return False

        try:
            payload = json.loads(result.stdout or "{}")
        except json.JSONDecodeError:
            return False

        return bool(payload.get("streams"))

    def _remux_section_audio(self, section_id: str, video_path: Path) -> Path:
        steps_file = self.output_dir / f"{section_id}_steps.json"
        code_file = self.output_dir / f"{section_id}.py"
        if not steps_file.exists() or not code_file.exists():
            raise FileNotFoundError(f"Missing steps/code file for remux: {section_id}")

        if section_id in self.section_steps:
            section_steps = self.section_steps[section_id]
            is_valid, validation_error = self._validate_cached_section_steps(section_steps)
            if not is_valid:
                raise ValueError(f"Invalid in-memory cached steps for remux {section_id}: {validation_error}")
        else:
            with open(steps_file, "r", encoding="utf-8") as f:
                section_steps = json.load(f)
            is_valid, validation_error = self._validate_cached_section_steps(section_steps)
            if not is_valid:
                raise ValueError(f"Invalid or missing cached steps for remux {section_id}: {validation_error}")
            self.section_steps[section_id] = section_steps

        remux_dir = self.output_dir / "audio_remux"
        remux_dir.mkdir(exist_ok=True)
        narration_path = remux_dir / f"{section_id}_track.wav"
        fixed_video_path = remux_dir / f"{section_id}_with_audio.mp4"

        build_section_narration_track(section_steps, code_file, narration_path)
        remux_video_with_audio(video_path, narration_path, fixed_video_path)
        return fixed_video_path

    def get_serializable_state(self):
        """返回可以序列化保存的Agent状态"""
        state = {"idx": self.idx, "knowledge_point": self.learning_topic, "folder": self.folder, "cfg": self.cfg}
        if self.outline is not None:
            state["outline_data"] = {
                "topic": self.outline.topic,
                "target_audience": self.outline.target_audience,
                "sections": self.outline.sections,
            }
        return state

    def _ensure_outline(self) -> None:
        if self.outline is not None:
            return

        outline_file = self.output_dir / "outline.json"
        if not outline_file.exists():
            raise RuntimeError(f"Outline is missing and outline.json not found: {outline_file}")

        with open(outline_file, "r", encoding="utf-8") as f:
            outline_data = json.load(f)

        self.outline = TeachingOutline(
            topic=outline_data["topic"],
            target_audience=outline_data["target_audience"],
            sections=outline_data["sections"],
        )

    @staticmethod
    def _validate_cached_section_steps(section_steps: List[dict], expected_steps: Optional[int] = None) -> Tuple[bool, str]:
        if expected_steps is not None and len(section_steps) != expected_steps:
            return False, f"cached steps count mismatch: got {len(section_steps)}, expected {expected_steps}"

        for idx, step in enumerate(section_steps):
            if not isinstance(step, dict):
                return False, f"step {idx} is not a dict"

            highlight_indices = step.get("highlight_indices")
            if not isinstance(highlight_indices, list) or not highlight_indices:
                return False, f"step {idx} has invalid highlight_indices: {highlight_indices!r}"
            if any(not isinstance(line_idx, int) for line_idx in highlight_indices):
                return False, f"step {idx} highlight_indices must contain only ints"

            audio_path = step.get("audio_path")
            if not isinstance(audio_path, str) or not audio_path.strip():
                return False, f"step {idx} has invalid audio_path: {audio_path!r}"
            if not Path(audio_path).exists():
                return False, f"step {idx} audio file not found: {audio_path}"

            audio_duration = step.get("audio_duration")
            if not isinstance(audio_duration, (int, float)):
                return False, f"step {idx} has invalid audio_duration type: {audio_duration!r}"
            if audio_duration != audio_duration or audio_duration <= 0:
                return False, f"step {idx} has invalid audio_duration value: {audio_duration!r}"

        return True, ""

    def _load_validated_cached_steps(self, section: Section, steps_file: Path) -> Optional[List[dict]]:
        if not steps_file.exists():
            return None

        with open(steps_file, "r", encoding="utf-8") as f:
            section_steps = json.load(f)

        expected_steps = 2 if section.id == "section_overview" else len(
            section.highlight_groups or self._build_default_highlight_groups(section.lecture_lines)
        )
        is_valid, validation_error = self._validate_cached_section_steps(section_steps, expected_steps)
        if not is_valid:
            print(f"⚠️ {section.id} 缓存 steps 无效，忽略缓存并重建: {validation_error}")
            return None

        self.section_steps[section.id] = section_steps
        return section_steps

    def _actual_tts_duration_for_section(self, section: Section) -> float:
        section_steps = self.section_steps.get(section.id) or []
        total_duration = 0.0
        for step in section_steps:
            if not isinstance(step, dict):
                continue
            audio_duration = step.get("audio_duration")
            if isinstance(audio_duration, (int, float)) and audio_duration == audio_duration and audio_duration > 0:
                total_duration += float(audio_duration)
        if total_duration > 0:
            return total_duration
        return float(self._estimate_section_seconds(section))

    def _validate_synced_step_coverage(self, code: str, expected_steps: int) -> Tuple[bool, str]:
        try:
            tree = ast.parse(code)
        except SyntaxError as exc:
            return False, f"SyntaxError during AST validation: {exc}"

        construct_func = None
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name != "TeachingScene":
                for child in node.body:
                    if isinstance(child, ast.FunctionDef) and child.name == "construct":
                        construct_func = child
                        break
            if construct_func:
                break

        if construct_func is None:
            return False, "No construct() method found in generated scene code"

        synced_calls = 0
        raw_add_sound_calls = 0
        for node in ast.walk(construct_func):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr == "play_synced_step":
                    synced_calls += 1
                elif node.func.attr == "add_sound":
                    raw_add_sound_calls += 1

        if raw_add_sound_calls > 0:
            return False, "construct() contains raw add_sound() calls instead of play_synced_step()"
        if synced_calls < expected_steps:
            return False, f"construct() only calls play_synced_step() {synced_calls} times, expected {expected_steps}"

        return True, ""

    @staticmethod
    def _build_default_highlight_groups(lecture_lines: List[str]) -> List[List[int]]:
        return [[index] for index in range(len(lecture_lines))]

    @classmethod
    def _normalize_highlight_groups(cls, lecture_lines: List[str], highlight_groups) -> List[List[int]]:
        if not lecture_lines:
            return []

        if not highlight_groups:
            return cls._build_default_highlight_groups(lecture_lines)

        if not isinstance(highlight_groups, list):
            raise ValueError("highlight_groups must be a list of index lists")

        normalized_groups: List[List[int]] = []
        seen_indices = set()
        expected_indices = set(range(len(lecture_lines)))

        for group in highlight_groups:
            if not isinstance(group, list) or not group:
                raise ValueError("Each highlight group must be a non-empty list of indices")

            normalized_group: List[int] = []
            for raw_index in group:
                if not isinstance(raw_index, int):
                    raise ValueError("Highlight group indices must be integers")
                if not (0 <= raw_index < len(lecture_lines)):
                    raise ValueError(f"Highlight group index out of range: {raw_index}")
                if raw_index in seen_indices:
                    raise ValueError(f"Highlight group index repeated: {raw_index}")
                seen_indices.add(raw_index)
                normalized_group.append(raw_index)

            normalized_groups.append(normalized_group)

        if seen_indices != expected_indices:
            missing = sorted(expected_indices - seen_indices)
            extra = sorted(seen_indices - expected_indices)
            raise ValueError(
                f"highlight_groups must cover every lecture line exactly once; missing={missing}, extra={extra}"
            )

        return normalized_groups

    @staticmethod
    def _count_lecture_line_chars(text: str) -> int:
        return len((text or "").strip())

    @classmethod
    def _validate_split_lecture_parts(cls, original_lines: List[str], split_payload: Any) -> Optional[List[List[str]]]:
        if not isinstance(split_payload, dict):
            return None
        items = split_payload.get("lines")
        if not isinstance(items, list) or len(items) != len(original_lines):
            return None

        normalized_parts_by_source: List[Optional[List[str]]] = [None] * len(original_lines)
        for expected_index, item in enumerate(items):
            if not isinstance(item, dict):
                return None
            source_index = item.get("source_index")
            parts = item.get("parts")
            if source_index != expected_index:
                return None
            if not isinstance(parts, list) or not parts:
                return None

            normalized_parts: List[str] = []
            for part in parts:
                if not isinstance(part, str):
                    return None
                normalized = " ".join(part.strip().split())
                if not normalized:
                    return None
                if cls._count_lecture_line_chars(normalized) > LECTURE_LINE_MAX_CHARS:
                    return None
                normalized_parts.append(normalized)

            normalized_parts_by_source[source_index] = normalized_parts

        if any(parts is None for parts in normalized_parts_by_source):
            return None

        return normalized_parts_by_source

    @classmethod
    def _fallback_split_lecture_lines(cls, lecture_lines: List[str]) -> Tuple[List[str], List[List[int]]]:
        def split_line(line: str) -> List[str]:
            normalized_line = " ".join(line.strip().split())
            if not normalized_line:
                return []

            parts: List[str] = []
            remaining = normalized_line
            while remaining:
                if cls._count_lecture_line_chars(remaining) <= LECTURE_LINE_MAX_CHARS:
                    parts.append(remaining)
                    break

                split_at = remaining.rfind(" ", 0, LECTURE_LINE_MAX_CHARS + 1)
                if split_at <= 0:
                    parts.append(remaining[:LECTURE_LINE_MAX_CHARS].strip())
                    remaining = remaining[LECTURE_LINE_MAX_CHARS:].strip()
                    continue

                parts.append(remaining[:split_at].strip())
                remaining = remaining[split_at + 1 :].strip()

            return [part for part in parts if part]

        rewritten_lines: List[str] = []
        source_to_new_indices: List[List[int]] = []
        for line in lecture_lines:
            parts = split_line(line)
            if not parts:
                continue
            new_indices: List[int] = []
            for part in parts:
                new_indices.append(len(rewritten_lines))
                rewritten_lines.append(part)
            source_to_new_indices.append(new_indices)
        return rewritten_lines, source_to_new_indices

    def _split_lecture_lines_with_ai(self, lecture_lines: List[str]) -> Tuple[List[str], List[List[int]]]:
        normalized_source_lines = [" ".join(str(line).strip().split()) for line in lecture_lines if str(line).strip()]
        if not normalized_source_lines:
            return [], []

        default_mapping = [[index] for index in range(len(normalized_source_lines))]
        if all(self._count_lecture_line_chars(line) <= LECTURE_LINE_MAX_CHARS for line in normalized_source_lines):
            return normalized_source_lines, default_mapping

        prompt = LECTURE_LINE_SPLIT_PROMPT.format(
            max_chars=LECTURE_LINE_MAX_CHARS,
            lecture_lines_json=json.dumps(normalized_source_lines, ensure_ascii=False, indent=2),
        )

        split_groups: Optional[List[List[str]]] = None
        for _ in range(LECTURE_LINE_SPLIT_MAX_RETRIES):
            response = self._request_api_and_track_tokens(prompt, max_tokens=800)
            raw_text = self._extract_response_text(response)
            try:
                split_payload = json.loads(extract_json_from_markdown(raw_text))
            except Exception:
                continue
            split_groups = self._validate_split_lecture_parts(normalized_source_lines, split_payload)
            if split_groups is not None:
                break

        if split_groups is None:
            return self._fallback_split_lecture_lines(normalized_source_lines)

        rewritten_lines: List[str] = []
        source_to_new_indices: List[List[int]] = []
        for parts in split_groups:
            new_indices: List[int] = []
            for part in parts:
                new_indices.append(len(rewritten_lines))
                rewritten_lines.append(part)
            source_to_new_indices.append(new_indices)

        return rewritten_lines, source_to_new_indices

    @classmethod
    def _remap_highlight_groups(
        cls,
        original_highlight_groups: List[List[int]],
        source_to_new_indices: List[List[int]],
    ) -> List[List[int]]:
        remapped_groups: List[List[int]] = []
        for group in original_highlight_groups:
            remapped_group: List[int] = []
            for source_index in group:
                remapped_group.extend(source_to_new_indices[source_index])
            remapped_groups.append(remapped_group)
        return remapped_groups

    def _prepare_section_lecture_lines(
        self,
        lecture_lines: List[str],
        highlight_groups,
    ) -> Tuple[List[str], List[List[int]]]:
        normalized_original_lines = [" ".join(str(line).strip().split()) for line in lecture_lines if str(line).strip()]
        normalized_groups = self._normalize_highlight_groups(normalized_original_lines, highlight_groups)
        rewritten_lines, source_to_new_indices = self._split_lecture_lines_with_ai(normalized_original_lines)
        remapped_groups = self._remap_highlight_groups(normalized_groups, source_to_new_indices)
        return rewritten_lines, remapped_groups

    def _get_user_difficulty_preference(self) -> str:
        summary = {}
        if self.user_profile and getattr(self.user_profile, "parsed_profile", None):
            summary = self.user_profile.parsed_profile.get("user_summary", {}) or {}
        return str(summary.get("difficulty_preference", "intermediate")).strip().lower()

    def _select_duration_with_ai(self) -> int:
        difficulty = self._get_user_difficulty_preference() or "intermediate"
        prompt = f"""
You are planning a learning video length.

Knowledge point: {self.learning_topic}
Learner difficulty preference: {difficulty}

Choose the best total duration in minutes.
Use these rules when deciding:
- Simpler content should usually be shorter.
- If the student's foundation is weaker, the video should usually be longer.
- Consider both topic simplicity and learner foundation together, not separately.

Example:
- Simple topic + strong foundation -> choose a shorter duration, such as 2 or 3 minutes.
- More complex topic + weaker foundation -> choose a longer duration, such as 5 or 6 minutes.

Constraints:
- Must be an integer
- Must be between 3 and 6 inclusive

Return only one integer number.
"""
        response = self._request_api_and_track_tokens(prompt, max_tokens=20)
        raw_text = self._extract_response_text(response)
        match = re.search(r"\d+", raw_text)
        if not match:
            return 4
        value = int(match.group(0))
        if value < 3 or value > 6:
            return 4
        return value

    def _ensure_ai_duration_selected(self) -> None:
        if getattr(self, "_ai_duration_selected", False):
            return
        try:
            selected = self._select_duration_with_ai()
        except Exception:
            selected = 4
        if selected < 3 or selected > 6:
            selected = 4
        self.duration = selected
        self._ai_duration_selected = True
        print(f"⏱️ AI 选择视频时长: {self.duration} 分钟")

    def _estimate_section_seconds(self, section: Section) -> int:
        if isinstance(section.estimated_duration, (int, float)) and section.estimated_duration > 0:
            return int(section.estimated_duration)
        return 30

    @staticmethod
    def _coerce_non_empty_str(value: Any) -> str:
        if isinstance(value, str):
            normalized = value.strip()
            if normalized:
                return normalized
        raise ValueError("Expected a non-empty string")

    @staticmethod
    def _coerce_string_list(value: Any, field_name: str, allow_empty: bool = True) -> List[str]:
        if not isinstance(value, list):
            raise ValueError(f"{field_name} must be a list")
        normalized = [str(item).strip() for item in value if str(item).strip()]
        if not allow_empty and not normalized:
            raise ValueError(f"{field_name} must not be empty")
        return normalized

    @staticmethod
    def _extract_outline_json(text: str) -> str:
        return extract_json_from_markdown(text)

    def _build_outline_retry_prompt(self, base_prompt: str, raw_content: str, violations: List[str]) -> str:
        violations_json = json.dumps(violations, ensure_ascii=False, indent=2)
        return (
            f"{base_prompt}\n\n"
            "The previous outline output was rejected by runtime validation.\n"
            "Fix the violations below and regenerate the FULL JSON outline.\n"
            "Do not explain anything. Return JSON only.\n\n"
            f"Validation violations:\n{violations_json}\n\n"
            f"Previous output:\n{raw_content}"
        )

    @staticmethod
    def _clip_fallback_text(value: str, limit: int = 160) -> str:
        normalized = " ".join(str(value or "").split())
        if len(normalized) <= limit:
            return normalized
        return normalized[: limit - 3].rstrip() + "..."

    def _fallback_outline_string(self, field_name: str, section: Dict[str, Any], index: int, sections: List[Dict[str, Any]]) -> str:
        title = self._clip_fallback_text(section.get("title") or f"Section {index + 1}", 80)
        content = self._clip_fallback_text(section.get("content") or title, 160)
        next_title = ""
        if index + 1 < len(sections) and isinstance(sections[index + 1], dict):
            next_title = self._clip_fallback_text(sections[index + 1].get("title") or "the next section", 80)

        fallbacks = {
            "id": f"section_{index}",
            "title": f"Section {index + 1}",
            "content": title,
            "learning_objective": f"Understand the key idea in {title}.",
            "prior_knowledge_activation": f"Recall the basic idea related to {title} before learning this part.",
            "new_concept": title,
            "misconception_check": f"Do not confuse {title} with a different but similar idea.",
            "bridge_to_next": (
                f"This section prepares the learner for {next_title}." if next_title else "This section prepares the learner for the next idea."
            ),
        }
        if field_name == "content" and content:
            return content
        return fallbacks[field_name]

    def _fallback_evidence_basis(self, section: Dict[str, Any], index: int) -> List[Dict[str, str]]:
        claim_source = section.get("content") or section.get("title") or f"section {index + 1}"
        claim = self._clip_fallback_text(claim_source, 160) or f"Key point from section {index + 1}"
        anchor = self._clip_fallback_text(section.get("new_concept") or section.get("title") or "the lesson concept", 120)
        return [
            {
                "claim": claim,
                "source_type": "textbook_rule",
                "anchor": f"Use textbook-standard explanation for {anchor}.",
            }
        ]

    def _apply_outline_fallbacks(
        self,
        outline_data: Dict[str, Any],
        violations: List[str],
    ) -> Tuple[Dict[str, Any], List[str]]:
        degraded = json.loads(json.dumps(outline_data or {}, ensure_ascii=False))
        fallback_notes: List[str] = []

        if not isinstance(degraded, dict):
            degraded = {}
            fallback_notes.append("outline root replaced with empty object before fallback")

        for field_name in ["topic", "target_audience"]:
            try:
                degraded[field_name] = self._coerce_non_empty_str(degraded.get(field_name))
            except ValueError:
                if field_name == "topic":
                    degraded[field_name] = self.learning_topic
                else:
                    degraded[field_name] = f"Learners studying {self.learning_topic}"
                fallback_notes.append(f"filled top-level field '{field_name}'")

        scaffold_map = degraded.get("scaffold_map")
        if not isinstance(scaffold_map, list) or not scaffold_map:
            degraded["scaffold_map"] = [
                {
                    "section_id": "section_0_intro",
                    "prior_knowledge": f"Learners already know something related to {self.learning_topic}.",
                    "target_concept": f"Build understanding of {self.learning_topic}.",
                    "bridge_strategy": "Move from familiar intuition to the new idea step by step.",
                }
            ]
            fallback_notes.append("replaced empty scaffold_map with default scaffold")

        sections = degraded.get("sections")
        if not isinstance(sections, list):
            sections = []
            degraded["sections"] = sections
        if not sections:
            sections.append(
                {
                    "id": "section_0_intro",
                    "title": self.learning_topic,
                    "content": f"Introduce {self.learning_topic}.",
                    "estimated_duration": max(1, int((self.duration * 60) / 1.4)),
                }
            )
            fallback_notes.append("created fallback section because sections was empty")

        required_string_fields = [
            "id",
            "title",
            "content",
            "learning_objective",
            "prior_knowledge_activation",
            "new_concept",
            "misconception_check",
            "bridge_to_next",
        ]

        for index, raw_section in enumerate(sections):
            if not isinstance(raw_section, dict):
                raw_section = {}
                sections[index] = raw_section
                fallback_notes.append(f"replaced sections[{index}] with empty object before fallback")

            for field_name in required_string_fields:
                try:
                    raw_section[field_name] = self._coerce_non_empty_str(raw_section.get(field_name))
                except ValueError:
                    raw_section[field_name] = self._fallback_outline_string(field_name, raw_section, index, sections)
                    fallback_notes.append(f"filled sections[{index}].{field_name}")

            evidence_basis = raw_section.get("evidence_basis")
            normalized_evidence: List[Dict[str, str]] = []
            if isinstance(evidence_basis, list):
                for evidence_item in evidence_basis:
                    if not isinstance(evidence_item, dict):
                        continue
                    claim = str(evidence_item.get("claim") or "").strip()
                    source_type = str(evidence_item.get("source_type") or "").strip()
                    anchor = str(evidence_item.get("anchor") or "").strip()
                    if claim and source_type and anchor:
                        normalized_evidence.append(
                            {"claim": claim, "source_type": source_type, "anchor": anchor}
                        )
            if not normalized_evidence:
                normalized_evidence = self._fallback_evidence_basis(raw_section, index)
                fallback_notes.append(f"filled sections[{index}].evidence_basis")
            raw_section["evidence_basis"] = normalized_evidence

            estimated_duration = raw_section.get("estimated_duration")
            if not isinstance(estimated_duration, int) or estimated_duration <= 0:
                raw_section["estimated_duration"] = max(20, int((self.duration * 60) / max(1, len(sections) * 2)))
                fallback_notes.append(f"filled sections[{index}].estimated_duration")

        normalized_outline, remaining_violations = self._validate_outline_data(degraded)
        if remaining_violations:
            raise ValueError(
                "Outline fallback could not recover invalid data: " + "; ".join(remaining_violations)
            )

        if fallback_notes:
            print("⚠️ 大纲结构二次失败，已降级补齐字段继续执行: " + "; ".join(fallback_notes))
        elif violations:
            print("⚠️ 大纲结构二次失败，但规范化后已可继续执行")
        return normalized_outline, fallback_notes

    def _build_storyboard_fallback_line(self, section: Dict[str, Any], index: int) -> str:
        title = self._clip_fallback_text(section.get("title") or f"Section {index + 1}", 80)
        return f"We now focus on {title}."

    def _apply_storyboard_fallbacks(
        self,
        storyboard_data: Dict[str, Any],
        violations: List[str],
    ) -> Tuple[Dict[str, Any], List[str]]:
        degraded = json.loads(json.dumps(storyboard_data or {}, ensure_ascii=False))
        fallback_notes: List[str] = []

        sections = degraded.get("sections")
        if not isinstance(sections, list):
            sections = []
            degraded["sections"] = sections
        if not sections:
            sections.append(
                {
                    "id": "section_0_intro",
                    "title": self.learning_topic,
                    "lecture_lines": [f"This lesson introduces {self.learning_topic}."],
                    "animations": ["Visual: Display the lesson title and a simple supporting diagram."],
                    "estimated_duration": 30,
                }
            )
            fallback_notes.append("created fallback storyboard section because sections was empty")

        for index, raw_section in enumerate(sections):
            if not isinstance(raw_section, dict):
                raw_section = {}
                sections[index] = raw_section
                fallback_notes.append(f"replaced storyboard sections[{index}] with empty object before fallback")

            raw_section["id"] = str(raw_section.get("id") or f"section_{index}").strip() or f"section_{index}"
            title = str(raw_section.get("title") or "").strip()
            if not title:
                title = f"Section {index + 1}"
                raw_section["title"] = title
                fallback_notes.append(f"filled storyboard sections[{index}].title")
            else:
                raw_section["title"] = title

            lecture_lines = raw_section.get("lecture_lines")
            if not isinstance(lecture_lines, list):
                lecture_lines = []
            lecture_lines = [str(line).strip() for line in lecture_lines if str(line).strip()]
            if not lecture_lines:
                lecture_lines = [self._build_storyboard_fallback_line(raw_section, index)]
                fallback_notes.append(f"filled storyboard sections[{index}].lecture_lines")
            raw_section["lecture_lines"] = lecture_lines

            animations = raw_section.get("animations")
            if not isinstance(animations, list):
                animations = []
            animations = [str(item).strip() for item in animations if str(item).strip()]
            if not animations:
                animations = [f"Visual: Highlight the key idea in {title} with clear labels."]
                fallback_notes.append(f"filled storyboard sections[{index}].animations")
            raw_section["animations"] = animations

            estimated_duration = raw_section.get("estimated_duration")
            if not isinstance(estimated_duration, int) or estimated_duration <= 0:
                raw_section["estimated_duration"] = max(15, len(lecture_lines) * 6)
                fallback_notes.append(f"filled storyboard sections[{index}].estimated_duration")

            raw_section["highlight_groups"] = self._build_default_highlight_groups(lecture_lines)
            raw_section["evidence_lines_indices"] = [min(1, len(lecture_lines) - 1)]
            raw_section["intro_transition_spoken"] = None
            raw_section["outro_transition_spoken"] = None

            new_terms = raw_section.get("new_terms_introduced")
            if not isinstance(new_terms, list):
                new_terms = []
            raw_section["new_terms_introduced"] = [str(item).strip() for item in new_terms if str(item).strip()][: self._max_new_terms_per_section()]

        normalized_storyboard, remaining_violations, _ = self._validate_storyboard_data(degraded)
        if remaining_violations:
            raise ValueError(
                "Storyboard fallback could not recover invalid data: " + "; ".join(remaining_violations)
            )

        if fallback_notes:
            print("⚠️ 分镜结构二次失败，已降级补齐字段继续执行: " + "; ".join(fallback_notes))
        elif violations:
            print("⚠️ 分镜结构二次失败，但规范化后已可继续执行")
        return normalized_storyboard, fallback_notes

    def _validate_outline_data(self, outline_data: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
        violations: List[str] = []
        normalized: Dict[str, Any] = {}

        try:
            normalized["topic"] = self._coerce_non_empty_str(outline_data.get("topic"))
        except ValueError:
            violations.append("top-level field 'topic' must be a non-empty string")

        try:
            normalized["target_audience"] = self._coerce_non_empty_str(outline_data.get("target_audience"))
        except ValueError:
            violations.append("top-level field 'target_audience' must be a non-empty string")

        try:
            normalized["factuality_anchor_checklist"] = self._coerce_string_list(
                outline_data.get("factuality_anchor_checklist"),
                "factuality_anchor_checklist",
                allow_empty=True,
            )
        except ValueError as exc:
            violations.append(str(exc))

        scaffold_map = outline_data.get("scaffold_map")
        if not isinstance(scaffold_map, list) or not scaffold_map:
            violations.append("top-level field 'scaffold_map' must be a non-empty list")
            normalized["scaffold_map"] = []
        else:
            normalized_scaffold_map: List[Dict[str, str]] = []
            for index, item in enumerate(scaffold_map):
                if not isinstance(item, dict):
                    violations.append(f"scaffold_map[{index}] must be an object")
                    continue
                try:
                    normalized_scaffold_map.append(
                        {
                            "section_id": self._coerce_non_empty_str(item.get("section_id")),
                            "prior_knowledge": self._coerce_non_empty_str(item.get("prior_knowledge")),
                            "target_concept": self._coerce_non_empty_str(item.get("target_concept")),
                            "bridge_strategy": self._coerce_non_empty_str(item.get("bridge_strategy")),
                        }
                    )
                except ValueError:
                    violations.append(
                        f"scaffold_map[{index}] must contain non-empty section_id, prior_knowledge, target_concept, and bridge_strategy"
                    )
            normalized["scaffold_map"] = normalized_scaffold_map

        difficulty_level = outline_data.get("difficulty_level")
        if difficulty_level is not None:
            try:
                normalized["difficulty_level"] = self._coerce_non_empty_str(difficulty_level)
            except ValueError:
                violations.append("top-level field 'difficulty_level' must be a non-empty string when present")
        elif self.forced_difficulty_level:
            violations.append("top-level field 'difficulty_level' must be present when forced_difficulty_level is set")
            normalized["difficulty_level"] = self.forced_difficulty_level

        if self.forced_difficulty_level:
            actual_difficulty = str(outline_data.get("difficulty_level", "")).strip().lower()
            expected_difficulty = str(self.forced_difficulty_level).strip().lower()
            if actual_difficulty != expected_difficulty:
                violations.append(
                    f"difficulty_level must equal forced_difficulty_level '{self.forced_difficulty_level}'"
                )

        sections = outline_data.get("sections")
        if not isinstance(sections, list):
            violations.append("top-level field 'sections' must be a list")
            sections = []

        if not (6 <= len(sections) <= 9):
            violations.append("sections must contain 6 to 9 items")

        normalized_sections: List[Dict[str, Any]] = []
        total_duration = 0
        for index, section in enumerate(sections):
            if not isinstance(section, dict):
                violations.append(f"sections[{index}] must be an object")
                continue
            normalized_section: Dict[str, Any] = {}
            required_string_fields = [
                "id",
                "title",
                "content",
                "learning_objective",
                "prior_knowledge_activation",
                "new_concept",
                "misconception_check",
                "bridge_to_next",
            ]
            for field_name in required_string_fields:
                try:
                    normalized_section[field_name] = self._coerce_non_empty_str(section.get(field_name))
                except ValueError:
                    violations.append(f"sections[{index}].{field_name} must be a non-empty string")

            evidence_basis = section.get("evidence_basis")
            if not isinstance(evidence_basis, list) or not evidence_basis:
                violations.append(f"sections[{index}].evidence_basis must be a non-empty list")
                normalized_section["evidence_basis"] = []
            else:
                normalized_evidence_basis = []
                for evidence_index, evidence_item in enumerate(evidence_basis):
                    if not isinstance(evidence_item, dict):
                        violations.append(
                            f"sections[{index}].evidence_basis[{evidence_index}] must be an object"
                        )
                        continue
                    try:
                        normalized_evidence_basis.append(
                            {
                                "claim": self._coerce_non_empty_str(evidence_item.get("claim")),
                                "source_type": self._coerce_non_empty_str(evidence_item.get("source_type")),
                                "anchor": self._coerce_non_empty_str(evidence_item.get("anchor")),
                            }
                        )
                    except ValueError:
                        violations.append(
                            f"sections[{index}].evidence_basis[{evidence_index}] must contain non-empty claim, source_type, and anchor"
                        )
                normalized_section["evidence_basis"] = normalized_evidence_basis

            estimated_duration = section.get("estimated_duration")
            if not isinstance(estimated_duration, int) or estimated_duration <= 0:
                violations.append(f"sections[{index}].estimated_duration must be a positive integer")
            else:
                normalized_section["estimated_duration"] = estimated_duration
                total_duration += estimated_duration

            normalized_sections.append(normalized_section)

        target_seconds = int((self.duration * 60) / 1.4)
        allowed_delta = max(20, int(target_seconds * 0.25))
        if sections and abs(total_duration - target_seconds) > allowed_delta:
            violations.append(
                f"sum of estimated_duration must stay near {target_seconds} seconds (got {total_duration})"
            )

        normalized["sections"] = normalized_sections
        return normalized, violations

    def _validate_index_list(self, field_name: str, value: Any, line_count: int, allow_empty: bool = False) -> List[int]:
        if not isinstance(value, list):
            raise ValueError(f"{field_name} must be a list of integers")
        normalized: List[int] = []
        seen = set()
        for item in value:
            if not isinstance(item, int):
                raise ValueError(f"{field_name} must contain only integers")
            if not (0 <= item < line_count):
                raise ValueError(f"{field_name} index out of range: {item}")
            if item in seen:
                raise ValueError(f"{field_name} contains duplicate index: {item}")
            seen.add(item)
            normalized.append(item)
        if not allow_empty and not normalized:
            raise ValueError(f"{field_name} must not be empty")
        return normalized

    def _validate_single_index(self, field_name: str, value: Any, line_count: int) -> int:
        if not isinstance(value, int):
            raise ValueError(f"{field_name} must be an integer")
        if not (0 <= value < line_count):
            raise ValueError(f"{field_name} index out of range: {value}")
        return value

    def _max_new_terms_per_section(self) -> int:
        parsed_profile = getattr(self.user_profile, "parsed_profile", {}) or {}
        stage2_guidance = parsed_profile.get("stage2_storyboard_guidance", {}) or {}
        value = stage2_guidance.get("max_new_terms_per_section", 3)
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return 3
        return parsed if parsed > 0 else 3

    def _build_storyboard_retry_prompt(
        self,
        base_prompt: str,
        raw_content: str,
        violations: List[str],
        invalid_section_ids: Optional[List[str]] = None,
    ) -> str:
        violations_json = json.dumps(violations, ensure_ascii=False, indent=2)
        section_note = ""
        if invalid_section_ids:
            section_note = (
                "Only the following sections need to be corrected; keep all other valid sections logically unchanged: "
                + ", ".join(invalid_section_ids)
                + "\n"
            )
        return (
            f"{base_prompt}\n\n"
            "The previous storyboard output was rejected by runtime validation.\n"
            f"{section_note}"
            "Fix the violations below and regenerate the FULL JSON storyboard.\n"
            "Do not explain anything. Return JSON only.\n\n"
            f"Validation violations:\n{violations_json}\n\n"
            f"Previous output:\n{raw_content}"
        )

    def _validate_storyboard_data(self, storyboard_data: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str], List[str]]:
        violations: List[str] = []
        invalid_section_ids: List[str] = []
        sections = storyboard_data.get("sections")
        if not isinstance(sections, list) or not sections:
            return {"sections": []}, ["top-level field 'sections' must be a non-empty list"], []

        max_new_terms = self._max_new_terms_per_section()
        normalized_sections: List[Dict[str, Any]] = []
        for index, section in enumerate(sections):
            section_id = f"section_{index}"
            if isinstance(section, dict) and str(section.get("id", "")).strip():
                section_id = str(section.get("id")).strip()
            section_errors: List[str] = []
            if not isinstance(section, dict):
                violations.append(f"sections[{index}] must be an object")
                invalid_section_ids.append(section_id)
                continue

            normalized_section: Dict[str, Any] = {"id": section_id}
            try:
                normalized_section["title"] = self._coerce_non_empty_str(section.get("title"))
            except ValueError:
                section_errors.append("title must be a non-empty string")

            lecture_lines_raw = section.get("lecture_lines")
            if not isinstance(lecture_lines_raw, list) or not lecture_lines_raw:
                section_errors.append("lecture_lines must be a non-empty list")
                lecture_lines: List[str] = []
            else:
                lecture_lines = []
                for line in lecture_lines_raw:
                    text = str(line).strip()
                    if text:
                        lecture_lines.append(text)
                if not lecture_lines:
                    section_errors.append("lecture_lines must contain non-empty strings")
            normalized_section["lecture_lines"] = lecture_lines

            animations_raw = section.get("animations")
            if not isinstance(animations_raw, list) or not animations_raw:
                section_errors.append("animations must be a non-empty list")
                normalized_section["animations"] = []
            else:
                normalized_section["animations"] = [str(item).strip() for item in animations_raw if str(item).strip()]
                if not normalized_section["animations"]:
                    section_errors.append("animations must contain non-empty strings")

            estimated_duration = section.get("estimated_duration")
            if not isinstance(estimated_duration, int) or estimated_duration <= 0:
                section_errors.append("estimated_duration must be a positive integer")
            else:
                normalized_section["estimated_duration"] = estimated_duration

            line_count = len(lecture_lines)
            if line_count:
                try:
                    normalized_section["highlight_groups"] = self._normalize_highlight_groups(
                        lecture_lines,
                        section.get("highlight_groups"),
                    )
                except ValueError as exc:
                    section_errors.append(str(exc))
                    normalized_section["highlight_groups"] = self._build_default_highlight_groups(lecture_lines)

                try:
                    normalized_section["evidence_lines_indices"] = self._validate_index_list(
                        "evidence_lines_indices",
                        section.get("evidence_lines_indices"),
                        line_count,
                        allow_empty=False,
                    )
                except ValueError as exc:
                    section_errors.append(str(exc))
                    normalized_section["evidence_lines_indices"] = []

                try:
                    normalized_section["intro_transition_spoken"] = section.get("intro_transition_spoken")
                except Exception as exc:
                    section_errors.append(str(exc))
                    normalized_section["intro_transition_spoken"] = None

                try:
                    normalized_section["outro_transition_spoken"] = section.get("outro_transition_spoken")
                except Exception as exc:
                    section_errors.append(str(exc))
                    normalized_section["outro_transition_spoken"] = None

                new_terms = section.get("new_terms_introduced")
                if not isinstance(new_terms, list):
                    section_errors.append("new_terms_introduced must be a list")
                    normalized_section["new_terms_introduced"] = []
                else:
                    normalized_section["new_terms_introduced"] = [str(item).strip() for item in new_terms if str(item).strip()]
                    if len(normalized_section["new_terms_introduced"]) > max_new_terms:
                        section_errors.append(
                            f"new_terms_introduced exceeds max_new_terms_per_section ({max_new_terms})"
                        )
            else:
                normalized_section["highlight_groups"] = []
                normalized_section["evidence_lines_indices"] = []
                normalized_section["intro_transition_spoken"] = None
                normalized_section["outro_transition_spoken"] = None
                normalized_section["new_terms_introduced"] = []

            normalized_sections.append(normalized_section)
            if section_errors:
                invalid_section_ids.append(section_id)
                violations.extend([f"{section_id}: {error}" for error in section_errors])

        return {"sections": normalized_sections}, violations, invalid_section_ids


    def _fallback_trim_sections_by_duration(self, sections: List[Section], target_minutes: int) -> List[Section]:
        target_seconds = max(0, int(target_minutes) * 60)
        selected = []
        total_seconds = 0
        for section in sections:
            section_seconds = self._estimate_section_seconds(section)
            if selected and total_seconds + section_seconds > target_seconds:
                break
            selected.append(section)
            total_seconds += section_seconds
        return selected or sections

    def _video_limit_minutes(self) -> int:
        return max(1, int(self.max_video_seconds / 60))

    def _select_sections_with_ai(self) -> None:
        if not self.sections:
            return

        total_estimated = sum(self._estimate_section_seconds(s) for s in self.sections)
        hard_limit_seconds = self.max_video_seconds

        if total_estimated <= hard_limit_seconds and len(self.sections) <= 10:
            print(f"🧩 当前总预估时长为 {total_estimated} 秒，节数为 {len(self.sections)}，未超过硬上限（{hard_limit_seconds} 秒），无需删减")
            return

        payload = []
        for section in self.sections:
            preview_lines = section.lecture_lines[:2] if section.lecture_lines else []
            payload.append(
                {
                    "id": section.id,
                    "title": section.title,
                    "estimated_seconds": self._estimate_section_seconds(section),
                    "preview_lines": preview_lines,
                }
            )

        prompt = f"""
You are selecting the most critical sections for a lesson while preserving logical flow.

Target total duration: {self.duration} minutes (3-8 minutes)
Knowledge point: {self.learning_topic}
Learner difficulty: {self._get_user_difficulty_preference()}

Sections (in original order):
{json.dumps(payload, ensure_ascii=False, indent=2)}

Task:
- Choose a subset of section IDs that keeps the lesson logically coherent.
- Keep the original order (do not reorder).
- Aim to fit the target duration based on estimated_seconds.

Return ONLY a JSON array of section IDs, e.g. ["section_1", "section_2"].
"""
        try:
            response = self._request_api_and_track_tokens(prompt, max_tokens=200)
            raw_text = self._extract_response_text(response)
            selected_ids = json.loads(extract_json_from_markdown(raw_text))
        except Exception:
            selected_ids = []

        id_set = {section.id for section in self.sections}
        if not isinstance(selected_ids, list):
            selected_ids = []
        selected_ids = [section_id for section_id in selected_ids if section_id in id_set]

        if not selected_ids:
            self.sections = self._fallback_trim_sections_by_duration(self.sections, self._video_limit_minutes())
            print(f"🧩 AI 选节失败，已按时长顺序截断到 {self.max_video_seconds} 秒硬上限")
            return

        selected_set = set(selected_ids)
        ordered_sections = [section for section in self.sections if section.id in selected_set]

        if not ordered_sections:
            self.sections = self._fallback_trim_sections_by_duration(self.sections, self._video_limit_minutes())
            print(f"🧩 AI 选节为空，已按时长顺序截断到 {self.max_video_seconds} 秒硬上限")
            return

        trimmed_sections = self._fallback_trim_sections_by_duration(ordered_sections, self._video_limit_minutes())
        self.sections = trimmed_sections
        print(f"🧩 AI 已筛选小节: {len(self.sections)} 个")

    def generate_outline(self) -> TeachingOutline:
        self._ensure_ai_duration_selected()
        outline_file = self.output_dir / "outline.json"

        if outline_file.exists():
            print("📂 正在读取大纲...")
            with open(outline_file, "r", encoding="utf-8") as f:
                outline_data = json.load(f)
            outline_data, outline_violations = self._validate_outline_data(outline_data)
            if outline_violations:
                raise ValueError(f"Cached outline failed validation: {'; '.join(outline_violations)}")
        else:
            """Step 1: Generate teaching outline from topic"""
            refer_img_path = (
                self.knowledge_ref_img_folder / img_name
                if (img_name := self.KNOWLEDGE2PATH.get(self.learning_topic)) is not None
                else None
            )
            prompt1 = get_prompt1_outline(
                knowledge_point=self.learning_topic,
                duration=self.duration,
                reference_image_path=refer_img_path,
                user_profile=self.user_profile,
                forced_difficulty_level=self.forced_difficulty_level,
                subject=self.subject,
            )

            print(f"📝 正在生成大纲...")
            retry_prompt = prompt1
            outline_data = None
            last_validation_errors: List[str] = []
            validation_retry_limit = 3

            for attempt in range(1, validation_retry_limit + 1):
                api_func = self._request_api_and_track_tokens if refer_img_path else self._request_api_and_track_tokens
                response = api_func(retry_prompt, max_tokens=self.max_code_token_length)
                if response is None:
                    print(f"⚠️ 第 {attempt} 次尝试失败，正在重试...")
                    if attempt == validation_retry_limit:
                        raise ValueError("API 请求多次失败")
                    continue
                try:
                    content = response.candidates[0].content.parts[0].text
                except Exception:
                    try:
                        content = response.choices[0].message.content
                    except Exception:
                        content = str(response)
                try:
                    extracted_content = self._extract_outline_json(content)
                    parsed_outline = json.loads(extracted_content)
                except json.JSONDecodeError:
                    print(f"⚠️ 第 {attempt} 次尝试大纲格式无效，正在重试...")
                    retry_prompt = self._build_outline_retry_prompt(
                        prompt1,
                        content,
                        ["Output must be valid JSON parseable by Python json.loads()."],
                    )
                    if attempt == validation_retry_limit:
                        raise ValueError("大纲格式多次无效，请检查提示词或 API 响应")
                    continue

                normalized_outline, validation_errors = self._validate_outline_data(parsed_outline)
                if validation_errors:
                    last_validation_errors = validation_errors
                    print(f"⚠️ 第 {attempt} 次尝试大纲结构校验失败，正在重试...")
                    retry_prompt = self._build_outline_retry_prompt(prompt1, extracted_content, validation_errors)
                    if attempt == validation_retry_limit:
                        outline_data, _ = self._apply_outline_fallbacks(parsed_outline, validation_errors)
                        with open(self.output_dir / "outline.json", "w", encoding="utf-8") as f:
                            json.dump(outline_data, f, ensure_ascii=False, indent=2)
                        break
                    continue

                outline_data = normalized_outline
                with open(self.output_dir / "outline.json", "w", encoding="utf-8") as f:
                    json.dump(outline_data, f, ensure_ascii=False, indent=2)
                break

            if outline_data is None:
                if last_validation_errors:
                    raise ValueError("大纲结构多次无效: " + "; ".join(last_validation_errors))
                raise ValueError("大纲生成失败")

        self.outline = TeachingOutline(
            topic=outline_data["topic"],
            target_audience=outline_data["target_audience"],
            sections=outline_data["sections"],
            factuality_anchor_checklist=outline_data.get("factuality_anchor_checklist"),
            scaffold_map=outline_data.get("scaffold_map"),
            difficulty_level=outline_data.get("difficulty_level"),
        )
        print(f"== 大纲已生成: {self.outline.topic}")
        return self.outline

    def generate_storyboard(self) -> List[Section]:
        """Step 2: Generate teaching storyboard from outline (optionally with asset enhancement)"""
        if not self.outline:
            raise ValueError("大纲未生成，请先生成大纲")

        storyboard_file = self.output_dir / "storyboard.json"
        enhanced_storyboard_file = self.output_dir / "storyboard_with_assets.json"

        if enhanced_storyboard_file.exists():
            print("📂 发现已增强的分镜脚本，正在加载...")
            with open(enhanced_storyboard_file, "r", encoding="utf-8") as f:
                self.enhanced_storyboard = json.load(f)
        elif storyboard_file.exists():
            print("📂 发现分镜脚本，正在加载...")
            with open(storyboard_file, "r", encoding="utf-8") as f:
                storyboard_data = json.load(f)
            storyboard_data, storyboard_violations, _ = self._validate_storyboard_data(storyboard_data)
            if storyboard_violations:
                raise ValueError(f"Cached storyboard failed validation: {'; '.join(storyboard_violations)}")
            if self.use_assets:
                self.enhanced_storyboard = self._enhance_storyboard_with_assets(storyboard_data)
            else:
                self.enhanced_storyboard = storyboard_data
        else:
            print("🎬 正在生成分镜脚本...")
            refer_img_path = (
                self.knowledge_ref_img_folder / img_name
                if (img_name := self.KNOWLEDGE2PATH.get(self.learning_topic)) is not None
                else None
            )

            prompt2 = get_prompt2_storyboard(
                outline=json.dumps(self.outline.__dict__, ensure_ascii=False, indent=2),
                duration=self.duration,
                reference_image_path=refer_img_path,
                user_profile=self.user_profile,
                subject=self.subject,
            )

            retry_prompt = prompt2
            storyboard_data = None
            last_validation_errors: List[str] = []
            invalid_section_ids: List[str] = []
            validation_retry_limit = 3
            for attempt in range(1, validation_retry_limit + 1):
                api_func = self._request_api_and_track_tokens
                response = api_func(retry_prompt, max_tokens=self.max_code_token_length)
                if response is None:
                    print(f"⚠️ 第 {attempt} 次尝试 API 请求失败，正在重试...")
                    if attempt == validation_retry_limit:
                        raise ValueError("API 请求多次失败")
                    continue

                try:
                    content = response.candidates[0].content.parts[0].text
                except Exception:
                    try:
                        content = response.choices[0].message.content
                    except Exception:
                        content = str(response)

                try:
                    json_str = extract_json_from_markdown(content)
                    parsed_storyboard = json.loads(json_str)
                except json.JSONDecodeError as e:
                    print(f"⚠️ 第 {attempt} 次尝试分镜格式无效，正在重试...")
                    print(f"❌ JSON Error: {e}")
                    print(f"❌ Content snippet: {content[:1000]}...")
                    retry_prompt = self._build_storyboard_retry_prompt(
                        prompt2,
                        content,
                        ["Output must be valid JSON parseable by Python json.loads()."],
                    )
                    if attempt == validation_retry_limit:
                        raise ValueError("分镜格式多次无效，请检查提示词或 API 响应")
                    continue

                normalized_storyboard, validation_errors, invalid_section_ids = self._validate_storyboard_data(parsed_storyboard)
                if validation_errors:
                    last_validation_errors = validation_errors
                    print(f"⚠️ 第 {attempt} 次尝试分镜结构校验失败，正在重试...")
                    retry_prompt = self._build_storyboard_retry_prompt(
                        prompt2,
                        json_str,
                        validation_errors,
                        invalid_section_ids=invalid_section_ids,
                    )
                    if attempt == validation_retry_limit:
                        storyboard_data, _ = self._apply_storyboard_fallbacks(parsed_storyboard, validation_errors)
                        with open(storyboard_file, "w", encoding="utf-8") as f:
                            json.dump(storyboard_data, f, ensure_ascii=False, indent=2)
                        if self.use_assets:
                            self.enhanced_storyboard = self._enhance_storyboard_with_assets(storyboard_data)
                        else:
                            self.enhanced_storyboard = storyboard_data
                        break
                    continue

                storyboard_data = normalized_storyboard

                with open(storyboard_file, "w", encoding="utf-8") as f:
                    json.dump(storyboard_data, f, ensure_ascii=False, indent=2)

                if self.use_assets:
                    self.enhanced_storyboard = self._enhance_storyboard_with_assets(storyboard_data)
                else:
                    self.enhanced_storyboard = storyboard_data
                break

            if storyboard_data is None:
                if last_validation_errors:
                    raise ValueError("分镜结构多次无效: " + "; ".join(last_validation_errors))
                raise ValueError("分镜生成失败")

        normalized_enhanced_storyboard, enhanced_violations, _ = self._validate_storyboard_data(self.enhanced_storyboard)
        if enhanced_violations:
            raise ValueError("增强后的分镜不合法: " + "; ".join(enhanced_violations))
        self.enhanced_storyboard = normalized_enhanced_storyboard

        self.sections = []
        for section_data in self.enhanced_storyboard["sections"]:
            lecture_lines, highlight_groups = self._prepare_section_lecture_lines(
                section_data.get("lecture_lines", []),
                section_data.get("highlight_groups"),
            )
            section = Section(
                id=section_data["id"],
                title=section_data["title"],
                lecture_lines=lecture_lines,
                animations=section_data["animations"],
                estimated_duration=section_data.get("estimated_duration"),
                highlight_groups=highlight_groups,
                evidence_lines_indices=section_data.get("evidence_lines_indices"),
                intro_transition_spoken=section_data.get("intro_transition_spoken"),
                outro_transition_spoken=section_data.get("outro_transition_spoken"),
                new_terms_introduced=section_data.get("new_terms_introduced"),
            )
            self.sections.append(section)

        self._select_sections_with_ai()
        print(f"== 分镜处理完成，共生成 {len(self.sections)} 个小节")
        return self.sections

    def _enhance_storyboard_with_assets(self, storyboard_data: dict) -> dict:
        """Enhance storyboard: smart analysis and download assets"""
        print("🤖 正在增强分镜：智能分析并下载素材...")

        try:
            enhanced_storyboard = process_storyboard_with_assets(
                storyboard=storyboard_data,
                api_function=self.API,
                assets_dir=str(self.assets_dir),
                iconfinder_api_key=self.iconfinder_api_key,
            )
            enhanced_storyboard_file = self.output_dir / "storyboard_with_assets.json"
            with open(enhanced_storyboard_file, "w", encoding="utf-8") as f:
                json.dump(enhanced_storyboard, f, ensure_ascii=False, indent=2)
            print("✅ 分镜已增强素材")
            return enhanced_storyboard

        except Exception as e:
            print(f"⚠️ 素材下载失败，使用原始分镜: {e}")
            return storyboard_data

    def inject_cover_section(self) -> None:
        """
        在 sections 列表最前面注入一个「封面」section。

        封面展示大标题（短名称）+ 副标题（完整 topic），并播放介绍旁白。
        使用确定性模板生成 Manim 代码，保证 100% 成功率。
        """
        self._ensure_outline()

        # 如果已经注入过，不重复注入
        if self.sections and self.sections[0].id == "section_cover":
            print("🎬 封面 section 已存在，跳过注入")
            return

        # 封面旁白：介绍语（会走 TTS 管线）
        intro_text = f"本视频将带你学习：{self.outline.topic}"

        cover_section = Section(
            id="section_cover",
            title=self.outline.topic,
            lecture_lines=[intro_text],
            animations=["Gradient background", "Create decoration lines", "FadeIn title", "FadeIn subtitle", "Play intro audio"],
            estimated_duration=10,  # 封面约 8-12 秒（含旁白）
            highlight_groups=[[0]],
        )

        # 插入到 sections 最前面
        self.sections.insert(0, cover_section)
        print(f"🎬 已注入封面 section（知识点：{self.outline.topic}）")

    def _generate_cover_code(self, section: Section) -> str:
        """
        为封面 section 使用确定性模板生成 Manim 代码。

        封面现在有旁白（介绍语），需要先生成 TTS 音频，再生成代码。

        Returns:
            完整的 Manim 代码字符串
        """
        self._ensure_outline()

        # 先生成 TTS 音频（封面有旁白了）
        section_steps = self.prepare_section_steps(section)

        cover_title, cover_subtitle = self._resolve_cover_title_pair()
        code = generate_cover_manim_code(
            topic=cover_subtitle,
            short_title=cover_title,
            section_steps=section_steps,
        )

        # 保存代码文件
        code_file = self.output_dir / f"{section.id}.py"
        with open(code_file, "w", encoding="utf-8") as f:
            f.write(code)

        self.section_codes[section.id] = code
        print(f"🎬 封面 section 代码已生成（模板化，含 TTS 旁白）")
        return code

    def inject_overview_section(self) -> None:
        """
        在 sections 列表最前面注入一个「课程导览」概述 section。

        该方法使用 AI 合并精简 section titles，然后生成 lecture_lines。
        概述 section 后续会正常走 TTS 管线（Stage 2.5）和模板化代码生成（跳过 LLM Stage 3）。
        """
        if not self.outline or not self.sections:
            print("⚠️ 大纲或分节尚未生成，跳过概述注入")
            return

        # 如果已经注入过，不重复注入
        if self.sections and self.sections[0].id == "section_overview":
            print("📋 概述 section 已存在，跳过注入")
            return

        # 从大纲提取 section titles（排除 overview 和 cover）
        section_titles = [
            s.title for s in self.sections
            if s.id not in ("section_overview", "section_cover")
        ]

        # 使用 AI 合并精简章节标题（3-6 条高层学习路径）
        print("🤖 正在使用 AI 提炼概述主线...")
        merged_titles = _merge_section_titles_with_ai(
            section_titles=section_titles,
            topic=self.outline.topic,
            api_func=self._request_api_and_track_tokens,
        )
        print(f"📋 提炼后共 {len(merged_titles)} 条概述主线: {merged_titles}")

        # 生成概述的 lecture_lines（仅包含屏幕展示的 roadmap phrases）
        overview_lines = build_overview_lecture_lines(
            section_titles=merged_titles,
            user_profile_summary=(self.user_profile.parsed_profile or {}).get("user_summary", {}) if self.user_profile else None,
        )

        overview_section = Section(
            id="section_overview",
            title=self.outline.topic,
            lecture_lines=overview_lines,
            animations=["FadeIn title", "Sequential FadeIn bullet points", "FadeIn ending"],
            estimated_duration=20,  # 概述约 15-25 秒
            highlight_groups=self._build_default_highlight_groups(overview_lines),
        )

        # 插入到 sections 最前面
        self.sections.insert(0, overview_section)
        print(f"📋 已注入概述 section（{len(overview_lines)} 条讲解行）")

    def _generate_overview_code(self, section: Section) -> str:
        """
        为概述 section 使用确定性模板生成 Manim 代码（跳过 LLM）。

        Returns:
            完整的 Manim 代码字符串
        """
        import re as _re

        # 确保 section_steps 已构建
        section_steps = self.prepare_section_steps(section)

        # 从 lecture_lines 中提取概述展示项
        merged_titles = []
        for line in section.lecture_lines:
            stripped_line = line.strip()
            if not stripped_line:
                continue

            # 旧格式兼容：提取 "the first part, Title" 中的标题部分
            en_match = _re.match(r"^the \w+ part, (.+)$", stripped_line, _re.IGNORECASE)
            if en_match:
                merged_titles.append(en_match.group(1).strip())
                continue

            # 旧格式兼容：提取 "第X部分，标题" 中的标题部分
            match = _re.match(r"^第[一二三四五六七八九十\d]+部分，(.+)$", stripped_line)
            if match:
                merged_titles.append(match.group(1).strip())
                continue

            # 旧格式兼容：去掉圈号前缀（如 "① "）
            cleaned = _re.sub(r"^[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳]\s*", "", stripped_line)
            if cleaned and cleaned != stripped_line:
                merged_titles.append(cleaned)
                continue

            merged_titles.append(stripped_line)

        code = generate_overview_manim_code(
            section_titles=merged_titles,
            section_steps=section_steps,
            page_title_text=self.outline.topic,
        )

        # 注入 base_class（与其他 section 统一处理）
        code = replace_base_class(code, base_class)

        # 保存代码文件
        code_file = self.output_dir / f"{section.id}.py"
        with open(code_file, "w", encoding="utf-8") as f:
            f.write(code)

        self.section_codes[section.id] = code
        print(f"📋 概述 section 代码已生成（模板化，无需 LLM）")
        return code

    def generate_section_code(self, section: Section, attempt: int = 1, feedback_improvements=None, error_message: str = None) -> str:
        """Generate Manim code for a single section
        
        Args:
            section: 章节对象
            attempt: 当前尝试次数
            feedback_improvements: MLLM 反馈的改进建议（效果不佳时）
            error_message: 上次运行失败的错误信息（运行失败时）
        """
        # ── 封面 section 使用确定性模板，跳过 LLM ──
        if section.id == "section_cover" and not feedback_improvements:
            code_file = self.output_dir / f"{section.id}.py"
            steps_file = self.output_dir / f"{section.id}_steps.json"
            audio_dir = self.output_dir / "audio" / section.id
            audio_files_exist = audio_dir.exists() and any(
                fp.is_file() for p in ("*.wav",) for fp in audio_dir.glob(p)
            )
            if (
                attempt == 1
                and code_file.exists()
                and steps_file.exists()
                and audio_files_exist
            ):
                section_steps = self._load_validated_cached_steps(section, steps_file)
                if section_steps is not None:
                    print(f"📂 发现 {section.id} 的现有代码，正在读取...")
                    with open(code_file, "r", encoding="utf-8") as f:
                        code = f.read()
                        self.section_codes[section.id] = code
                        return code
            return self._generate_cover_code(section)

        # ── 概述 section 使用确定性模板，跳过 LLM ──
        if section.id == "section_overview" and not feedback_improvements:
            code_file = self.output_dir / f"{section.id}.py"
            steps_file = self.output_dir / f"{section.id}_steps.json"
            audio_dir = self.output_dir / "audio" / section.id
            audio_files_exist = audio_dir.exists() and any(
                fp.is_file() for p in ("*.wav",) for fp in audio_dir.glob(p)
            )
            if (
                attempt == 1
                and code_file.exists()
                and steps_file.exists()
                and audio_files_exist
            ):
                section_steps = self._load_validated_cached_steps(section, steps_file)
                if section_steps is not None:
                    print(f"📂 发现 {section.id} 的现有代码，正在读取...")
                    with open(code_file, "r", encoding="utf-8") as f:
                        code = f.read()
                        self.section_codes[section.id] = code
                        return code
            return self._generate_overview_code(section)

        code_file = self.output_dir / f"{section.id}.py"
        steps_file = self.output_dir / f"{section.id}_steps.json"
        audio_dir = self.output_dir / "audio" / section.id
        audio_files_exist = audio_dir.exists() and any(
            file_path.is_file()
            for pattern in ("*.wav", "*.mp3", "*.ogg")
            for file_path in audio_dir.glob(pattern)
        )

        if (
            attempt == 1
            and code_file.exists()
            and not feedback_improvements
            and steps_file.exists()
            and audio_files_exist
        ):
            print(f"📂 发现 {section.id} 的现有代码，正在读取...")
            section_steps = self._load_validated_cached_steps(section, steps_file)
            if section_steps is not None:
                with open(code_file, "r", encoding="utf-8") as f:
                    code = f.read()
                    self.section_codes[section.id] = code
                    return code
        # print(f"💻 正在为 {section.id} 生成 Manim 代码 (尝试 {attempt}/{self.max_regenerate_tries})...")
        regenerate_note = ""
        if attempt > 1:
            # 仅用于运行失败的情况
            regenerate_note = get_regenerate_note(
                attempt, 
                MAX_REGENERATE_TRIES=self.max_regenerate_tries,
                error_message=error_message
            )

        # Add MLLM feedback and improvement suggestions
        if feedback_improvements:
            current_code = self.section_codes.get(section.id, "")
            try:
                modifier = GridCodeModifier(current_code)
                modified_code = modifier.parse_feedback_and_modify(feedback_improvements)
                modified_code = fix_png_path(modified_code, self.assets_dir)
                with open(code_file, "w", encoding="utf-8") as f:
                    f.write(modified_code)

                self.section_codes[section.id] = modified_code
                return modified_code
            except Exception as e:
                print(f"⚠️ GridCodeModifier 失败，回退到原始代码: {e}")
                code_gen_prompt = get_feedback_improve_code(
                    feedback=get_feedback_list_prefix(feedback_improvements), code=current_code
                )

        else:
            section_steps = self.prepare_section_steps(section)
            code_gen_prompt = get_prompt3_code(
                regenerate_note=regenerate_note,
                section=section,
                section_steps=section_steps,
                base_class=base_class,
                user_profile=self.user_profile,
                estimated_duration=section.estimated_duration,  # 传递预计时长
                subject=self.subject,
            )

        response = self._request_api_and_track_tokens(code_gen_prompt, max_tokens=self.max_code_token_length)
        if response is None:
            print(f"❌ 通过 API 生成 {section.id} 代码失败。")
            return ""

        try:
            code = response.candidates[0].content.parts[0].text
        except Exception:
            try:
                code = response.choices[0].message.content
            except Exception:
                code = str(response)
        if "```python" in code:
            code = code.split("```python")[1].split("```")[0].strip()
        elif "```" in code:
            code = code.split("```")[1].strip()

        # Replace base class
        code = replace_base_class(code, base_class)
        code = fix_png_path(code, self.assets_dir)

        if not feedback_improvements:
            is_valid, validation_error = self._validate_synced_step_coverage(code, len(section_steps))
            if not is_valid:
                if attempt < self.max_regenerate_tries:
                    print(f"⚠️ {section.id} 代码未覆盖全部音频步骤，重新生成: {validation_error}")
                    return self.generate_section_code(
                        section=section,
                        attempt=attempt + 1,
                        error_message=validation_error,
                    )
                raise ValueError(validation_error)

        with open(code_file, "w", encoding="utf-8") as f:
            f.write(code)

        self.section_codes[section.id] = code
        return code

    def prepare_section_steps(self, section: Section) -> List[dict]:
        steps_file = self.output_dir / f"{section.id}_steps.json"
        audio_dir = self.output_dir / "audio" / section.id
        if (
            steps_file.exists()
            and audio_dir.exists()
            and any(file_path.is_file() for file_path in audio_dir.glob("*.wav"))
        ):
            section_steps = self._load_validated_cached_steps(section, steps_file)
            if section_steps is not None:
                return section_steps

        section_steps = build_section_steps(
            section=section,
            output_root=self.output_dir,
            api_func=self._request_api_and_track_tokens,
            user_profile=self.user_profile,
        )
        expected_steps = 2 if section.id == "section_overview" else len(
            section.highlight_groups or self._build_default_highlight_groups(section.lecture_lines)
        )
        is_valid, validation_error = self._validate_cached_section_steps(section_steps, expected_steps)
        if not is_valid:
            raise ValueError(f"Generated invalid steps for {section.id}: {validation_error}")
        save_section_steps(section_steps, steps_file)
        self.section_steps[section.id] = section_steps
        return section_steps

    def _trim_sections_by_actual_tts_duration(self) -> None:
        if not self.sections:
            return

        # 1. 识别固定小节（封面/概览）
        pinned_ids = {"section_cover", "section_overview"}
        pinned_sections = [s for s in self.sections if s.id in pinned_ids]
        variable_sections = [s for s in self.sections if s.id not in pinned_ids]

        if not variable_sections:
            return

        # 2. 计算固定小节的时长和剩余预算
        pinned_duration = sum(self._actual_tts_duration_for_section(s) for s in pinned_sections)
        remaining_budget = max(0.0, float(self.max_video_seconds) - pinned_duration)

        # 3. 计算所有可变小节的总长
        variable_total_duration = sum(self._actual_tts_duration_for_section(s) for s in variable_sections)

        # 4. 如果没超预算，直接结束
        if variable_total_duration <= remaining_budget:
            total_duration = pinned_duration + variable_total_duration
            print(f"⏱️ TTS 实际总时长 {total_duration:.1f} 秒，未超过上限 {self.max_video_seconds} 秒，无需裁剪")
            return

        print(f"⚠️ 可变小节 TTS 时长 {variable_total_duration:.1f} 秒超过剩余预算 {remaining_budget:.1f} 秒 (上限 {self.max_video_seconds} 秒)，开始使用 AI 全局优化裁剪...")

        # 5. 准备发给 AI 的可变小节 Payload
        payload = []
        for section in variable_sections:
            dur = self._actual_tts_duration_for_section(section)
            if dur <= 0:
                dur = float(self._estimate_section_seconds(section))
            
            payload.append({
                "id": section.id,
                "title": section.title,
                "actual_tts_seconds": round(dur, 1),
                "preview_lines": section.lecture_lines[:2] if section.lecture_lines else []
            })

        # 6. 调用 AI 选择最连贯的子集
        prompt = f"""
You are selecting the most critical sections for a lesson while preserving logical flow to fit within a strict real audio length limit.

Remaining budget for variable sections: {remaining_budget} seconds (Max total: {self.max_video_seconds}s)
Knowledge point: {self.learning_topic}
Learner difficulty: {self._get_user_difficulty_preference()}

Variable Sections (in original order, with actual TTS duration):
{json.dumps(payload, ensure_ascii=False, indent=2)}

Task:
- Choose a subset of variable section IDs that keeps the lesson logically coherent.
- The sum of `actual_tts_seconds` of the chosen IDs MUST NOT exceed {remaining_budget} seconds.
- Keep the original order (do not reorder).
- Trim the least critical sections that do not affect the main logic flow.

Return ONLY a JSON array of section IDs, e.g. ["section_1", "section_3", "section_5"].
"""
        try:
            response = self._request_api_and_track_tokens(prompt, max_tokens=200)
            raw_text = self._extract_response_text(response)
            selected_ids = json.loads(extract_json_from_markdown(raw_text))
        except Exception:
            selected_ids = []

        if not isinstance(selected_ids, list):
            selected_ids = []

        # 7. 应用 AI 选择结果及后备逻辑
        id_set = {s.id for s in variable_sections}
        selected_ids = [sid for sid in selected_ids if sid in id_set]

        # 重新构建可变小节列表（按原序）
        ai_selected_variable = [s for s in variable_sections if s.id in selected_ids]

        # 如果 AI 结果为空或依然超时，执行最后的贪心截断兜底
        final_selected_variable = []
        current_dur = 0.0
        # 如果 AI 选了就用 AI 的，没选就用全部可变节进行兜底处理
        candidate_pool = ai_selected_variable if ai_selected_variable else variable_sections

        for s in candidate_pool:
            dur = self._actual_tts_duration_for_section(s)
            if dur <= 0: dur = float(self._estimate_section_seconds(s))
            if final_selected_variable and current_dur + dur > remaining_budget:
                continue
            final_selected_variable.append(s)
            current_dur += dur

        # 8. 更新 self.sections
        kept_ids = pinned_ids | {s.id for s in final_selected_variable}
        original_count = len(self.sections)
        trimmed_sections = [s for s in self.sections if s.id not in kept_ids]
        self.sections = [s for s in self.sections if s.id in kept_ids]

        total_duration = pinned_duration + current_dur
        print(f"⏱️ 最终 TTS 实际总时长 {total_duration:.1f} 秒，保留 {len(self.sections)}/{original_count} 节")
        if trimmed_sections:
            print(f"✂️ 已按 AI 逻辑优化裁剪小节: {[s.id for s in trimmed_sections]}")

    def debug_and_fix_code(self, section_id: str, max_fix_attempts: int = 3) -> Tuple[bool, Optional[str]]:
        """Enhanced debug and fix code method
        
        Returns:
            Tuple[bool, Optional[str]]: (成功与否, 最后一次错误信息)
        """
        if section_id not in self.section_codes:
            code_file = self.output_dir / f"{section_id}.py"
            if code_file.exists():
                print(f"📂 [Worker] 从文件重新加载代码: {section_id}")
                with open(code_file, "r", encoding="utf-8") as f:
                    self.section_codes[section_id] = f.read()
            else:
                return False, "代码文件不存在"
        
        last_error = None  # 保存最后一次错误信息

        # 动态解析 Scene 名称，避免类名与默认推断不一致
        code_content_for_scene = self.section_codes.get(section_id, "")
        scene_candidates = re.findall(r"class\s+(\w+)\s*\([^)]*\):", code_content_for_scene)
        # 过滤掉没有 construct 方法的类
        preferred_scene = None
        if scene_candidates:
            for cname in scene_candidates:
                # 简单检查, 该类后出现 'def construct' 字样
                pattern = rf"class\s+{cname}\s*\([^)]*\):[\s\S]*?def\s+construct\s*\("""
                if re.search(pattern, code_content_for_scene):
                    # 排除纯基类名称，如 TeachingScene/BaseScene 等
                    if cname.lower() not in ("teachingscene", "basescene"):
                        preferred_scene = cname
                        break
            if not preferred_scene:
                preferred_scene = scene_candidates[-1]

        # 封面 section 现在有旁白（介绍语），与其他 section 走同样的音频回灌流程
        is_cover = False  # 封面不再特殊处理

        # [Optimized] Check if video already exists to skip rendering
        scene_name_check = preferred_scene if preferred_scene else f"{section_id.title().replace('_', '')}Scene"
        code_file_check = f"{section_id}.py"
        video_patterns_check = [
            self.output_dir / "media" / "videos" / f"{code_file_check.replace('.py', '')}" / "480p15" / f"{scene_name_check}.mp4",
            self.output_dir / "media" / "videos" / "480p15" / f"{scene_name_check}.mp4",
            self.output_dir / "media" / "videos" / f"{code_file_check.replace('.py', '')}" / "720p30" / f"{scene_name_check}.mp4",
            self.output_dir / "media" / "videos" / "720p30" / f"{scene_name_check}.mp4",
            self.output_dir / "media" / "videos" / f"{code_file_check.replace('.py', '')}" / "1080p60" / f"{scene_name_check}.mp4",
            self.output_dir / "media" / "videos" / "1080p60" / f"{scene_name_check}.mp4",
        ]
        for video_path in video_patterns_check:
            if video_path.exists():
                # 封面无旁白，直接使用已有视频，跳过回灌
                if is_cover:
                    self.section_videos[section_id] = str(video_path)
                    print(f"✅ {self.learning_topic} {section_id} 发现已有封面视频，跳过渲染: {video_path}")
                    return True, None

                if self._video_has_audio_stream(video_path):
                    try:
                        fixed_video_path = self._remux_section_audio(section_id, video_path)
                    except Exception as remux_error:
                        print(f"⚠️ {self.learning_topic} {section_id} 已有视频回灌失败，将重新渲染: {remux_error}")
                        break

                    if self._video_has_audio_stream(fixed_video_path):
                        self.section_videos[section_id] = str(fixed_video_path)
                        print(f"✅ {self.learning_topic} {section_id} 发现已有视频，回灌后跳过渲染: {fixed_video_path}")
                        return True, None  # 成功，无错误
                    print(f"⚠️ {self.learning_topic} {section_id} 已有视频回灌后仍无音轨，重新渲染: {fixed_video_path}")
                    break
                print(f"⚠️ {self.learning_topic} {section_id} 已有视频缺少音轨，重新渲染: {video_path}")

        for fix_attempt in range(max_fix_attempts):
            print(f"🔧 {self.learning_topic} 正在调试 {section_id} (尝试 {fix_attempt + 1}/{max_fix_attempts})")

            try:
                # 首先尝试使用代码中真实存在的 Scene 名称，否则退回到默认推断
                scene_name = preferred_scene if preferred_scene else f"{section_id.title().replace('_', '')}Scene"
                code_file = f"{section_id}.py"
                cmd = [sys.executable, "-m", "manim", self.render_quality, str(code_file), scene_name]

                result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.output_dir, timeout=2000)

                if result.returncode == 0:
                    video_patterns = [
                        self.output_dir / "media" / "videos" / f"{code_file.replace('.py', '')}" / "480p15" / f"{scene_name}.mp4",
                        self.output_dir / "media" / "videos" / "480p15" / f"{scene_name}.mp4",
                        self.output_dir / "media" / "videos" / f"{code_file.replace('.py', '')}" / "720p30" / f"{scene_name}.mp4",
                        self.output_dir / "media" / "videos" / "720p30" / f"{scene_name}.mp4",
                        self.output_dir / "media" / "videos" / f"{code_file.replace('.py', '')}" / "1080p60" / f"{scene_name}.mp4",
                        self.output_dir / "media" / "videos" / "1080p60" / f"{scene_name}.mp4",
                    ]

                    for video_path in video_patterns:
                        if video_path.exists():
                            # 封面无旁白，渲染成功后直接使用，跳过回灌
                            if is_cover:
                                self.section_videos[section_id] = str(video_path)
                                print(f"✅ {self.learning_topic} {section_id} 封面渲染完成")
                                return True, None

                            try:
                                fixed_video_path = self._remux_section_audio(section_id, video_path)
                            except Exception as remux_error:
                                last_error = f"Audio remux failed: {remux_error}"
                                print(f"❌ {self.learning_topic} {section_id} 音频回灌失败: {remux_error}")
                                break

                            if not self._video_has_audio_stream(fixed_video_path):
                                last_error = f"Rendered video has no audio stream after remux: {fixed_video_path}"
                                print(f"❌ {self.learning_topic} {section_id} 回灌后仍无音轨: {fixed_video_path}")
                                break

                            self.section_videos[section_id] = str(fixed_video_path)
                            print(f"✅ {self.learning_topic} {section_id} 完成")
                            return True, None  # 成功，无错误
                
                # 保存错误信息
                last_error = result.stderr

                current_code = self.section_codes[section_id]
                fixed_code = self.scope_refine_fixer.fix_code_smart(section_id, current_code, result.stderr, self.output_dir)

                if fixed_code:
                    self.section_codes[section_id] = fixed_code
                    with open(self.output_dir / code_file, "w", encoding="utf-8") as f:
                        f.write(fixed_code)
                else:
                    break

            except subprocess.TimeoutExpired:
                last_error = "Manim 渲染超时 (超过 300 秒)"
                print(f"❌ {self.learning_topic} {section_id} 超时")
                break
            except Exception as e:
                last_error = str(e)
                print(f"❌ {self.learning_topic} {section_id} 失败，异常: {e}")
                break

        return False, last_error

    def get_mllm_feedback(self, section: Section, video_path: str, round_number: int = 1) -> VideoFeedback:
        print(f"🤖 {self.learning_topic} 使用 MLLM 分析视频 ({round_number}/{self.feedback_rounds}): {section.id}")

        current_code = self.section_codes[section.id]
        positions = self.extractor.extract_grid_positions(current_code)
        position_table = self.extractor.generate_position_table(positions)
        analysis_prompt = get_prompt4_layout_feedback(section=section, position_table=position_table)
        evaluation_prompt = get_prompt_aes(self.learning_topic)

        def _parse_layout(feedback_content):
            has_layout_issues, suggested_improvements = False, []
            try:
                data = json.loads(feedback_content)
                lay = data.get("layout", {})
                has_layout_issues = bool(lay.get("has_issues", False))
                for it in lay.get("improvements", []) or []:
                    if isinstance(it, dict):
                        prob = str(it.get("problem", "")).strip()
                        sol = str(it.get("solution", "")).strip()
                        if prob or sol:
                            suggested_improvements.append(f"[LAYOUT] Problem: {prob}; Solution: {sol}")

                pedagogy = data.get("pedagogy", {})
                for it in pedagogy.get("improvements", []) or []:
                    if isinstance(it, dict):
                        prob = str(it.get("problem", "")).strip()
                        sol = str(it.get("solution", "")).strip()
                        if prob or sol:
                            suggested_improvements.append(f"[PEDAGOGY] Problem: {prob}; Solution: {sol}")

            except json.JSONDecodeError:
                print(f"⚠️ {self.learning_topic} JSON 解析失败，回退到关键词分析")

                for m in re.finditer(
                    r"Problem:\s*(.*?);\s*Solution:\s*(.*?)(?=\n|$)", feedback_content, flags=re.IGNORECASE | re.DOTALL
                ):
                    suggested_improvements.append(f"[LAYOUT] Problem: {m.group(1).strip()}; Solution: {m.group(2).strip()}")

                if not suggested_improvements:
                    for sol in re.findall(r"Solution\s*:\s*(.+)", feedback_content, flags=re.IGNORECASE):
                        suggested_improvements.append(f"[LAYOUT] Problem: ; Solution: {sol.strip()}")

            has_pedagogy_issues = any(item.startswith("[PEDAGOGY]") for item in suggested_improvements)
            return has_layout_issues or has_pedagogy_issues, suggested_improvements

        def _parse_stage5_evaluation(feedback_content):
            try:
                data = json.loads(feedback_content)
            except json.JSONDecodeError:
                print(f"⚠️ {self.learning_topic} Stage5 评分 JSON 解析失败，跳过 good-enough 判定")
                return False, None, None, [], []

            scores = {
                "element_layout": float((data.get("element_layout") or {}).get("score", 0) or 0),
                "overall_score": float(data.get("overall_score", 0) or 0),
                "attractiveness": float((data.get("attractiveness") or {}).get("score", 0) or 0),
                "visual_consistency": float((data.get("visual_consistency") or {}).get("score", 0) or 0),
                "logic_flow": float((data.get("logic_flow") or {}).get("score", 0) or 0),
                "accuracy_depth": float((data.get("accuracy_depth") or {}).get("score", 0) or 0),
                "learner_fit_zpd": float((data.get("learner_fit_zpd") or {}).get("score", 0) or 0),
                "unsupported_claim_count": float((data.get("accuracy_depth") or {}).get("unsupported_claim_count", 0) or 0),
            }
            hard_blockers = [str(item).strip() for item in (data.get("hard_blockers") or []) if str(item).strip()]
            critical_failures = [str(item).strip() for item in (data.get("critical_failures") or []) if str(item).strip()]
            prompt_decision = bool(data.get("is_good_enough", False))
            reason = str(data.get("good_enough_reason", "")).strip() or None
            average_visual_score = (
                scores["element_layout"] + scores["attractiveness"] + scores["visual_consistency"]
            ) / 3
            meets_threshold = (
                scores["element_layout"] >= 12
                and scores["overall_score"] >= 76
                and average_visual_score >= 12
                and scores["logic_flow"] >= 15
                and scores["accuracy_depth"] >= 13
                and scores["learner_fit_zpd"] >= 15
                and scores["unsupported_claim_count"] == 0
            )
            pedagogy_gate_failed = (
                scores["logic_flow"] < 15
                or scores["learner_fit_zpd"] < 15
                or scores["unsupported_claim_count"] > 0
            )
            is_good_enough = (prompt_decision or meets_threshold) and not pedagogy_gate_failed and not hard_blockers and not critical_failures
            if not reason and critical_failures:
                reason = "; ".join(critical_failures)

            pedagogy_improvements = []
            if scores["unsupported_claim_count"] > 0:
                pedagogy_improvements.append(
                    f"[PEDAGOGY] Remove or justify unsupported factual claims. Unsupported claim count: {int(scores['unsupported_claim_count'])}."
                )
            if scores["learner_fit_zpd"] < 13:
                pedagogy_improvements.append(
                    "[PEDAGOGY] Improve learner fit: simplify unexplained jargon, reduce new-term load, and connect from prior knowledge."
                )
            if scores["logic_flow"] < 13:
                pedagogy_improvements.append(
                    "[PEDAGOGY] Improve scaffolding: strengthen transitions, ensure one core new concept per section, and add clearer bridge lines."
                )
            if scores["accuracy_depth"] < 13:
                pedagogy_improvements.append(
                    "[PEDAGOGY] Improve accuracy and depth: anchor key claims in named definitions, laws, theorems, experiments, or worked-example rules."
                )
            for item in hard_blockers:
                pedagogy_improvements.append(f"[PEDAGOGY] Resolve hard blocker: {item}")
            for item in critical_failures:
                pedagogy_improvements.append(f"[PEDAGOGY] Resolve critical failure: {item}")

            return is_good_enough, reason, scores, hard_blockers + critical_failures, pedagogy_improvements

        try:
            response = request_gemini_video_img(prompt=analysis_prompt, video_path=video_path, image_path=self.GRID_IMG_PATH)
            feedback_content = extract_answer_from_response(response)
            has_layout_issues, suggested_improvements = _parse_layout(feedback_content)

            evaluation_response = request_gemini_video_img(
                prompt=evaluation_prompt,
                video_path=video_path,
                image_path=self.GRID_IMG_PATH,
            )
            evaluation_content = extract_answer_from_response(evaluation_response)
            is_good_enough, good_enough_reason, evaluation_scores, hard_blockers, pedagogy_improvements = _parse_stage5_evaluation(
                evaluation_content
            )
            if pedagogy_improvements:
                suggested_improvements = pedagogy_improvements + suggested_improvements
            if has_layout_issues or hard_blockers:
                is_good_enough = False

            raw_response = json.dumps(
                {
                    "layout_feedback": feedback_content,
                    "stage5_evaluation": evaluation_content,
                },
                ensure_ascii=False,
            )
            feedback = VideoFeedback(
                section_id=section.id,
                video_path=video_path,
                has_issues=has_layout_issues or bool(pedagogy_improvements),
                suggested_improvements=suggested_improvements,
                raw_response=raw_response,
                is_good_enough=is_good_enough,
                good_enough_reason=good_enough_reason,
                evaluation_scores=evaluation_scores,
            )
            self.video_feedbacks[f"{section.id}_round{round_number}"] = feedback
            return feedback

        except Exception as e:
            print(f"❌ {self.learning_topic} MLLM 分析失败: {str(e)}")
            return VideoFeedback(
                section_id=section.id,
                video_path=video_path,
                has_issues=False,
                suggested_improvements=[],
                raw_response=f"Error: {str(e)}",
            )

    def optimize_with_feedback(self, section: Section, feedback: VideoFeedback) -> bool:
        """Optimize the code based on feedback from the MLLM"""
        if not feedback.has_issues or not feedback.suggested_improvements:
            print(f"✅ {self.learning_topic} {section.id} 无需优化")
            return True

        # === Step 1: back up original code AND video ===
        original_code_content = self.section_codes[section.id]
        
        # [新增] 备份原始视频文件
        original_video_path = self.section_videos.get(section.id)
        video_backup_path = None
        if original_video_path and os.path.exists(original_video_path):
            try:
                video_path_obj = Path(original_video_path)
                # 创建备份文件名，例如: Section01_backup.mp4
                video_backup_path = video_path_obj.with_name(f"{video_path_obj.stem}_backup{video_path_obj.suffix}")
                shutil.copy2(original_video_path, video_backup_path)
                print(f"📦 已备份原始视频: {video_backup_path}")
            except Exception as e:
                print(f"⚠️ 视频备份失败: {e}")

        for attempt in range(self.max_feedback_gen_code_tries):
            print(
                f"🎯 {self.learning_topic} MLLM 反馈优化 {section.id} 代码，尝试 {attempt + 1}/{self.max_feedback_gen_code_tries}"
            )

            # === Step 2: back up original code and apply improvements ===
            if attempt > 0:
                self.section_codes[section.id] = original_code_content

            # === Step 3: re-generate code with feedback ===
            self.generate_section_code(
                section=section, attempt=attempt + 1, feedback_improvements=feedback.suggested_improvements
            )
            success, _ = self.debug_and_fix_code(section.id, max_fix_attempts=self.max_mllm_fix_bugs_tries)
            
            if success:
                optimized_output_dir = self.output_dir / "optimized_videos"
                optimized_output_dir.mkdir(exist_ok=True)
                optimized_video_path = optimized_output_dir / f"{section.id}_optimized.mp4"

                if section.id in self.section_videos:
                    current_video_path = Path(self.section_videos[section.id])
                    if current_video_path.exists():
                        current_video_path.replace(optimized_video_path)
                        self.section_videos[section.id] = str(optimized_video_path)
                        print(f"✨ {self.learning_topic} {section.id} 优化后的视频已保存: {optimized_video_path}")
                        
                        # [新增] 优化成功，删除不再需要的备份文件
                        if video_backup_path and video_backup_path.exists():
                            try:
                                video_backup_path.unlink()
                            except:
                                pass
                    else:
                        print(f"⚠️ {self.learning_topic} {section.id} 未找到生成的视频文件: {current_video_path}")
                else:
                    print(f"⚠️ {self.learning_topic} {section.id} 未找到优化后的视频路径")
                return True
            else:
                print(
                    f"❌ {self.learning_topic} {section.id} MLLM 优化失败，尝试 {attempt + 1}/{self.max_feedback_gen_code_tries}"
                )
        
        print(f"❌ {self.learning_topic} {section.id} 所有优化尝试均失败，回滚到原始版本")
        
        # 回滚代码
        self.section_codes[section.id] = original_code_content
        with open(self.output_dir / f"{section.id}.py", "w", encoding="utf-8") as f:
            f.write(original_code_content)

        # [新增] 回滚视频文件
        if video_backup_path and video_backup_path.exists():
            try:
                target_path = Path(original_video_path)
                # 将备份文件移动回原路径（覆盖可能存在的失败产物）
                video_backup_path.replace(target_path)
                self.section_videos[section.id] = str(target_path)
                print(f"♻️ 已从备份恢复原始视频: {target_path}")
            except Exception as e:
                print(f"⚠️ 视频恢复失败: {e}")
        else:
            print(f"⚠️ 无法恢复视频：未找到备份文件")

        return False

    def generate_codes(self) -> Dict[str, str]:
        if not self.sections:
            raise ValueError(f"{self.learning_topic} 请先生成教学小节")

        def task(section):
            try:
                self.generate_section_code(section, attempt=1)
                return section.id, None
            except Exception as e:
                return section.id, e

        failed_sections = {}
        with ThreadPoolExecutor(max_workers=12) as executor:
            futures = {executor.submit(task, section): section for section in self.sections}
            for future in as_completed(futures):
                section_id, err = future.result()
                if err:
                    print(f"❌ {self.learning_topic} {section_id} 代码生成失败: {err}")
                    failed_sections[section_id] = err

        critical_sections = [section_id for section_id in ("section_cover", "section_overview") if section_id in failed_sections]
        if critical_sections:
            raise RuntimeError(
                f"{self.learning_topic} 关键 section 代码生成失败: "
                + ", ".join(f"{section_id}: {failed_sections[section_id]}" for section_id in critical_sections)
            )

        return self.section_codes

    def render_section(self, section: Section) -> bool:
        section_id = section.id

        try:
            success = False
            last_error = None  # 保存最后一次错误信息用于重试
            for regenerate_attempt in range(self.max_regenerate_tries):
                # print(f"🎯 Processing {section_id} (regenerate attempt {regenerate_attempt + 1}/{self.max_regenerate_tries})")
                try:
                    if regenerate_attempt > 0:
                        # 将上次的错误信息传递给代码生成，帮助 LLM 修复问题
                        self.generate_section_code(section, attempt=regenerate_attempt + 1, error_message=last_error)
                    success, last_error = self.debug_and_fix_code(section_id, max_fix_attempts=self.max_fix_bug_tries)
                    if success:
                        break
                    # last_error 已经在 debug_and_fix_code 中更新
                except Exception as e:
                    last_error = str(e)
                    print(f"⚠️ {section_id} 第 {regenerate_attempt + 1} 次尝试抛出异常: {str(e)}")
                    continue
            if not success:
                print(f"❌ {self.learning_topic} {section_id} 全部失败，跳过该小节")
                return False

            # MLLM feedback
            if self.use_feedback:
                try:
                    for round in range(self.feedback_rounds):
                        if self.section_feedback_stop_flags.get(section_id):
                            print(f"✅ {self.learning_topic} {section_id} 已标记停止优化，跳过剩余反馈轮次")
                            break
                        current_video = self.section_videos.get(section_id)
                        if not current_video:
                            print(f"❌ {self.learning_topic} {section_id} 没有可用视频进行 MLLM 反馈")
                            return success
                        try:
                            feedback = self.get_mllm_feedback(section, current_video, round_number=round + 1)
                            if feedback.is_good_enough:
                                self.section_feedback_stop_flags[section_id] = True
                                self.section_feedback_stop_reasons[section_id] = feedback.good_enough_reason or "stage5 evaluation passed"
                                print(
                                    f"✅ {self.learning_topic} {section_id} 第 {round+1} 轮已判定足够好，停止后续优化: {self.section_feedback_stop_reasons[section_id]}"
                                )
                                break

                            optimization_success = self.optimize_with_feedback(section, feedback)
                            if optimization_success:
                                pass
                            else:
                                print(
                                    f"⚠️ {self.learning_topic} {section_id} 第 {round+1} 轮 MLLM 反馈优化失败，使用当前版本"
                                )
                        except Exception as e:
                            print(
                                f"⚠️ {self.learning_topic} {section_id} 第 {round+1} 轮 MLLM 反馈处理异常: {str(e)}"
                            )
                            continue

                except Exception as e:
                    print(f"⚠️ {self.learning_topic} {section_id} MLLM 反馈处理异常: {str(e)}")

            return success

        except Exception as e:
            print(f"❌ {self.learning_topic} {section_id} 渲染过程异常: {str(e)}")
            return False

    def render_section_worker(self, section_data) -> Tuple[str, bool, Optional[str]]:
        section_id = "unknown"
        try:
            section, agent_class, kwargs = section_data
            section_id = section.id
            agent = agent_class(**kwargs)
            success = agent.render_section(section)
            video_path = agent.section_videos.get(section.id) if success else None
            return section_id, success, video_path

        except Exception as e:
            print(f"❌ {self.learning_topic} {section_id} 渲染过程异常: {str(e)}")
            return section_id, False, None

    def _is_video_file_stable(self, video_path: Path, interval_seconds: float = 0.2) -> bool:
        video_path = Path(video_path)
        if not video_path.exists() or video_path.stat().st_size <= 0:
            return False

        first_size = video_path.stat().st_size
        time.sleep(interval_seconds)
        if not video_path.exists():
            return False
        second_size = video_path.stat().st_size
        return first_size == second_size and second_size > 0

    def _discover_completed_section_videos(self) -> Dict[str, str]:
        discovered = {}
        ordered_sections = self.sections or []

        for section in ordered_sections:
            candidate_paths = []
            optimized_video_path = self.output_dir / "optimized_videos" / f"{section.id}_optimized.mp4"
            remux_video_path = self.output_dir / "audio_remux" / f"{section.id}_with_audio.mp4"
            candidate_paths.extend([optimized_video_path, remux_video_path])

            scene_name = f"{section.id.title().replace('_', '')}Scene"
            code_file = f"{section.id}.py"
            candidate_paths.extend([
                self.output_dir / "media" / "videos" / f"{code_file.replace('.py', '')}" / "480p15" / f"{scene_name}.mp4",
                self.output_dir / "media" / "videos" / "480p15" / f"{scene_name}.mp4",
                self.output_dir / "media" / "videos" / f"{code_file.replace('.py', '')}" / "720p30" / f"{scene_name}.mp4",
                self.output_dir / "media" / "videos" / "720p30" / f"{scene_name}.mp4",
                self.output_dir / "media" / "videos" / f"{code_file.replace('.py', '')}" / "1080p60" / f"{scene_name}.mp4",
                self.output_dir / "media" / "videos" / "1080p60" / f"{scene_name}.mp4",
            ])

            seen = set()
            for candidate_path in candidate_paths:
                candidate_path = Path(candidate_path)
                candidate_key = str(candidate_path.resolve()) if candidate_path.exists() else str(candidate_path)
                if candidate_key in seen or not candidate_path.exists() or candidate_path.stat().st_size <= 0:
                    continue
                seen.add(candidate_key)
                if not self._is_video_file_stable(candidate_path):
                    continue
                if self._video_has_audio_stream(candidate_path):
                    discovered[section.id] = str(candidate_path)
                    break

        return discovered

    def _discover_fallback_section_videos(self) -> Dict[str, str]:
        discovered = {}
        ordered_sections = self.sections or []

        for section in ordered_sections:
            candidate_paths = [
                self.output_dir / "optimized_videos" / f"{section.id}_optimized.mp4",
                self.output_dir / "audio_remux" / f"{section.id}_with_audio.mp4",
            ]

            for candidate_path in candidate_paths:
                candidate_path = Path(candidate_path)
                if not candidate_path.exists() or candidate_path.stat().st_size <= 0:
                    continue
                if not self._is_video_file_stable(candidate_path):
                    continue
                if self._video_has_audio_stream(candidate_path):
                    discovered[section.id] = str(candidate_path)
                    break

        return discovered

    def render_all_sections(
        self,
        max_workers: int = 12,
        section_timeout: Optional[int] = None,
        deadline: Optional[float] = None,
    ) -> Dict[str, str]:
        print(f"🎥 开始并行渲染所有分节视频 (最多 {max_workers} 个进程)...")

        if section_timeout is None:
            section_timeout = self.render_timeout_seconds

        tasks = []
        for section in self.sections:
            try:
                task_data = (section, self.__class__, self.get_serializable_state())
                tasks.append(task_data)
            except Exception as e:
                print(f"⚠️ 为 {section.id} 准备任务数据时出错: {str(e)}")
                continue

        if not tasks:
            print("❌ 没有有效任务可执行")
            return {}

        results = {}
        successful_count = 0
        failed_count = 0

        try:
            executor = ProcessPoolExecutor(max_workers=max_workers)
            try:
                future_to_section = {}
                for task in tasks:
                    try:
                        future = executor.submit(self.render_section_worker, task)
                        future_to_section[future] = task[0].id
                    except Exception as e:
                        section_id = task[0].id if task and len(task) > 0 else "unknown"
                        print(f"⚠️ 提交 {section_id} 任务时出错: {str(e)}")
                        failed_count += 1

                pending_futures = set(future_to_section)
                while pending_futures:
                    timeout = None
                    if deadline is not None:
                        remaining = deadline - time.time()
                        if remaining <= 0:
                            discovered_results = self._discover_completed_section_videos()
                            for sid, video_path in discovered_results.items():
                                if sid not in results:
                                    results[sid] = video_path
                                    successful_count += 1
                            print("⏰ 已到 29 分 45 秒保底截止，停止等待剩余渲染任务")
                            break
                        timeout = min(float(section_timeout), remaining)

                    done_futures, pending_futures = wait(
                        pending_futures,
                        timeout=timeout,
                        return_when=FIRST_COMPLETED,
                    )
                    if not done_futures:
                        discovered_results = self._discover_completed_section_videos()
                        for sid, video_path in discovered_results.items():
                            if sid not in results:
                                results[sid] = video_path
                                successful_count += 1
                        print("⏰ 已到 29 分 45 秒保底截止，立即扫描已落盘片段并进入视频合并")
                        break

                    for future in done_futures:
                        section_id = future_to_section[future]
                        try:
                            sid, success, video_path = future.result()

                            if success and video_path:
                                results[sid] = video_path
                                successful_count += 1
                                print(f"✅ {sid} 视频渲染成功: {video_path}")
                            else:
                                failed_count += 1
                                print(f"⚠️ {sid} 视频渲染失败")

                        except Exception as e:
                            failed_count += 1
                            print(f"❌ {section_id} 视频渲染过程错误: {str(e)}")
            finally:
                executor.shutdown(wait=False, cancel_futures=True)

        except Exception as e:
            print(f"❌ 并行渲染过程中出现严重错误: {str(e)}")

        # 更新结果并输出统计信息
        self.section_videos.update(results)

        total_sections = len(self.sections)
        print(f"\n📊 渲染统计:")
        print(f"   总小节数: {total_sections}")
        print(f"   成功率: {successful_count/total_sections*100:.1f}%" if total_sections > 0 else "   成功率: 0%")

        if successful_count == 0:
            print("❌ 所有分节视频渲染失败")
        elif failed_count > 0:
            print(
                f"⚠️ {failed_count} 个分节视频渲染失败，但 {successful_count} 个分节视频渲染成功"
            )
        else:
            print("🎉 所有分节视频渲染成功！")

        return results

    def merge_videos(self, output_filename: str = None) -> str:
        """Step 5: Merge all section videos"""
        if not self.section_videos:
            raise ValueError("没有可用视频进行合并")

        if output_filename is None:
            safe_name = topic_to_safe_name(self.learning_topic)
            output_filename = f"{safe_name}.mp4"

        output_path = self.output_dir / output_filename

        print(f"🔗 开始合并分节视频...")

        video_list_file = self.output_dir / "video_list.txt"
        ordered_ids = []
        if self.sections:
            ordered_ids = [s.id for s in self.sections]
        else:
            # 备选方案：如果缺失 sections 对象，使用自然排序 (Natural Sort)
            # 这里简单实现一个 key function 处理 trailing numbers
            def natural_keys(text):
                return [int(c) if c.isdigit() else c for c in re.split(r'(\d+)', text)]
            ordered_ids = sorted(self.section_videos.keys(), key=natural_keys)
        
        with open(video_list_file, "w", encoding="utf-8") as f:
            # 优先使用 ordered_ids (来自大纲 self.sections)
            target_ids = ordered_ids if ordered_ids else sorted(self.section_videos.keys())
    
            for section_id in target_ids:
            # 确保只处理不仅在大纲中、且实际生成了视频的 ID
                if section_id in self.section_videos:
                    video_path = self.section_videos[section_id].replace(f"{self.output_dir}/", "")
                    f.write(f"file '{video_path}'\n")

        # ffmpeg
        try:
            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
            result = subprocess.run(
                [ffmpeg_exe, "-y", "-f", "concat", "-safe", "0", "-i", str(video_list_file), "-c", "copy", str(output_path)],
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                if self._video_has_audio_stream(output_path):
                    return str(output_path)
                print(f"❌ 合并结果缺少音轨: {output_path}")
                return None
            else:
                print(f"❌ 合并分节视频失败: {result.stderr}")
                return None
        except Exception as e:
            print(f"❌ 合并分节视频失败: {e}")
            return None

    def GENERATE_VIDEO(self) -> str:
        """Generate complete video with MLLM feedback optimization"""
        pipeline_start = time.time()
        try:
            self._ensure_ai_duration_selected()
            self.generate_outline()
            self.generate_storyboard()
            self.inject_overview_section()
            self.generate_codes()
            self._trim_sections_by_actual_tts_duration()

            elapsed = time.time() - pipeline_start
            remaining_budget = max(120.0, float(self.pipeline_budget_seconds) - elapsed)
            section_timeout = max(60, min(self.render_timeout_seconds, int(remaining_budget * 0.8)))
            print(
                f"⏳ 流水线已用时 {elapsed:.1f} 秒 / {self.pipeline_budget_seconds} 秒，剩余 {remaining_budget:.1f} 秒，单节渲染超时 {section_timeout} 秒"
            )

            self.render_all_sections(section_timeout=section_timeout)
            final_video = self.merge_videos()
            if final_video:
                total_elapsed = time.time() - pipeline_start
                print(f"🎉 视频生成成功，总耗时 {total_elapsed:.1f} 秒: {final_video}")
                return final_video
            else:
                print(f"❌ {self.learning_topic} 失败")
                return None
        except Exception as e:
            print(f"❌ 视频生成失败: {e}")
            return None


def process_knowledge_point(idx, kp, folder_path: Path, cfg: RunConfig):
    print(f"\n🚀 正在处理知识点: {kp}")
    start_time = time.time()

    agent = TeachingVideoAgent(
        idx=idx,
        knowledge_point=kp,
        folder=folder_path,
        cfg=cfg,
    )
    video_path = agent.GENERATE_VIDEO()

    duration_minutes = (time.time() - start_time) / 60
    total_tokens = agent.token_usage["total_tokens"]

    print(f"✅ 知识点 '{kp}' 处理完成。耗时: {duration_minutes:.2f} 分钟, Token 使用: {total_tokens}")
    return kp, video_path, duration_minutes, total_tokens


def process_batch(batch_data, cfg: RunConfig):
    """Process a batch of knowledge points (serial within a batch)"""
    batch_idx, kp_batch, folder_path = batch_data
    results = []
    print(f"第 {batch_idx + 1} 批次开始处理 {len(kp_batch)} 个知识点")

    for local_idx, (idx, kp) in enumerate(kp_batch):
        try:
            if local_idx > 0:
                delay = random.uniform(3, 6)
                print(f"⏳ 第 {batch_idx + 1} 批次在处理 {kp} 前等待 {delay:.1f} 秒...")
                time.sleep(delay)
            results.append(process_knowledge_point(idx, kp, folder_path, cfg))
        except Exception as e:
            print(f"❌ 第 {batch_idx + 1} 批次处理 {kp} 失败: {e}")
            results.append((kp, None, 0, 0))
    return batch_idx, results


def run_Code2Video(
    knowledge_points: List[str], folder_path: Path, parallel=True, batch_size=3, max_workers=12, cfg: RunConfig = RunConfig()
):
    all_results = []

    if parallel:
        batches = []
        for i in range(0, len(knowledge_points), batch_size):
            batch = [(i + j, kp) for j, kp in enumerate(knowledge_points[i : i + batch_size])]
            batches.append((i // batch_size, batch, folder_path))

        print(
            f"🔄 并行批处理模式: {len(batches)} 个批次，每批 {batch_size} 个知识点，{max_workers} 个并发批次"
        )
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(process_batch, batch, cfg): batch for batch in batches}
            for future in as_completed(futures):
                try:
                    batch_idx, batch_results = future.result()
                    all_results.extend(batch_results)
                    print(f"✅ 第 {batch_idx + 1} 批次完成")
                except Exception as e:
                    print(f"❌ 第 {batch_idx + 1} 批次处理失败: {e}")
    else:
        print("🔄 串行处理模式")
        for idx, kp in enumerate(knowledge_points):
            try:
                all_results.append(process_knowledge_point(idx, kp, folder_path, cfg))
            except Exception as e:
                print(f"❌ 串行处理 {kp} 失败: {e}")
                all_results.append((kp, None, 0, 0))

    successful_runs = [r for r in all_results if r[1] is not None]
    total_runs = len(all_results)
    if not successful_runs:
        print("\n所有知识点处理失败，无法计算平均值。")
        return

    total_duration = sum(r[2] for r in successful_runs)
    total_tokens_consumed = sum(r[3] for r in successful_runs)
    num_successful = len(successful_runs)

    print("\n" + "=" * 50)
    print(f"   总知识点数: {total_runs}")
    print(f"   成功处理: {num_successful} ({num_successful/total_runs*100:.1f}%)")
    print(f"   平均耗时 [分]: {total_duration/num_successful:.2f} 分钟/知识点")
    print(f"   平均 Token 消耗: {total_tokens_consumed/num_successful:,.0f} tokens/知识点")
    print("=" * 50)


def get_api_and_output(API_name):
    mapping = {
        "gpt-41": (request_gpt41_token, "Chatgpt41"),
        "claude": (request_claude_token, "CLAUDE"),
        "gpt-5": (request_gpt5_token, "Chatgpt5"),
        "gpt-4o": (request_gpt4o_token, "Chatgpt4o"),
        "gpt-o4mini": (request_o4mini_token, "Chatgpto4mini"),
        "Gemini": (request_gemini_token, "Gemini"),
    }
    try:
        return mapping[API_name]
    except KeyError:
        raise ValueError("无效的 API 模型名称")


def build_and_parse_args(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--competition", action="store_true", default=False)
    parser.add_argument("--json", action="store_true", default=False)
    parser.add_argument("--api-model", dest="api_model", type=str, default="claude")
    parser.add_argument("--knowledge-point", dest="knowledge_point", type=str, default=None)
    parser.add_argument("--age", type=int, default=None)
    parser.add_argument("--gender", type=str, default=None)
    parser.add_argument("--language", type=str, default=None)
    parser.add_argument("--duration", type=int, default=5)
    parser.add_argument("--difficulty", choices=["simple", "medium", "hard"], default="medium")
    parser.add_argument("--extra-info", dest="extra_info", type=str, default="")
    parser.add_argument("--use-feedback", action="store_true", dest="use_feedback", default=True)
    parser.add_argument("--no-feedback", action="store_false", dest="use_feedback")
    parser.add_argument("--use-assets", action="store_true", dest="use_assets", default=True)
    parser.add_argument("--no-assets", action="store_false", dest="use_assets")
    parser.add_argument("--request-id", dest="request_id", type=str, default=None)
    parser.add_argument("--course-requirement", dest="course_requirement", type=str, default="")
    parser.add_argument("--student-persona", dest="student_persona", type=str, default="")
    parser.add_argument("--output-dir", dest="output_dir", type=str, default=None)
    parser.add_argument("--render-quality", dest="render_quality", type=str, default=None)

    parser.add_argument("--API", type=str, choices=["gpt-41", "claude", "gpt-5", "gpt-4o", "gpt-o4mini", "Gemini"], default=None)
    parser.add_argument("--knowledge_point", type=str, default=None)
    parser.add_argument("--user_profile", type=str, default="")
    parser.add_argument("--knowledge_file", type=str, default=None)
    parser.add_argument("--folder_prefix", type=str, default="TEST")
    parser.add_argument("--iconfinder_api_key", type=str, default="")
    parser.add_argument("--max_code_token_length", type=int, default=10000)
    parser.add_argument("--max_fix_bug_tries", type=int, default=10)
    parser.add_argument("--max_regenerate_tries", type=int, default=10)
    parser.add_argument("--max_feedback_gen_code_tries", type=int, default=3)
    parser.add_argument("--max_mllm_fix_bugs_tries", type=int, default=3)
    parser.add_argument("--feedback_rounds", type=int, default=2)
    parser.add_argument("--max_video_seconds", type=int, default=600)
    parser.add_argument("--pipeline_budget_seconds", type=int, default=1800)
    parser.add_argument("--render_timeout_seconds", type=int, default=600)
    parser.add_argument("--parallel", action="store_true", default=False)
    parser.add_argument("--no_parallel", action="store_false", dest="parallel")
    parser.add_argument("--parallel_group_num", type=int, default=3)
    parser.add_argument("--max_concepts", type=int, default=-1)
    parser.add_argument("--max_workers", type=int, default=None)
    return parser.parse_args(argv)


def _normalize_cli_args(args):
    if args.API:
        args.api_model = args.API
    args.legacy_knowledge_point = args.knowledge_point
    if args.user_profile and not args.extra_info:
        args.extra_info = args.user_profile
    return args


def _load_competition_request_from_stdin() -> Dict[str, Any]:
    raw = sys.stdin.read().strip()
    if not raw:
        raise ValueError("competition 模式需要通过 stdin 提供 JSON，或传入 --request-id --course-requirement --student-persona")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"competition 模式 stdin JSON 解析失败: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("competition 模式 stdin 输入必须是 JSON object")
    return payload


def _get_cli_competition_request(args) -> Dict[str, Any]:
    if args.request_id or args.course_requirement or args.student_persona:
        request_data = {
            "request_id": args.request_id,
            "course_requirement": args.course_requirement,
            "student_persona": args.student_persona,
        }
    else:
        request_data = _load_competition_request_from_stdin()

    request_id = request_data.get("request_id")
    course_requirement = request_data.get("course_requirement")
    student_persona = request_data.get("student_persona")
    if not request_id or not course_requirement or not student_persona:
        raise ValueError("competition 模式需要 request_id、course_requirement、student_persona")

    return {
        "request_id": request_id,
        "course_requirement": course_requirement,
        "student_persona": student_persona,
        "competition_mode": True,
        "duration": args.duration,
        "api_model": args.api_model,
        "output_dir": args.output_dir,
        "render_quality": args.render_quality,
    }


def _build_cli_request(args):
    if args.competition:
        return _get_cli_competition_request(args)

    knowledge_point = args.knowledge_point or args.legacy_knowledge_point
    if not knowledge_point:
        raise ValueError("standard 模式需要 --knowledge-point")
    return {
        "knowledge_point": knowledge_point,
        "age": args.age,
        "gender": args.gender,
        "language": args.language,
        "duration": args.duration,
        "difficulty": args.difficulty,
        "extra_info": args.extra_info,
        "use_feedback": args.use_feedback,
        "use_assets": args.use_assets,
        "api_model": args.api_model,
        "output_dir": args.output_dir,
        "render_quality": args.render_quality,
    }


def _upload_competition_artifacts(request_id: str, video_file: str, subtitle_file: Optional[str], expires_at: str):
    from src.api.config import settings
    from src.api.utils.file_utils import get_video_path, update_metadata
    from src.api.utils.oss_utils import (
        build_oss_object_key,
        generate_oss_signed_url,
        upload_file_to_oss,
    )

    video_path = get_video_path(video_file)
    if not video_path:
        raise ValueError("competition 模式生成完成但视频文件不可下载")

    video_object_key = build_oss_object_key(request_id, video_file)
    upload_file_to_oss(video_path, video_object_key, content_type="video/mp4")
    video_url = generate_oss_signed_url(video_object_key, settings.oss_url_expire_seconds)

    subtitle_url = None
    subtitle_object_key = None
    if subtitle_file:
        subtitle_path = get_video_path(subtitle_file)
        if subtitle_path:
            subtitle_object_key = build_oss_object_key(request_id, subtitle_file)
            upload_file_to_oss(subtitle_path, subtitle_object_key, content_type="application/x-subrip")
            subtitle_url = generate_oss_signed_url(subtitle_object_key, settings.oss_url_expire_seconds)

    update_metadata(
        Path(video_file).stem,
        {
            "oss_bucket_name": settings.oss_bucket_name,
            "oss_endpoint": settings.oss_endpoint,
            "oss_object_key": video_object_key,
            "oss_subtitle_object_key": subtitle_object_key,
            "oss_signed_url_expires_at": expires_at,
        },
    )
    return video_url, subtitle_url


def main(argv=None):
    from src.api.execution import ExecutionContext, execute_video_generation
    from src.api.utils.file_utils import get_video_path

    args = _normalize_cli_args(build_and_parse_args(argv))
    request_data = _build_cli_request(args)
    result = execute_video_generation(ExecutionContext(request_data=request_data))

    if args.competition:
        video_file = result.get("video_file")
        if not video_file or not get_video_path(video_file):
            raise ValueError("competition 模式生成完成但视频文件不可下载")

        metadata = result.get("metadata") or {}
        expires_at = metadata.get("public_link_expires_at")
        if not expires_at:
            raise ValueError("competition 模式生成完成但未写入 48 小时公开下载有效期")

        subtitle_file = result.get("subtitle_file")
        video_url, subtitle_url = _upload_competition_artifacts(
            request_data["request_id"],
            video_file,
            subtitle_file,
            expires_at,
        )

        output = {
            "request_id": request_data["request_id"],
            "video_url": video_url,
            "subtitle_url": subtitle_url,
            "supplementary_url": [],
        }
    else:
        metadata = result.get("metadata") or {}
        output = {
            "message": "视频生成成功。" if result.get("success") else result.get("error") or "视频生成失败。",
            "data": {
                "video_file": result.get("video_file"),
                "outline": metadata.get("outline"),
                "duration_seconds": (metadata.get("video_specs") or {}).get("duration_seconds"),
                "token_usage": result.get("token_usage"),
                "subtitle_file": result.get("subtitle_file"),
            },
        }

    print(json.dumps(output, ensure_ascii=False, indent=2 if args.json else None))
    return 0 if result.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
