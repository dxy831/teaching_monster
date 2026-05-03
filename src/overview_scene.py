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
OVERVIEW_INTRO_LINE = "This video will be divided into the following parts"
OVERVIEW_ENDING_LINE = "Alright, let's now begin with the detailed content"


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
    Use AI to merge and simplify detailed section titles into a concise overview list suitable for display.

    Args:
        section_titles: Original list of all section titles
        topic: Video topic (used to filter entries that duplicate the topic)
        api_func: API call function
        max_retries: Maximum number of retries

    Returns:
        Merged title list (5-12 items)
    """
    titles_json = json.dumps(section_titles, ensure_ascii=False)

    prompt = f"""You are a teaching video outline simplifier.

Task: Merge and simplify the following list of section titles into a concise overview list suitable for a "course navigation" page.

Rules:
1. Merge sections with similar or consecutive content into a single high-level summary
   Example: "Execution Trace (Part 1): xxx" and "Execution Trace (Part 2): yyy" merge into "Execution Trace"
   Example: "Complete Source Code (Part 1)", "Complete Source Code (Part 2)", "Complete Source Code (Part 3)" merge into "Complete Source Code"
2. If the original title has a "prefix - suffix" or "prefix: suffix" structure, prioritize keeping "prefix: key qualifying suffix"
   Example: "Scene Introduction: Starting from game leaderboards, why does linear search frustrate people?" should be kept as "Scene Introduction: Linear Search Dilemma"
   Example: "Core Algorithm Concept - Search Space Reduction" should be kept as "Core Algorithm Concept: Search Space Reduction"
   Example: "Complexity Analysis: Why is it O(log n)?" should be kept as "Complexity Analysis: O(log n)"
3. But if the suffix is only concluding or generalizing in nature, don't force keeping the suffix
   Example: Titles like "Complete Source Code", "Complete Code Review", "Advanced Thinking and Summary Review" should be simplified to more natural high-level titles
4. Keep the final number of items between 5-12
5. Try to keep each item within 8 English words
6. Do not introduce new content, only merge/simplify original titles
7. If a title is identical or highly repetitive with the video topic "{topic}", delete that entry
8. Remove original numbering, output title text directly
9. Output format: JSON string array, e.g. ["Title 1", "Title 2", ...]

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
) -> List[str]:
    """
    Generate overview lecture_lines (narration text short sentences) from merged section titles.

    Strategy:
    - First line: intro line (e.g., "This video will be divided into the following parts")
    - Middle lines: one line per section title, using "the Xth part, title" format
      (for TTS use, let AI expand into natural "the first part...", "the second part..." expressions)
    - Last line: ending line (e.g., "Alright, let's now begin with the detailed content")

    Note: The screen still uses ① ② ③ circled number format for display, the format here only affects narration.

    Args:
        section_titles: Merged and simplified title list

    Returns:
        List[str] — short sentence list suitable for passing to Section.lecture_lines
    """
    lines: List[str] = []

    # Intro line
    lines.append(OVERVIEW_INTRO_LINE)

    # Section list — using "the Xth part, title" format (for TTS expansion)
    for idx, title in enumerate(section_titles, start=1):
        lines.append(f"the {_ordinal(idx)} part, {title}")

    # Ending line
    lines.append(OVERVIEW_ENDING_LINE)

    return lines


def _validate_overview_section_steps(section_titles: List[str], section_steps: List[dict]) -> None:
    expected_steps = len(section_titles) + 2
    if len(section_steps) != expected_steps:
        raise ValueError(f"overview steps count mismatch: got {len(section_steps)}, expected {expected_steps}")

    for idx, step in enumerate(section_steps):
        if not isinstance(step, dict):
            raise ValueError(f"overview step {idx} is not a dict")
        audio_path = step.get("audio_path")
        if not isinstance(audio_path, str) or not audio_path.strip():
            raise ValueError(f"overview step {idx} has invalid audio_path: {audio_path!r}")
        audio_duration = step.get("audio_duration")
        if not isinstance(audio_duration, (int, float)) or not math.isfinite(audio_duration) or audio_duration <= 0:
            raise ValueError(f"overview step {idx} has invalid audio_duration: {audio_duration!r}")


# ── Generate deterministic Manim code ───────────────────────────────────


