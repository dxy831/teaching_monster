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
from typing import Callable, List
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from pydub import AudioSegment
import imageio_ffmpeg

from src.gpt_request import cfg


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TTS_BASE_URL = "https://vip.dmxapi.com/v1"
DEFAULT_TTS_MODEL = "tts-1-hd"
DEFAULT_TTS_VOICE = "alloy"


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
You are a teaching video narration polisher, currently processing the "course overview/table of contents" section narration.

Task:
- Expand the screen text below into a more natural, conversational, single-sentence narration suitable for TTS playback
- Must sound as natural and fluent as an experienced teacher introducing the course outline in class
- Don't start every sentence with "next" or "now"; vary the transition phrasing
- Avoid repetitive openings such as "Now we move into..." or "Now let's move on to..."
- Preserve the original meaning; do not introduce new knowledge points
- Must be "minimal incremental expansion", with a concise teacher-speech style
- Output must be a single line of plain text only, no quotes, numbering, or explanations
- Do not include any labels, prefixes, or metadata (like 'spoken_script:', 'output:', 'narration:', etc.)
- Output spoken_script must be in English

Reference examples (screen text → excellent narration):
- "This video will be divided into the following parts" → "Before we officially begin, let's take a look at the overall structure of this lesson"
- "Part 1, Basic Concepts" → "First, we'll start with the basic concepts to help everyone build a solid foundation"
- "Part 2, Core Principles" → "Building on that, in part 2 we'll dive deeper into the core principles"
- "Part 3, Code Implementation" → "After understanding the principles, in part 3 we'll get hands-on with the code"
- "Part 4, Practical Case Study" → "From there, we'll explore a practical case study in part 4"
- "Part 5, Performance Optimization" → "Then, in part 5 we'll discuss performance optimization techniques"
- "Part 6, Common Issues" → "Finally, we'll summarize some common issues and important considerations"
- "the fourth part, Energy Payoff Phase" → "From there, we'll examine the Energy Payoff Phase in the fourth part"
- "the fifth part, Energy Accounting Summary" → "Next, the fifth part gives us a clear accounting summary of the energy flows"
- "Alright, let's officially begin learning the specific content" → "Okay, now that we understand the course structure, let's move into the first part"

Screen text:
"""


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
) -> str:
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
    model = os.getenv("TTS_MODEL") or DEFAULT_TTS_MODEL
    voice = os.getenv("TTS_VOICE") or DEFAULT_TTS_VOICE

    if not api_key:
        raise ValueError("Missing TTS API key. Set TTS_API_KEY or OPENAI_API_KEY or config api_key.")
    if not base_url:
        raise ValueError("Missing TTS base URL. Set TTS_BASE_URL or configure gpt5.base_url.")

    return api_key, base_url.rstrip("/"), model, voice


def synthesize_tts_audio(
    text: str,
    output_path: Path,
    max_retries: int = 5,
    timeout: int = 120,
) -> Path:
    output_path = Path(output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    api_key, base_url, model, voice = get_tts_endpoint_config()
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
            if response.status_code == 400:
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


def build_section_steps(
    section,
    output_root: Path,
    api_func: Callable,
    expansion_max_retries: int = 3,
    tts_max_retries: int = 5,
) -> List[dict]:
    output_root = Path(output_root).resolve()
    audio_dir = reset_section_audio_dir(output_root / "audio" / section.id)
    section_steps = []
    highlight_groups = getattr(section, "highlight_groups", None) or [[index] for index in range(len(section.lecture_lines))]

    # 批量扩展短句以减少 API 调用
    batch_expansions = []
    for index, highlight_indices in enumerate(highlight_groups):
        screen_texts = [section.lecture_lines[line_index] for line_index in highlight_indices]
        combined_screen_text = " ".join(screen_texts)
        batch_expansions.append((index, highlight_indices, screen_texts, combined_screen_text))

    # 并行调用 LLM 扩展
    spoken_scripts = [None] * len(batch_expansions)
    with ThreadPoolExecutor(max_workers=16) as executor:
        future_to_index = {
            executor.submit(
                expand_screen_text_to_spoken_script,
                combined_screen_text,
                api_func,
                expansion_max_retries
            ): index
            for index, (_, _, _, combined_screen_text) in enumerate(batch_expansions)
        }
        for future in as_completed(future_to_index):
            index = future_to_index[future]
            spoken_scripts[index] = future.result()

    # 并行生成 TTS 音频
    audio_results = [None] * len(batch_expansions)
    with ThreadPoolExecutor(max_workers=16) as executor:
        future_to_index = {
            executor.submit(
                synthesize_tts_audio,
                spoken_script,
                audio_dir / f"step_{index:02d}.wav",
                tts_max_retries
            ): index
            for index, spoken_script in enumerate(spoken_scripts)
        }
        for future in as_completed(future_to_index):
            index = future_to_index[future]
            audio_results[index] = future.result()

    # 构建 section_steps
    for (index, highlight_indices, screen_texts, _), spoken_script, audio_path in zip(batch_expansions, spoken_scripts, audio_results):
        audio_duration = measure_audio_duration(audio_path)
        section_steps.append(
            {
                "screen_text": screen_texts[0] if len(screen_texts) == 1 else "\n".join(screen_texts),
                "screen_texts": screen_texts,
                "spoken_script": spoken_script,
                "audio_path": str(audio_path.resolve()),
                "audio_duration": audio_duration,
                "highlight_indices": list(highlight_indices),
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
