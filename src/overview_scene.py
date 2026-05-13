"""
Overview Scene Generator — Video Overview/Course Navigation Template

Generates a deterministic overview section at the beginning of the video to quickly preview what will be covered.

Design philosophy references:
- MIT OCW / University lectures: Display agenda at the beginning
- 3Blue1Brown: Brief journey preview
- Educational psychology "Advance Organizer" theory

This module does not rely on LLM to generate Manim code, but uses deterministic templates to ensure 100% success rate.
Narration text still goes through the normal TTS pipeline (expand → TTS → physical timing).

Section titles merging and simplification is done by AI (_merge_section_titles_with_ai),
ensuring the overview is concise and effective, with a maximum of 6 items per page.
"""

from __future__ import annotations

import json
import math
import re
import textwrap
from typing import Callable, List, Optional


# ── Constants ─────────────────────────────────────────────────────
BULLETS_PER_PAGE = 6  # Maximum number of sections displayed per page

# ── Circled number character mapping ────────────────────────────────────────────
_CIRCLED_NUMBERS = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"

# ── English ordinal word mapping ──────────────────────────────────────────
_ORDINAL_WORDS = [
    "first", "second", "third", "fourth", "fifth",
    "sixth", "seventh", "eighth", "ninth", "tenth",
    "eleventh", "twelfth", "thirteenth", "fourteenth", "fifteenth",
    "sixteenth", "seventeenth", "eighteenth", "nineteenth", "twentieth",
]

# ── Overview intro/ending line constants ─────────────────────────────────
OVERVIEW_INTRO_LINE = "Today\'s roadmap"
OVERVIEW_ENDING_LINE = "Let\'s begin"
OVERVIEW_INTRO_DELAY = 1.0


def _circled(n: int) -> str:
    """Returns ①②③… format numbering, falls back to (n) if out of range."""
    if 1 <= n <= len(_CIRCLED_NUMBERS):
        return _CIRCLED_NUMBERS[n - 1]
    return f"({n})"


def _ordinal(n: int) -> str:
    """Returns 'first', 'second'… format ordinal words, falls back to 'Nth' if out of range."""
    if 1 <= n <= len(_ORDINAL_WORDS):
        return _ORDINAL_WORDS[n - 1]
    return f"{n}th"


# ── AI merge section titles ──────────────────────────────────


def _merge_section_titles_with_ai(
    section_titles: List[str],
    topic: str,
    api_func: Callable,
    max_retries: int = 3,
) -> List[str]:
    """
    Use AI to compress detailed section titles into a high-level learning path for the overview.

    Args:
        section_titles: Original list of all section titles
        topic: Video topic (used to filter entries that duplicate the topic)
        api_func: API call function
        max_retries: Maximum number of retries

    Returns:
        High-level overview path items (3-6 items)
    """
    titles_json = json.dumps(section_titles, ensure_ascii=False)

    prompt = f"""You are a teaching video structure editor.

Task: Turn the following list of section titles into a concise high-level learning path for the overview page of an educational video.

Rules:
1. Do NOT produce a table of contents that simply mirrors every section.
2. Summarize the section titles into 3 to 6 high-level path items.
3. Each item should sound like a learning step or idea transition, not a raw chapter label.
4. Emphasize causal progression whenever possible: problem → first idea → limitation → improved idea → takeaway.
5. Keep each item within 10 English words when possible.
6. Do not introduce topic-specific claims that are absent from the section titles.
7. If a title is identical or highly repetitive with the video topic \"{topic}\", do not repeat it as a path item.
8. Remove original numbering, output title text directly.
9. Output format: JSON string array, e.g. [\"Start from the core problem\", \"See why the first idea helps\", ...]

Section title list:
{titles_json}

Please output the JSON array directly without any other text:"""

    for attempt in range(1, max_retries + 1):
        try:
            response = api_func(prompt, max_tokens=500)
            # Extract text
            try:
                content = response.candidates[0].content.parts[0].text
            except Exception:
                try:
                    content = response.choices[0].message.content
                except Exception:
                    content = str(response)

            content = content.strip()
            # Remove possible markdown code block wrapper
            if content.startswith("```"):
                content = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", content)
                content = re.sub(r"\s*```$", "", content)
            content = content.strip()

            merged = json.loads(content)
            if isinstance(merged, list) and len(merged) >= 3:
                return [str(t) for t in merged]
        except Exception as e:
            print(f"⚠️ AI merge section titles attempt {attempt} failed: {e}")
            if attempt >= max_retries:
                break

    # Fallback: simple rule-based merging
    return _merge_section_titles_fallback(section_titles, topic)


