import json
import os
import random
import re
import shutil
import ast
import subprocess
import time
import wave
from pathlib import Path
from typing import Callable, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from pydub import AudioSegment
import imageio_ffmpeg
from prompts.user_profile import UserProfile
from src.gpt_request import cfg


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TTS_BASE_URL = "https://vip.dmxapi.com/v1"
DEFAULT_TTS_MODEL = "tts-1"
DEFAULT_TTS_VOICE = "alloy"
LECTURE_PAGE_MAX_LINES = 9

# 并发控制配置（可通过环境变量调整）
LLM_EXPANSION_MAX_WORKERS = int(os.getenv("LLM_EXPANSION_MAX_WORKERS", "16"))
TTS_SYNTHESIS_MAX_WORKERS = int(os.getenv("TTS_SYNTHESIS_MAX_WORKERS", "32"))

# TTS模型负载均衡配置 - 使用DMXAPI可用的模型
TTS_MODELS = ["tts-1", "tts-1-1106"]
TTS_MODEL_MAX_WORKERS = 16  # 每个模型的最大并发数（总共32并发）


def extract_response_text(response) -> str:
    try:
        content = response.candidates[0].content.parts[0].text
    except Exception:
        try:
            content = response.choices[0].message.content
        except Exception:
            content = str(response)

    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip().strip('"')


def retry_with_backoff(operation_name: str, func: Callable, max_retries: int, base_delay: float):
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            return func()
        except Exception as exc:
            last_error = exc
            if attempt >= max_retries:
                raise RuntimeError(f"{operation_name} failed after {max_retries} attempts: {exc}") from exc

            delay = (base_delay * (2 ** (attempt - 1))) + random.uniform(0, base_delay)
            print(
                f"⚠️ {operation_name} failed on attempt {attempt}/{max_retries}: {exc}. "
                f"Retrying in {delay:.2f}s..."
            )
            time.sleep(delay)

    raise RuntimeError(f"{operation_name} failed: {last_error}")


# ── Overview narration expansion special prompt ─────────────────────────────────
_OVERVIEW_EXPANSION_EXAMPLES = """
You are a teaching video narration polisher, currently processing the overview section narration.

Task:
- Expand the screen text below into a more natural, conversational, single-sentence narration suitable for TTS playback
- Must sound as natural and fluent as an experienced teacher introducing the lesson roadmap in class
- Preserve the original meaning; do not introduce new knowledge points
- Must be "minimal incremental expansion", with a concise teacher-speech style
- Output must be a single line of plain text only, no quotes, numbering, or explanations
- Do not include any labels, prefixes, or metadata (like 'spoken_script:', 'output:', 'narration:', etc.)
- Output spoken_script must be in English

Reference examples (screen text → excellent narration):
- "Today's roadmap" → "Let's first look at the roadmap, so you can see how the lesson will unfold"
- "Core problem" → "We'll begin with the core problem, because that gives the whole lesson a clear starting point"
- "First useful idea" → "From there, we'll move into the first useful idea and see how it starts to help"
- "Key limitation" → "We'll also notice the key limitation, because that is what pushes us toward a better explanation"
- "Final takeaway" → "In the end, we'll connect everything into one clear takeaway"
- "Let's begin" → "With that roadmap in place, let's begin"

Screen text:
"""

_OVERVIEW_COMBINED_NARRATION_PROMPT = """
You are writing the spoken overview for the opening of an educational lesson.

Task:
- Write one short, coherent teacher-style introduction for TTS playback
- The screen phrases are roadmap labels only; the spoken narration should add the opening and closing transitions that do NOT appear on screen
- Start by introducing the lesson topic naturally
- Explicitly tell the learner that the lesson will follow the roadmap below
- Connect the roadmap phrases into 2 to 4 smooth sentences in the same order
- End with a natural transition into the first part, such as beginning the first part of the lesson
- Explain the progression and logic between the parts, not just a point-by-point list
- Keep the tone smooth, quick, and classroom-like
- Do not repeatedly start sentences with "next"
- Do not add knowledge points beyond the topic and roadmap phrases
- Output plain English text only, with no quotes, numbering, labels, or markdown

Lesson topic:
{topic}

Roadmap phrases:
{roadmap_lines}
"""


