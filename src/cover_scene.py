"""
Cover Scene Generator — Video Cover Template

Generates a deterministic cover section at the beginning of the video, displaying the topic name in large text + subtitle.

Visual Design:
- 135° diagonal gradient background (#fff6db → #f9ebe4 → #fbd9c4), consistent with frontend k2v-preview
- Main title: Short topic name (e.g., "Binary Search"), bold large text in dark brown
- Subtitle: Full topic name, slightly smaller font
- Top and bottom decorative lines, Create animation expanding from center
- Voiceover TTS: Plays introduction audio

This module does not depend on LLM, deterministic template ensures 100% success rate.
"""

from __future__ import annotations

import json
import math


def _validate_cover_section_steps(section_steps: list) -> None:
    for idx, step in enumerate(section_steps):
        if not isinstance(step, dict):
            raise ValueError(f"cover step {idx} is not a dict")
        audio_path = step.get("audio_path")
        if not isinstance(audio_path, str) or not audio_path.strip():
            raise ValueError(f"cover step {idx} has invalid audio_path: {audio_path!r}")
        audio_duration = step.get("audio_duration")
        if not isinstance(audio_duration, (int, float)) or not math.isfinite(audio_duration) or audio_duration <= 0:
            raise ValueError(f"cover step {idx} has invalid audio_duration: {audio_duration!r}")


def generate_cover_manim_code(topic: str, short_title: str, section_steps: list) -> str:
    """
    Generate complete Manim code for cover section (deterministic template, no LLM dependency).

    Visual Design:
    1. Full-screen 135° gradient background rectangle (#fff6db → #f9ebe4 → #fbd9c4)
    2. Top decorative line expands from center to sides with Create animation
    3. Main title (short name) centered FadeIn
    4. Subtitle (full name) FadeIn below main title
    5. Bottom decorative line expands from center to sides with Create animation
    6. Play introduction voiceover, hold for display
    7. Fade out

    Args:
        topic: Full topic name (subtitle)
        short_title: Short topic name (main title, e.g., "Binary Search")
        section_steps: Built section steps (containing audio_path, audio_duration)

    Returns:
        Complete Python/Manim code string
    """
    _validate_cover_section_steps(section_steps)

    # Safely escape quotes
    safe_topic = topic.replace('"', '\\"').replace("'", "\\'")
    safe_short_title = short_title.replace('"', '\\"').replace("'", "\\'")

    code = f'''from manim import *
import numpy as np

{_get_base_class_import()}

class CoverScene(Scene):
    def construct(self):
        steps = {json.dumps(section_steps, ensure_ascii=False)}

        # ── Gradient background (135°, top-left to bottom-right) ──
        self.camera.background_color = "#f9ebe4"

        bg = Rectangle(
            width=20, height=12,
            fill_opacity=1.0,
            stroke_width=0,
        )
        bg.set_fill(color=["#fff6db", "#f9ebe4", "#fbd9c4"])
        bg.set_sheen_direction(DR)
        bg.move_to(ORIGIN)
        self.add(bg)

        # ── Main title (short name, centered) ──
        title = Text(
            "{safe_short_title}",
            color="#7B4B2A",
            weight="BOLD",
        )
        title.move_to(UP * 0.5)

        # ── Subtitle (full name) ──
        subtitle = Text(
            "{safe_topic}",
            font_size=24,
            color="#8B5E3C",
        )
        subtitle.next_to(title, DOWN, buff=0.5)

        # ── Decorative lines ──
        line_width = max(title.width, subtitle.width) + 1.5
        line_width = max(line_width, 5.0)
        half_width = line_width / 2

        upper_line = Line(
            start=LEFT * half_width,
            end=RIGHT * half_width,
            color="#e4c8a6",
            stroke_width=2.5,
        )
        upper_line.next_to(title, UP, buff=0.6)

        lower_line = Line(
            start=LEFT * half_width,
            end=RIGHT * half_width,
            color="#e4c8a6",
            stroke_width=2.5,
        )
        lower_line.next_to(subtitle, DOWN, buff=0.6)

        # ── Animation sequence ──
        # 0. First add all elements statically to the scene (ensure first frame is complete cover for video thumbnail)
        self.add(upper_line, title, subtitle, lower_line)
        self.wait(0.1)

        # 1. Remove static elements, re-display with animation (visually starts from complete cover, then has entrance feel)
        self.remove(upper_line, title, subtitle, lower_line)

        # 2. Decorative lines expand from center
        self.play(
            Create(upper_line),
            Create(lower_line),
            run_time=0.8,
        )

        # 3. Main title FadeIn
        self.play(
            FadeIn(title, scale=0.9),
            run_time=0.6,
        )

        # 4. Subtitle FadeIn
        self.play(
            FadeIn(subtitle, shift=UP * 0.2),
            run_time=0.5,
        )

        # 5. Play introduction voiceover
        if steps:
            self.play_synced_step(
                steps[0].get("highlight_indices", [0]),
                steps[0]["audio_path"],
                steps[0]["audio_duration"],
            )
        else:
            self.wait(2.0)

        # 6. Brief fade out transition
        self.play(
            FadeOut(title),
            FadeOut(subtitle),
            FadeOut(upper_line),
            FadeOut(lower_line),
            run_time=0.6,
        )

        self.wait(0.3)
'''

    return code


def _get_base_class_import() -> str:
    """Returns empty string, let agent.py's replace_base_class handle it uniformly."""
    return ""