def _merge_section_titles_fallback(
    section_titles: List[str],
    topic: str,
) -> List[str]:
    """
    Rule-based fallback: merge titles with consecutive identical prefixes.

    Merge logic:
    - Extract prefix before colon/parenthesis, merge consecutive entries with the same prefix into one
    - Skip entries that duplicate the topic
    """
    import re as _re

    def _get_prefix(title: str) -> str:
        # Take the part before the colon as prefix
        for sep in ["：", ":"]:
            if sep in title:
                prefix = title.split(sep)[0]
                # Remove parenthetical content
                prefix = _re.sub(r"[（(][^）)]*[）)]", "", prefix).strip()
                return prefix
        return title.strip()

    merged = []
    prev_prefix = None

    for title in section_titles:
        # Skip entries that duplicate the topic
        if title.strip() == topic.strip():
            continue

        prefix = _get_prefix(title)
        if prefix == prev_prefix and merged:
            # Same prefix, skip (already have it)
            continue
        else:
            # Use simplified prefix as title
            if prefix != title:
                merged.append(prefix)
            else:
                merged.append(title)
            prev_prefix = prefix

    return merged if merged else section_titles


# ── Extract overview data from outline ──────────────────────────────────────


def build_overview_lecture_lines(
    section_titles: List[str],
    user_profile_summary: Optional[dict] = None,
) -> List[str]:
    """
    Generate overview lecture_lines as short roadmap phrases.

    Strategy:
    - Return only roadmap phrases for on-screen display
    - Spoken-only opener / closer are generated later in the TTS layer

    Args:
        section_titles: Merged and simplified high-level path items
        user_profile_summary: Optional learner summary for tone adjustment

    Returns:
        List[str] — short phrases suitable for Section.lecture_lines
    """
    _ = user_profile_summary
    return [title.strip() for title in section_titles if title and title.strip()]


def _validate_overview_section_steps(section_titles: List[str], section_steps: List[dict]) -> None:
    if len(section_steps) != 2:
        raise ValueError(f"overview steps count mismatch: got {len(section_steps)}, expected 2")

    intro_step = section_steps[0]
    roadmap_step = section_steps[1]
    if not isinstance(intro_step, dict):
        raise ValueError("overview step 0 is not a dict")
    if not isinstance(roadmap_step, dict):
        raise ValueError("overview step 1 is not a dict")

    intro_audio_path = intro_step.get("audio_path")
    if not isinstance(intro_audio_path, str) or not intro_audio_path.strip():
        raise ValueError(f"overview step 0 has invalid audio_path: {intro_audio_path!r}")

    intro_audio_duration = intro_step.get("audio_duration")
    if not isinstance(intro_audio_duration, (int, float)) or not math.isfinite(intro_audio_duration) or intro_audio_duration <= 0:
        raise ValueError(f"overview step 0 has invalid audio_duration: {intro_audio_duration!r}")

    roadmap_audio_path = roadmap_step.get("audio_path")
    if not isinstance(roadmap_audio_path, str) or not roadmap_audio_path.strip():
        raise ValueError(f"overview step 1 has invalid audio_path: {roadmap_audio_path!r}")

    roadmap_audio_duration = roadmap_step.get("audio_duration")
    if not isinstance(roadmap_audio_duration, (int, float)) or not math.isfinite(roadmap_audio_duration) or roadmap_audio_duration <= 0:
        raise ValueError(f"overview step 1 has invalid audio_duration: {roadmap_audio_duration!r}")

    cue_timings = roadmap_step.get("cue_timings")
    if not isinstance(cue_timings, list) or len(cue_timings) != len(section_titles):
        raise ValueError(
            f"overview cue timings mismatch: got {len(cue_timings) if isinstance(cue_timings, list) else cue_timings!r}, expected {len(section_titles)}"
        )


# ── Generate deterministic Manim code ───────────────────────────────────