def build_overview_spoken_script(
    topic: str,
    lecture_lines: List[str],
    api_func: Callable,
    max_retries: int = 3,
    max_tokens: int = 300,
) -> str:
    core_lines = [str(line).strip() for line in lecture_lines if str(line).strip()]
    if not core_lines:
        safe_topic = topic.strip() or "this lesson"
        return f"In this video, we will introduce {safe_topic}. Let's begin the first part."

    roadmap_lines = "\n".join(f"- {line}" for line in core_lines)
    prompt = _OVERVIEW_COMBINED_NARRATION_PROMPT.format(
        topic=topic.strip() or "this lesson",
        roadmap_lines=roadmap_lines,
    ).strip()

    def _request():
        response = api_func(prompt, max_tokens=max_tokens)
        spoken_script = extract_response_text(response)
        if not spoken_script:
            raise ValueError("empty overview spoken_script")

        spoken_script = re.sub(r'^(spoken_script|output|narration)\s*[:：]\s*', '', spoken_script, flags=re.IGNORECASE)
        spoken_script = re.sub(r'^(spoken_script|output|narration)\s+', '', spoken_script, flags=re.IGNORECASE)
        spoken_script = spoken_script.strip()
        if not spoken_script:
            raise ValueError("empty overview spoken_script after cleanup")
        return spoken_script

    return retry_with_backoff(
        operation_name="overview spoken script generation",
        func=_request,
        max_retries=max_retries,
        base_delay=0.5,
    )