def generate_overview_manim_code(
    section_titles: List[str],
    section_steps: List[dict],
) -> str:
    """
    Generate complete Manim code for the overview section (deterministic template, no LLM dependency).

    Visual design:
    1. Display "Course Navigation" title + "Content Overview" subtitle, while playing intro narration (step_0)
    2. FadeIn each section title one by one (with play_synced_step narration)
       - Screen uses ① ② ③ circled number format
       - step_1 ~ step_N correspond to each bullet
       - If sections exceed BULLETS_PER_PAGE, automatically paginate
    3. Play ending narration (last step), no text displayed

    Args:
        section_titles: Merged section title list
        section_steps: Built section_steps (containing audio_path, audio_duration, etc.)
                       step_0 = intro, step_1~N = bullets, step_N+1 = ending

    Returns:
        Complete Python/Manim code string
    """
    _validate_overview_section_steps(section_titles, section_steps)

    # Build all bullet text list (screen uses circled number format)
    all_bullet_texts = []
    for idx, title in enumerate(section_titles, start=1):
        all_bullet_texts.append(f"{_circled(idx)} {title}")

    num_steps = len(section_steps)
    num_bullets = len(all_bullet_texts)

    # Pagination: BULLETS_PER_PAGE per page
    pages: List[List[int]] = []
    for start in range(0, num_bullets, BULLETS_PER_PAGE):
        end = min(start + BULLETS_PER_PAGE, num_bullets)
        pages.append(list(range(start, end)))

    num_pages = len(pages)
    if num_pages == 0:
        raise ValueError("overview requires at least one section title")

    # Generate all bullet Text creation code
    bullet_creation_lines = []
    for i, bt in enumerate(all_bullet_texts):
        safe_bt = bt.replace('"', '\\"').replace("'", "\\'")
        bullet_creation_lines.append(
            f'        bullet_{i} = Text("{safe_bt}", font_size=22, color="#2C1608")'
        )
    bullet_creation_code = "\n".join(bullet_creation_lines)

    # Generate pagination animation code
    # step index: step_0 = intro, step_1 ~ step_N = bullets, step_N+1 = ending
    page_animation_blocks = []
    for page_idx, page_bullet_indices in enumerate(pages):
        block_lines = []

        if page_idx == 0:
            page_bullet_names = [f"bullet_{i}" for i in page_bullet_indices]
            block_lines.append(
                f"        # ── Page {page_idx + 1} (of {num_pages}) ──"
            )
            block_lines.append(
                f"        bullets = VGroup({', '.join(page_bullet_names)}).arrange(DOWN, center=True, buff=0.35)"
            )
            block_lines.append(
                f"        bullets.next_to(underline, DOWN, buff=0.5)"
            )
            block_lines.append(
                f"        if bullets.get_bottom()[1] < -3.5:"
            )
            block_lines.append(
                f"            bullets.scale_to_fit_height(5.0)"
            )
            block_lines.append(
                f"            bullets.next_to(underline, DOWN, buff=0.5)"
            )
            block_lines.append(
                f"        self.lecture = bullets"
            )
            block_lines.append(
                f"        self.current_lecture_line_indices = {page_bullet_indices}"
            )
        else:
            page_bullet_names = [f"bullet_{i}" for i in page_bullet_indices]
            block_lines.append(
                f"\n        # ── Page {page_idx + 1} (of {num_pages}) ──"
            )
            block_lines.append(
                f"        self.play(FadeOut(bullets))"
            )
            block_lines.append(
                f"        self.remove(bullets)"
            )
            block_lines.append(
                f"        bullets = VGroup({', '.join(page_bullet_names)}).arrange(DOWN, center=True, buff=0.35)"
            )
            block_lines.append(
                f"        bullets.next_to(underline, DOWN, buff=0.5)"
            )
            block_lines.append(
                f"        if bullets.get_bottom()[1] < -3.5:"
            )
            block_lines.append(
                f"            bullets.scale_to_fit_height(5.0)"
            )
            block_lines.append(
                f"            bullets.next_to(underline, DOWN, buff=0.5)"
            )
            block_lines.append(
                f"        self.lecture = bullets"
            )
            block_lines.append(
                f"        self.current_lecture_line_indices = {page_bullet_indices}"
            )

        # FadeIn each bullet + play_synced_step
        # step index = bullet global index + 1 (because step_0 is intro)
        for local_idx, bullet_global_idx in enumerate(page_bullet_indices):
            step_idx = bullet_global_idx + 1  # +1 because step_0 is intro
            block_lines.append(
                f"\n        # Bullet {bullet_global_idx + 1}"
            )
            block_lines.append(
                f"        self.play_synced_step("
            )
            block_lines.append(
                f"            {local_idx},"
            )
            block_lines.append(
                f"            steps[{step_idx}][\"audio_path\"],"
            )
            block_lines.append(
                f"            steps[{step_idx}][\"audio_duration\"],"
            )
            block_lines.append(
                f"            FadeIn(bullet_{bullet_global_idx}, shift=RIGHT * 0.3),"
            )
            block_lines.append(
                f"        )"
            )

        page_animation_blocks.append("\n".join(block_lines))

    page_animation_code = "\n".join(page_animation_blocks)

    # Last step index (ending)
    last_step_idx = num_steps - 1

    code = f'''from manim import *
import numpy as np

{_get_base_class_import()}

class SectionOverviewScene(TeachingScene):
    def construct(self):
        steps = {json.dumps(section_steps, ensure_ascii=False)}

        # ── Background color ──
        self.camera.background_color = "#FFFDF4"

        # ── Title ──
        page_title = Text("Course Navigation", font_size=28, color="#BE8944", weight="BOLD")
        page_title.to_edge(UP, buff=0.5)

        # ── Subtitle "Content Overview" ──
        subtitle = Text("Content Overview", font_size=24, color="#7B4B2A", weight="BOLD")
        subtitle.move_to([0, 2.0, 0])

        # Underline decoration
        underline = Line(
            start=subtitle.get_left() + DOWN * 0.2,
            end=subtitle.get_right() + DOWN * 0.2,
            color="#e4c8a6",
            stroke_width=2,
        )

        # Create all bullet Text objects
{bullet_creation_code}

        # Display title + subtitle, while playing intro narration (step_0)
        self.add_sound(steps[0]["audio_path"])
        self.play(FadeIn(page_title), FadeIn(subtitle), FadeIn(underline), run_time=min(steps[0]["audio_duration"], 2.0))
        remaining_intro = steps[0]["audio_duration"] - min(steps[0]["audio_duration"], 2.0)
        if remaining_intro > 0:
            self.wait(remaining_intro)

        # ── Paginated display of all sections ──
{page_animation_code}

        # ── Ending narration (no text displayed, only play sound) ──
        self.add_sound(steps[{last_step_idx}]["audio_path"])
        self.wait(steps[{last_step_idx}]["audio_duration"])

        self.play(FadeOut(bullets))
        self.wait(0.5)
'''

    return code


def _get_base_class_import() -> str:
    """Returns inline definition of base_class (consistent with prompts/base_class.py)."""
    return ""