def generate_overview_manim_code(
    section_titles: List[str],
    section_steps: List[dict],
    page_title_text: str,
) -> str:
    """
    Generate complete Manim code for the overview section (deterministic template, no LLM dependency).

    Visual design:
    1. Display the actual lesson topic as the main title and a lightweight overview subtitle
    2. Play one continuous overview narration for the whole roadmap
    3. Fade in each overview path item in order, always at or before its corresponding narration segment
       - Screen uses ① ② ③ circled number format
       - If sections exceed BULLETS_PER_PAGE, automatically paginate

    Args:
        section_titles: Merged high-level overview path items
        section_steps: Built overview section_steps; index 0 contains the combined audio and cue timings
        page_title_text: Main title shown at the top of the overview page

    Returns:
        Complete Python/Manim code string
    """
    _validate_overview_section_steps(section_titles, section_steps)

    all_bullet_texts = []
    for idx, title in enumerate(section_titles, start=1):
        all_bullet_texts.append(f"{_circled(idx)} {title}")

    intro_step = section_steps[0]
    roadmap_step = section_steps[1]
    cue_timings = roadmap_step["cue_timings"]
    num_bullets = len(all_bullet_texts)

    pages: List[List[int]] = []
    for start in range(0, num_bullets, BULLETS_PER_PAGE):
        end = min(start + BULLETS_PER_PAGE, num_bullets)
        pages.append(list(range(start, end)))

    num_pages = len(pages)
    if num_pages == 0:
        raise ValueError("overview requires at least one section title")

    bullet_creation_lines = []
    for i, bt in enumerate(all_bullet_texts):
        safe_bt = bt.replace('"', '\\"').replace("'", "\\'")
        bullet_creation_lines.append(
            f'        bullet_{i} = Text("{safe_bt}", font_size=22, color="#2C1608")'
        )
    bullet_creation_code = "\n".join(bullet_creation_lines)

    page_setup_blocks = []
    reveal_blocks = []
    previous_cue_for_wait = 0.0
    for page_idx, page_bullet_indices in enumerate(pages):
        page_bullet_names = [f"bullet_{i}" for i in page_bullet_indices]
        setup_lines = []
        if page_idx == 0:
            setup_lines.append(f"        # ── Page {page_idx + 1} (of {num_pages}) ──")
        else:
            setup_lines.append(f"\n        # ── Page {page_idx + 1} (of {num_pages}) ──")
            previous_page_bullets = ", ".join(f"bullet_{i}" for i in pages[page_idx - 1])
            setup_lines.append(f"        self.play(FadeOut(VGroup({previous_page_bullets})), run_time=0.25)")
        setup_lines.append(
            f"        bullets = VGroup({', '.join(page_bullet_names)}).arrange(DOWN, center=True, buff=0.35)"
        )
        setup_lines.append("        bullets.next_to(underline, DOWN, buff=0.5)")
        setup_lines.append("        if bullets.get_bottom()[1] < -3.5:")
        setup_lines.append("            bullets.scale_to_fit_height(5.0)")
        setup_lines.append("            bullets.next_to(underline, DOWN, buff=0.5)")
        setup_lines.append("        self.lecture = bullets")
        setup_lines.append(f"        self.current_lecture_line_indices = {page_bullet_indices}")
        page_setup_blocks.append("\n".join(setup_lines))

        for local_idx, bullet_global_idx in enumerate(page_bullet_indices):
            cue_time = float(cue_timings[bullet_global_idx])
            wait_before = max(cue_time - previous_cue_for_wait, 0.0)
            reveal_lines = []
            reveal_lines.append(f"\n        # Bullet {bullet_global_idx + 1}")
            if wait_before > 0:
                reveal_lines.append(f"        self.wait({wait_before})")
            reveal_lines.append(f"        self.play(FadeIn(bullet_{bullet_global_idx}, shift=RIGHT * 0.3), run_time=0.2)")
            reveal_blocks.append("\n".join(reveal_lines))
            previous_cue_for_wait = cue_time + 0.2

    page_setup_code = "\n".join(page_setup_blocks)
    reveal_code = "\n".join(reveal_blocks)

    safe_page_title = page_title_text.replace('"', '\\"').replace("'", "\\'")
    intro_wait_after_title = max(float(intro_step["audio_duration"]) - 0.4, 0.0)
    roadmap_audio_duration = float(roadmap_step["audio_duration"])
    roadmap_last_cue = float(cue_timings[-1]) if cue_timings else 0.0
    remaining_roadmap_audio = max(roadmap_audio_duration - roadmap_last_cue - 0.2, 0.0)

    code = f'''from manim import *
import numpy as np

{_get_base_class_import()}

class SectionOverviewScene(TeachingScene):
    def construct(self):
        steps = {json.dumps(section_steps, ensure_ascii=False)}
        intro_step = steps[0]
        roadmap_step = steps[1]

        self.camera.background_color = "#FFFDF4"

        page_title = Text("{safe_page_title}", font_size=28, color="#BE8944", weight="BOLD")
        page_title.to_edge(UP, buff=0.5)

        subtitle = Text("Learning Roadmap", font_size=24, color="#7B4B2A", weight="BOLD")
        subtitle.move_to([0, 2.0, 0])

        underline = Line(
            start=subtitle.get_left() + DOWN * 0.2,
            end=subtitle.get_right() + DOWN * 0.2,
            color="#e4c8a6",
            stroke_width=2,
        )

{bullet_creation_code}

        self.wait({OVERVIEW_INTRO_DELAY})
        self.add_sound(intro_step["audio_path"])
        self.play(FadeIn(page_title), FadeIn(subtitle), FadeIn(underline), run_time=0.4)
        if {intro_wait_after_title} > 0:
            self.wait({intro_wait_after_title})

{page_setup_code}

        self.add_sound(roadmap_step["audio_path"])
{reveal_code}

        if {remaining_roadmap_audio} > 0:
            self.wait({remaining_roadmap_audio})

        self.play(FadeOut(page_title), FadeOut(subtitle), FadeOut(underline), FadeOut(bullets), run_time=0.3)
        self.wait(0.5)
'''

    return code


def _get_base_class_import() -> str:
    """Returns inline definition of base_class (consistent with prompts/base_class.py)."""
    return ""