def _split_overview_spoken_script(spoken_script: str, topic: str) -> tuple[str, str]:
    cleaned = re.sub(r'^(spoken_script|output|narration)\s*[:：]\s*', '', spoken_script, flags=re.IGNORECASE)
    cleaned = re.sub(r'^(spoken_script|output|narration)\s+', '', cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.strip()

    safe_topic = topic.strip() or "this lesson"
    if not cleaned:
        return (
            f"Today we're diving into {safe_topic}.",
            "We'll follow the roadmap on screen step by step.",
        )

    parts = re.split(r"(?<=[.!?])\s+", cleaned, maxsplit=1)
    if len(parts) >= 2:
        intro_script = parts[0].strip()
        roadmap_script = parts[1].strip()
        if intro_script and roadmap_script:
            return intro_script, roadmap_script

    intro_script = f"Today we're diving into {safe_topic}."
    roadmap_script = cleaned if cleaned.endswith((".", "!", "?")) else f"{cleaned}."
    return intro_script, roadmap_script


def build_overview_cue_timings(lecture_lines: List[str], total_duration: float) -> List[float]:
    core_lines = [str(line).strip() for line in lecture_lines if str(line).strip()]
    if not core_lines:
        return []

    if total_duration <= 0:
        return [0.0 for _ in core_lines]

    lead_in = min(0.8, total_duration * 0.2)
    reveal_window = max(total_duration - lead_in, 0.0)
    if len(core_lines) == 1:
        return [0.0]

    interval = reveal_window / len(core_lines) if core_lines else 0.0
    cue_timings: List[float] = []
    for index in range(len(core_lines)):
        cue_time = max(0.0, lead_in + index * interval - 0.15)
        cue_timings.append(min(cue_time, total_duration))
    cue_timings[0] = 0.0
    return cue_timings



def _is_overview_screen_text(screen_text: str) -> bool:
    """判断 screen_text 是否属于概述部分（包含概述 / part 导航句式）。"""
    import re as _re
    if _re.search(r"第[一二三四五六七八九十\d]+部分", screen_text):
        return True
    if "本视频将分为" in screen_text:
        return True
    if "让我们正式开始" in screen_text or "开始具体内容的学习" in screen_text:
        return True
    if _re.search(r"^(the\s+(?:first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|eleventh|twelfth|\d+(?:st|nd|rd|th))\s+part)\b", screen_text, _re.IGNORECASE):
        return True
    if _re.search(r"^part\s+\d+\b", screen_text, _re.IGNORECASE):
        return True
    if screen_text.strip().lower().startswith("this video will be divided"):
        return True
    if screen_text.strip().lower().startswith("alright, let's now begin"):
        return True
    return False


def expand_screen_text_to_spoken_script(
    screen_text: str,
    api_func: Callable,
    max_retries: int = 3,
    max_tokens: int = 300,
    user_profile: Optional['UserProfile'] = None,
) -> str:
    # 根据年级获取术语简化策略
    grade_level = "high_school"  # 默认
    if user_profile and user_profile.parsed_profile:
        ap_level = user_profile.parsed_profile.get("user_summary", {}).get("ap_level", "standard")
        if ap_level == "middle_school":
            grade_level = "middle_school"
        elif ap_level in ["AP", "honors"]:
            grade_level = "ap_college"

    # 构建术语简化指令
    terminology_instruction = ""
    if grade_level == "middle_school":
        terminology_instruction = """
**Terminology Simplification (MANDATORY for middle school):**
- Replace ALL technical jargon with everyday language
- Use analogies for every technical term
- Examples:
  - ❌ "marginal gain" → ✅ "extra benefit"
  - ❌ "tangent line" → ✅ "flat line at the peak"
  - ❌ "inference engine" → ✅ "reasoning system"
  - ❌ "lignin" → ✅ "rigid cell wall material, like a straw's walls"
  - ❌ "heuristics" → ✅ "rules of thumb"
  - ❌ "translocation" → ✅ "two-way transport"
"""
    elif grade_level == "high_school":
        terminology_instruction = """
**Terminology Simplification (MANDATORY for high school):**
- Replace graduate-level jargon with high school vocabulary
- Examples:
  - ❌ "marginal gain" → ✅ "extra benefit" or "additional gain"
  - ❌ "tangent line" → ✅ "flat line at the peak" or "horizontal at the top"
  - ❌ "kinematic formula" → ✅ "motion formula" or "equation for movement"
  - ❌ "heuristics" → ✅ "rules of thumb" or "practical shortcuts"
  - ❌ "homoscedasticity" → ✅ "equal variance" or "consistent spread"
  - ❌ "inference engine" → ✅ "reasoning system" or "decision-making logic"
- Keep standard high school terms (e.g., "acceleration", "derivative" are OK)
"""
    else:  # ap_college
        terminology_instruction = """
**Terminology Guidance (AP/College level):**
- Academic terms are acceptable, but add brief definitions on first use
- Example: "marginal gain, which means the extra benefit from one more unit"
- Example: "the tangent line, which is the flat line touching the curve at that point"
"""

    # 概述部分使用带范例引导的特殊提示词
    if _is_overview_screen_text(screen_text):
        prompt = f"""{_OVERVIEW_EXPANSION_EXAMPLES}{screen_text}""".strip()
    else:
        prompt = f"""
You are a teaching video narration polisher.

Task:
- Expand the screen text below into a more natural, conversational, single-sentence narration suitable for TTS playback
- Must preserve the original meaning, don't introduce new knowledge points
- Must be "minimal incremental expansion", don't write long paragraphs
- Output must be a single line of plain text only, no quotes, numbering, or explanations
- Do not include any labels, prefixes, or metadata (like 'spoken_script:', 'output:', 'narration:', etc.)
- Output spoken_script must be in English

{terminology_instruction}

Screen text:
{screen_text}
""".strip()

    def _request():
        response = api_func(prompt, max_tokens=max_tokens)
        spoken_script = extract_response_text(response)
        if not spoken_script:
            raise ValueError("empty spoken_script")

        # Clean up any label prefixes that LLM might have added
        import re
        spoken_script = re.sub(r'^(spoken_script|output|narration)\s*[:：]\s*', '', spoken_script, flags=re.IGNORECASE)
        spoken_script = re.sub(r'^(spoken_script|output|narration)\s+', '', spoken_script, flags=re.IGNORECASE)
        spoken_script = spoken_script.strip()

        if not spoken_script:
            raise ValueError("empty spoken_script after cleanup")

        return spoken_script

    return retry_with_backoff(
        operation_name=f"spoken script expansion for '{screen_text}'",
        func=_request,
        max_retries=max_retries,
        base_delay=0.5,
    )


def get_tts_endpoint_config() -> tuple[str, str, str, str]:
    api_key = os.getenv("TTS_API_KEY") or os.getenv("OPENAI_API_KEY") or cfg("gpt5", "api_key")
    base_url = os.getenv("TTS_BASE_URL") or cfg("gpt5", "base_url") or DEFAULT_TTS_BASE_URL
    # 不再从环境变量读取model，而是在synthesize_tts_audio中动态选择
    voice = os.getenv("TTS_VOICE") or DEFAULT_TTS_VOICE

    if not api_key:
        raise ValueError("Missing TTS API key. Set TTS_API_KEY or OPENAI_API_KEY or config api_key.")
    if not base_url:
        raise ValueError("Missing TTS base URL. Set TTS_BASE_URL or configure gpt5.base_url.")

    return api_key, base_url.rstrip("/"), voice


def synthesize_tts_audio(
    text: str,
    output_path: Path,
    max_retries: int = 5,
    timeout: int = 120,
    model_index: int = 0,  # 新增：用于选择TTS模型
) -> Path:
    output_path = Path(output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    api_key, base_url, voice = get_tts_endpoint_config()
    # 根据model_index选择模型
    model = TTS_MODELS[model_index % len(TTS_MODELS)]
    endpoint = f"{base_url}/audio/speech"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload_candidates = [
        {
            "model": model,
            "voice": voice,
            "input": text,
            "response_format": "wav",
        },
        {
            "model": model,
            "voice": voice,
            "input": text,
        },
        {
            "model": model,
            "input": text,
            "response_format": "wav",
        },
        {
            "model": model,
            "input": text,
        },
    ]

    def _request():
        last_error = None
        for payload in payload_candidates:
            response = requests.post(endpoint, headers=headers, json=payload, timeout=timeout)
            if response.status_code < 400:
                if not response.content:
                    raise RuntimeError("TTS returned empty audio payload")

                content_type = (response.headers.get("Content-Type") or "").lower()
                audio_bytes = response.content

                if "application/json" in content_type or audio_bytes[:1] in (b"{", b"["):
                    raise RuntimeError(f"TTS returned JSON payload instead of audio: {audio_bytes[:400]!r}")

                resolved_path = resolve_audio_output_path(output_path, content_type, audio_bytes)
                resolved_path.write_bytes(audio_bytes)
                normalized_path = normalize_audio_for_manim(resolved_path, output_path.with_suffix(".wav"))
                if resolved_path != normalized_path and resolved_path.exists():
                    resolved_path.unlink()
                return normalized_path

            error_text = response.text[:400]
            last_error = RuntimeError(
                f"TTS HTTP {response.status_code} with payload keys {sorted(payload.keys())}: {error_text}"
            )

            # 仅对显式参数不兼容做 payload 级降级；鉴权/路径类错误直接抛出
            if response.status_code in (401, 403, 404):
                raise last_error
            if response.status_code in (400, 500):
                continue

            raise last_error

        raise last_error or RuntimeError("TTS request failed with unknown error")

    return retry_with_backoff(
        operation_name=f"TTS synthesis for {output_path.name}",
        func=_request,
        max_retries=max_retries,
        base_delay=1.0,
    )


def measure_audio_duration(audio_path: Path) -> float:
    audio_path = Path(audio_path).resolve()
    if audio_path.suffix.lower() == ".wav":
        with wave.open(str(audio_path), "rb") as wav_file:
            frame_rate = wav_file.getframerate()
            frame_count = wav_file.getnframes()
            if frame_rate <= 0:
                raise ValueError(f"Invalid frame rate in {audio_path}")
            return frame_count / float(frame_rate)

    audio = AudioSegment.from_file(audio_path)
    return len(audio) / 1000.0


def normalize_audio_for_manim(source_path: Path, target_path: Path) -> Path:
    source_path = Path(source_path).resolve()
    target_path = Path(target_path).resolve()

    audio = AudioSegment.from_file(source_path)
    if len(audio) < 250:
        raise RuntimeError(f"TTS audio is too short to be valid: {source_path} ({len(audio)} ms)")
    if audio.rms == 0:
        raise RuntimeError(f"TTS audio is silent: {source_path}")

    normalized = audio.set_frame_rate(48000).set_channels(2).set_sample_width(2)
    normalized.export(target_path, format="wav")
    return target_path


def resolve_audio_output_path(output_path: Path, content_type: str, audio_bytes: bytes) -> Path:
    output_path = Path(output_path).resolve()

    if audio_bytes.startswith(b"RIFF") and audio_bytes[8:12] == b"WAVE":
        return output_path.with_suffix(".wav")

    if audio_bytes.startswith(b"ID3") or audio_bytes[:2] in {b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"}:
        return output_path.with_suffix(".mp3")

    if audio_bytes.startswith(b"OggS") or "ogg" in content_type:
        return output_path.with_suffix(".ogg")

    if "mpeg" in content_type or "mp3" in content_type:
        return output_path.with_suffix(".mp3")

    if "wav" in content_type or "wave" in content_type:
        return output_path.with_suffix(".wav")

    raise RuntimeError(
        f"Unsupported TTS audio format. content_type={content_type!r}, first_bytes={audio_bytes[:16]!r}"
    )


def reset_section_audio_dir(section_audio_dir: Path) -> Path:
    section_audio_dir = Path(section_audio_dir).resolve()
    if section_audio_dir.exists():
        shutil.rmtree(section_audio_dir)
    section_audio_dir.mkdir(parents=True, exist_ok=True)
    return section_audio_dir


def _paginate_highlight_groups(section, highlight_groups: List[List[int]], page_max_lines: int = LECTURE_PAGE_MAX_LINES) -> List[List[dict]]:
    pages: List[List[dict]] = []
    current_page: List[dict] = []
    current_line_count = 0

    for highlight_indices in highlight_groups:
        group_line_count = len(highlight_indices)
        if current_page and current_line_count + group_line_count > page_max_lines:
            pages.append(current_page)
            current_page = []
            current_line_count = 0

        current_page.append({
            "highlight_indices": list(highlight_indices),
            "screen_texts": [section.lecture_lines[line_index] for line_index in highlight_indices],
            "line_count": group_line_count,
        })
        current_line_count += group_line_count

    if current_page:
        pages.append(current_page)

    return pages


def build_section_steps(
    section,
    output_root: Path,
    api_func: Callable,
    expansion_max_retries: int = 3,
    tts_max_retries: int = 5,
    user_profile: Optional['UserProfile'] = None,
) -> List[dict]:
    output_root = Path(output_root).resolve()
    audio_dir = reset_section_audio_dir(output_root / "audio" / section.id)
    section_steps = []
    highlight_groups = getattr(section, "highlight_groups", None) or [[index] for index in range(len(section.lecture_lines))]

    if getattr(section, "id", "") == "section_overview":
        spoken_script = build_overview_spoken_script(
            getattr(section, "title", ""),
            section.lecture_lines,
            api_func,
            expansion_max_retries,
            300,
        )
        intro_script, roadmap_script = _split_overview_spoken_script(spoken_script, getattr(section, "title", ""))

        intro_audio_path = synthesize_tts_audio(
            intro_script,
            audio_dir / "step_00.wav",
            max_retries=tts_max_retries,
            timeout=120,
            model_index=0,
        )
        roadmap_audio_path = synthesize_tts_audio(
            roadmap_script,
            audio_dir / "step_01.wav",
            max_retries=tts_max_retries,
            timeout=120,
            model_index=1,
        )

        intro_audio_duration = measure_audio_duration(intro_audio_path)
        roadmap_audio_duration = measure_audio_duration(roadmap_audio_path)
        cue_timings = build_overview_cue_timings(section.lecture_lines, roadmap_audio_duration)
        section_steps.append(
            {
                "screen_text": intro_script,
                "screen_texts": [intro_script],
                "spoken_script": intro_script,
                "audio_path": str(intro_audio_path.resolve()),
                "audio_duration": intro_audio_duration,
                "highlight_indices": [0],
                "page_index": 0,
                "page_line_indices": [0],
                "page_screen_texts": [intro_script],
                "step_index_within_page": 0,
                "segment_type": "intro",
                "cue_timings": [],
            }
        )
        section_steps.append(
            {
                "screen_text": "\n".join(section.lecture_lines),
                "screen_texts": list(section.lecture_lines),
                "spoken_script": roadmap_script,
                "audio_path": str(roadmap_audio_path.resolve()),
                "audio_duration": roadmap_audio_duration,
                "highlight_indices": list(range(len(section.lecture_lines))),
                "page_index": 0,
                "page_line_indices": list(range(len(section.lecture_lines))),
                "page_screen_texts": list(section.lecture_lines),
                "step_index_within_page": 1,
                "segment_type": "roadmap",
                "cue_timings": cue_timings,
            }
        )
        return section_steps

    paged_groups = _paginate_highlight_groups(section, highlight_groups)

    # 批量扩展短句以减少 API 调用
    batch_expansions = []
    for page_index, page_groups in enumerate(paged_groups):
        page_line_indices = [
            line_index
            for page_group in page_groups
            for line_index in page_group["highlight_indices"]
        ]
        page_screen_texts = [section.lecture_lines[line_index] for line_index in page_line_indices]

        for index_within_page, page_group in enumerate(page_groups):
            screen_texts = list(page_group["screen_texts"])
            combined_screen_text = " ".join(screen_texts)
            batch_expansions.append(
                {
                    "page_index": page_index,
                    "page_line_indices": page_line_indices,
                    "page_screen_texts": page_screen_texts,
                    "step_index_within_page": index_within_page,
                    "highlight_indices": list(page_group["highlight_indices"]),
                    "screen_texts": screen_texts,
                    "combined_screen_text": combined_screen_text,
                }
            )

    # 并行调用 LLM 扩展（可通过环境变量 LLM_EXPANSION_MAX_WORKERS 调整）
    spoken_scripts = [None] * len(batch_expansions)
    with ThreadPoolExecutor(max_workers=LLM_EXPANSION_MAX_WORKERS) as executor:
        future_to_index = {
            executor.submit(
                expand_screen_text_to_spoken_script,
                batch_expansion["combined_screen_text"],
                api_func,
                expansion_max_retries,
                300,  # max_tokens
                user_profile,
            ): index
            for index, batch_expansion in enumerate(batch_expansions)
        }
        for future in as_completed(future_to_index):
            index = future_to_index[future]
            spoken_scripts[index] = future.result()

    # 注入过渡句（仅在语音中念出，不出现在画面文本中）
    if len(spoken_scripts) > 0:
        intro_transition = getattr(section, "intro_transition_spoken", None)
        if intro_transition:
            spoken_scripts[0] = f"{intro_transition} {spoken_scripts[0]}"
            
        outro_transition = getattr(section, "outro_transition_spoken", None)
        if outro_transition:
            spoken_scripts[-1] = f"{spoken_scripts[-1]} {outro_transition}"

    # 并行生成 TTS 音频 - 使用两个模型负载均衡，每个模型4个并发
    audio_results = [None] * len(batch_expansions)

    # 将任务分配给两个模型
    model_0_tasks = []  # tts-1-hd
    model_1_tasks = []  # tts-1-hd-1106

    for index, spoken_script in enumerate(spoken_scripts):
        task = (index, spoken_script, audio_dir / f"step_{index:02d}.wav", tts_max_retries)
        if index % 2 == 0:
            model_0_tasks.append(task)
        else:
            model_1_tasks.append(task)

    # 为每个模型创建独立的线程池，各自4个并发
    from concurrent.futures import ThreadPoolExecutor as TPE

    def process_model_tasks(tasks, model_index):
        results = {}
        with TPE(max_workers=TTS_MODEL_MAX_WORKERS) as executor:
            future_to_index = {
                executor.submit(
                    synthesize_tts_audio,
                    spoken_script,
                    output_path,
                    max_retries,
                    120,  # timeout
                    model_index
                ): idx
                for idx, spoken_script, output_path, max_retries in tasks
            }
            for future in as_completed(future_to_index):
                idx = future_to_index[future]
                results[idx] = future.result()
        return results

    # 并行处理两个模型的任务
    with TPE(max_workers=2) as model_executor:
        model_0_future = model_executor.submit(process_model_tasks, model_0_tasks, 0)
        model_1_future = model_executor.submit(process_model_tasks, model_1_tasks, 1)

        model_0_results = model_0_future.result()
        model_1_results = model_1_future.result()

    # 合并结果
    audio_results = [None] * len(batch_expansions)
    for idx, path in model_0_results.items():
        audio_results[idx] = path
    for idx, path in model_1_results.items():
        audio_results[idx] = path

    # 构建 section_steps
    for (batch_expansion, spoken_script, audio_path) in zip(batch_expansions, spoken_scripts, audio_results):
        audio_duration = measure_audio_duration(audio_path)
        section_steps.append(
            {
                "screen_text": batch_expansion["screen_texts"][0] if len(batch_expansion["screen_texts"]) == 1 else "\n".join(batch_expansion["screen_texts"]),
                "screen_texts": list(batch_expansion["screen_texts"]),
                "spoken_script": spoken_script,
                "audio_path": str(audio_path.resolve()),
                "audio_duration": audio_duration,
                "highlight_indices": list(batch_expansion["highlight_indices"]),
                "page_index": batch_expansion["page_index"],
                "page_line_indices": list(batch_expansion["page_line_indices"]),
                "page_screen_texts": list(batch_expansion["page_screen_texts"]),
                "step_index_within_page": batch_expansion["step_index_within_page"],
            }
        )

    return section_steps


def save_section_steps(section_steps: List[dict], output_path: Path) -> Path:
    output_path = Path(output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(section_steps, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def _extract_constant_number(node) -> float | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        value = _extract_constant_number(node.operand)
        if value is not None:
            return -value
    return None


def _extract_step_index_from_call(call: ast.Call) -> int | None:
    if len(call.args) < 2:
        return None

    candidate = call.args[1]
    if not isinstance(candidate, ast.Subscript):
        return None

    value = candidate.value
    if not isinstance(value, ast.Subscript):
        return None
    if not isinstance(value.value, ast.Name) or value.value.id != "steps":
        return None

    step_index = _extract_constant_number(value.slice)
    if step_index is None:
        return None

    return int(step_index)


def _extract_step_index_from_subscript_arg(call: ast.Call, arg_index: int = 0) -> int | None:
    """
    从 steps[N]["audio_path"] 或 steps[N]["audio_duration"] 形式的参数中提取步骤索引 N。

    用于解析 add_sound(steps[0]["audio_path"]) 和 wait(steps[0]["audio_duration"]) 等调用。
    """
    if len(call.args) <= arg_index:
        return None

    candidate = call.args[arg_index]
    if not isinstance(candidate, ast.Subscript):
        return None

    # candidate 可能是 steps[N]["key"] 形式（双层下标）
    inner = candidate.value
    if isinstance(inner, ast.Subscript):
        # steps[N]["key"] → inner.value 是 steps, inner.slice 是 N
        if not isinstance(inner.value, ast.Name) or inner.value.id != "steps":
            return None
        step_index = _extract_constant_number(inner.slice)
        if step_index is not None:
            return int(step_index)
    elif isinstance(candidate.value, ast.Name) and candidate.value.id == "steps":
        # steps[N] 形式（单层下标）
        step_index = _extract_constant_number(candidate.slice)
        if step_index is not None:
            return int(step_index)

    return None


def _timeline_events_from_statements(statements, step_count: int, events: list[tuple[str, float]]):
    for stmt in statements:
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call) and isinstance(stmt.value.func, ast.Attribute):
            call = stmt.value
            attr = call.func.attr

            if attr == "play_synced_step":
                step_index = _extract_step_index_from_call(call)
                if step_index is None or not (0 <= step_index < step_count):
                    raise ValueError("Unable to resolve step index from play_synced_step call")
                events.append(("audio", float(step_index)))
                continue

            if attr == "add_sound":
                # 识别 self.add_sound(steps[N]["audio_path"]) 模式
                step_index = _extract_step_index_from_subscript_arg(call, arg_index=0)
                if step_index is not None and 0 <= step_index < step_count:
                    events.append(("audio", float(step_index)))
                continue

            if attr == "wait":
                if call.args:
                    # 先尝试常量数字
                    wait_duration = _extract_constant_number(call.args[0])
                    if wait_duration is not None and wait_duration > 0:
                        events.append(("silence", wait_duration))
                    else:
                        # 尝试识别 steps[N]["audio_duration"] 形式（封面模板使用）
                        step_index = _extract_step_index_from_subscript_arg(call, arg_index=0)
                        if step_index is not None and 0 <= step_index < step_count:
                            # wait 的时长等于该 step 的音频时长，但此处我们不重复
                            # 插入音频（add_sound 已处理），只需静音占位即可跳过
                            pass
                continue

            if attr == "play":
                run_time = 1.0
                for keyword in call.keywords:
                    if keyword.arg == "run_time":
                        constant = _extract_constant_number(keyword.value)
                        if constant is not None and constant > 0:
                            run_time = constant
                        break
                if run_time > 0:
                    events.append(("silence", run_time))
                continue

            if attr == "replace_lecture_lines":
                events.append(("silence", 1.0))
                continue

        if isinstance(stmt, ast.If):
            # Support the simple `if len(steps) > N:` pattern used by prompt few-shot examples.
            condition_is_true = False
            test = stmt.test
            if (
                isinstance(test, ast.Compare)
                and len(test.ops) == 1
                and isinstance(test.ops[0], ast.Gt)
                and isinstance(test.left, ast.Call)
                and isinstance(test.left.func, ast.Name)
                and test.left.func.id == "len"
                and len(test.left.args) == 1
                and isinstance(test.left.args[0], ast.Name)
                and test.left.args[0].id == "steps"
                and len(test.comparators) == 1
            ):
                threshold = _extract_constant_number(test.comparators[0])
                if threshold is not None:
                    condition_is_true = step_count > threshold
            # Support the simple `if steps:` truthiness check used by cover template.
            elif isinstance(test, ast.Name) and test.id == "steps":
                condition_is_true = step_count > 0

            branch = stmt.body if condition_is_true else stmt.orelse
            _timeline_events_from_statements(branch, step_count, events)


def _format_srt_timestamp(seconds: float) -> str:
    total_milliseconds = max(0, int(round(seconds * 1000)))
    hours, remainder = divmod(total_milliseconds, 3600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, milliseconds = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"


def build_section_subtitles(section_steps: List[dict], code_path: Path, start_offset: float = 0.0) -> List[dict]:
    code_path = Path(code_path).resolve()
    tree = ast.parse(code_path.read_text(encoding="utf-8"))
    construct_func = None
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name != "TeachingScene":
            for child in node.body:
                if isinstance(child, ast.FunctionDef) and child.name == "construct":
                    construct_func = child
                    break
        if construct_func is not None:
            break

    if construct_func is None:
        raise ValueError(f"No construct() method found in {code_path}")

    events: list[tuple[str, float]] = []
    _timeline_events_from_statements(construct_func.body, len(section_steps), events)

    subtitles: List[dict] = []
    current_time = float(start_offset)
    for event_type, payload in events:
        if event_type == "audio":
            step = section_steps[int(payload)]
            duration = float(step.get("audio_duration", 0) or 0)
            subtitles.append(
                {
                    "start": current_time,
                    "end": current_time + duration,
                    "text": step.get("spoken_script") or step.get("screen_text") or "",
                }
            )
            current_time += duration
        elif event_type == "silence":
            current_time += float(payload)

    return subtitles


def subtitles_to_srt(subtitles: List[dict]) -> str:
    blocks = []
    for index, item in enumerate(subtitles, start=1):
        text = (item.get("text") or "").strip()
        if not text:
            continue
        blocks.append(
            f"{index}\n{_format_srt_timestamp(item['start'])} --> {_format_srt_timestamp(item['end'])}\n{text}"
        )
    return "\n\n".join(blocks) + ("\n" if blocks else "")


def save_srt(subtitles: List[dict], output_path: Path) -> Path:
    output_path = Path(output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(subtitles_to_srt(subtitles), encoding="utf-8")
    return output_path


def build_section_narration_track(section_steps: List[dict], code_path: Path, output_path: Path) -> Path:
    code_path = Path(code_path).resolve()
    output_path = Path(output_path).resolve()

    tree = ast.parse(code_path.read_text(encoding="utf-8"))
    construct_func = None
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name != "TeachingScene":
            for child in node.body:
                if isinstance(child, ast.FunctionDef) and child.name == "construct":
                    construct_func = child
                    break
        if construct_func is not None:
            break

    if construct_func is None:
        raise ValueError(f"No construct() method found in {code_path}")

    events: list[tuple[str, float]] = []
    _timeline_events_from_statements(construct_func.body, len(section_steps), events)

    audio_track = AudioSegment.silent(duration=0, frame_rate=48000)
    for event_type, payload in events:
        if event_type == "audio":
            step = section_steps[int(payload)]
            segment = AudioSegment.from_file(step["audio_path"])
            audio_track += segment
        elif event_type == "silence":
            audio_track += AudioSegment.silent(duration=int(round(payload * 1000)), frame_rate=48000)

    normalized = audio_track.set_frame_rate(48000).set_channels(2).set_sample_width(2)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    normalized.export(output_path, format="wav")
    return output_path


def remux_video_with_audio(video_path: Path, audio_path: Path, output_path: Path) -> Path:
    video_path = Path(video_path).resolve()
    audio_path = Path(audio_path).resolve()
    output_path = Path(output_path).resolve()

    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    result = subprocess.run(
        [
            ffmpeg_exe,
            "-y",
            "-i",
            str(video_path),
            "-i",
            str(audio_path),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-shortest",
            str(output_path),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 or not output_path.exists():
        raise RuntimeError(f"Failed to remux audio into video: {video_path}: {result.stderr}")
    return output_path
