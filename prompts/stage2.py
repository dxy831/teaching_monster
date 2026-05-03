import json
from typing import Optional
from .user_profile import UserProfile, get_default_profile


def _get_subject_visual_strategy(subject: str, target_language: str) -> str:
    if subject == "physics":
        return """
    **Physics Visual Strategy (AP Physics 1 / C):**
    - **Force & Motion**: Use `Arrow` for force vectors with labeled magnitudes and directions. Every vector must have a text label showing its name and value (e.g., "F = 10 N").
    - **Graphs**: Use `Axes` / `NumberPlane` for motion graphs (x-t, v-t, a-t). Label both axes with quantity and unit.
    - **Free-Body Diagrams**: Use `Dot` for the object, `Arrow` for each force, and `MathTex` for labels. Forces must be drawn from the object outward.
    - **Formulas**: Use `MathTex` for all equations. Show derivation step-by-step with `TransformMatchingTex` or sequential `FadeIn`.
    - **Units**: Every numerical result displayed on screen must include its unit.
    - **FORBIDDEN**: Code blocks, code panes, execution traces — unless the section is explicitly about computational physics simulation.
"""
    elif subject == "biology":
        return """
    **Biology Visual Strategy (AP Biology):**
    - **Structures**: Use `RoundedRectangle`, `Circle`, `Ellipse` with fill colors and `Text` labels for organelles, molecules, or organisms.
    - **Processes**: Use sequential `Arrow` chains connecting labeled boxes to show metabolic pathways, signal cascades, or life cycles. Each step must be animated in order.
    - **Comparisons**: Use side-by-side layouts with `VGroup` columns for comparing structures or processes (e.g., mitosis vs. meiosis, DNA vs. RNA).
    - **Mechanism Detail**: For molecular mechanisms, animate the process chronologically — do not show the final state first.
    - **Terminology**: Every technical term must appear as a labeled `Text` object on first use, with consistent color coding throughout the video.
    - **FORBIDDEN**: Code blocks, code panes, execution traces — biology content must never include programming displays.
"""
    elif subject == "math":
        return """
    **Mathematics Visual Strategy (AP Calculus / Statistics):**
    - **Coordinate Planes**: Use `NumberPlane` or `Axes` with clearly labeled axes, scales, and key points.
    - **Functions**: Use `FunctionGraph` or `ParametricFunction` to plot curves. Highlight key features (intercepts, extrema, inflection points) with `Dot` and labels.
    - **Symbolic Transformations**: Use `MathTex` for all formulas. Show algebraic steps sequentially using `TransformMatchingTex` or `ReplacementTransform`.
    - **Geometric Constructions**: Use `Polygon`, `Arc`, `Angle`, `Line`, `DashedLine` for geometric proofs and illustrations.
    - **Proof Steps**: Each step in a derivation must be a separate `MathTex` object, animated in logical order.
    - **FORBIDDEN**: Code blocks in concept-explanation sections. Only allow code if the section explicitly covers numerical methods or computational math.
"""
    else:
        return f"""
    **Computer Science Visual Strategy (AP CS A / CS Principles):**
    - **Code Display**: Use `self.create_code_block()` for all code. Code must be in **{target_language}** and syntactically correct.
    - **Execution Traces**: Use `SurroundingRectangle` to highlight the current line of code. Track variable states with labeled boxes or tables.
    - **Data Structures**: Use `Square`/`Circle` + `Text` for arrays, trees, graphs, stacks, queues. Index labels are mandatory for arrays.
    - **State Changes**: Animate pointer movements, value swaps, and structural modifications step by step.
    - **Complexity**: Use `MathTex` for Big-O notation and `Axes` for performance comparison charts when relevant.
"""


def get_prompt2_storyboard(
    outline: str,
    duration: int = 5,
    reference_image_path: Optional[str] = None,
    user_profile: Optional[UserProfile] = None,
    subject: str = "computer_science",
):
    """
    Generate storyboard script prompt

    Args:
        outline: Outline JSON string
        reference_image_path: Reference image path (optional)
        user_profile: User configuration, optional

    Returns:
        Complete prompt string
    """
    # Use default profile if none provided
    if user_profile is None:
        user_profile = get_default_profile(subject)

    # Get AI-generated user profile prompt
    profile_prompt = user_profile.get_stage2_prompt()
    target_language = user_profile.get_language()
    subject = (subject or getattr(user_profile, "subject", "computer_science") or "computer_science").strip().lower()
    code_layout_required = subject == "computer_science"
    subject_directive = (
        f"Use split-left layout with a {target_language} code block for algorithm explanation."
        if code_layout_required
        else "Do not use code panes or code blocks; use lecture text, diagrams, formulas, labels, arrows, tables, and process animations only."
    )

    base_prompt = f"""
    **CRITICAL: All output content (titles, lecture_lines, animations) MUST be in English.**

    You are a subject-aware teaching storyboard director. Convert the outline into a detailed Manim animation script.

    Subject: {subject}
    {profile_prompt}

    # 🔴 Factual Accuracy & Multimodal Consistency (MANDATORY — Competition Standard)

    - Every formula, constant, term, or process shown on screen MUST exactly match the corresponding lecture_line narration. No discrepancy is allowed.
    - If a derivation or mechanism is presented step-by-step, every step MUST have a corresponding lecture_line — no skipping steps in either narration or visuals.
    - Physical quantities must always include units in both narration and on-screen display.
    - Do NOT show formulas or diagrams on screen that are not explained in the narration, and vice versa.

    # Subject-Specific Visual Strategy

    {_get_subject_visual_strategy(subject, target_language)}

    # Universal Visual Mapping System

    1.  **Layout Strategy**:
        - {subject_directive}
        - For computer_science sections that explain step-by-step logic, code snippets should appear throughout the relevant sections, not only at the end.
        - For non-computer-science subjects, the left side should remain lecture-focused and the right side should use visuals only.

    2.  **Abstract Concept Materialization**:
        - Use arrows, labels, tables, formulas, comparison markers, and highlighted objects to show reasoning.
        - For non-computer-science subjects, prefer phenomenon diagrams, process flows, structure comparisons, and worked-example boards.

    3.  **Script Requirements**:
        - Each lecture line must map to a visible step in the animation.
        - **Precision Highlighting Core Rule**: The "highlight" action in animations MUST precisely match the content of the current `lecture_lines`. If the narration explains multiple lines of code or concepts simultaneously, they MUST be highlighted together in the same step.
        - Each animation should correspond to a concept change, process step, comparison, or visual emphasis.
        - Keep the pacing aligned with the user profile.
        - **NEVER skip explaining on-screen content**: If a new object/code appears, there must be a corresponding lecture line and animation step to explain/highlight it.

    4.  **Duration Planning**:
        - Target total duration: {duration} minutes.
        - Remember the 50% buffer rule from the outline: planned durations should sum to approximately {int(duration * 60 / 1.5)} seconds across all sections.
        - The input `outline` already provides a specific `estimated_duration` for each section.
        - You MUST strictly follow the `estimated_duration` pre-calculated in the outline when designing exactly how many and how long your animations/lecture lines will take.
        - Provide a realistic `estimated_duration` field matching the outline's intended scale, plus your detailed `lecture_lines` that can comfortably fit within it (speech averages roughly 2-3 words per second).

    5.  **Subject Constraints**:
        - For computer_science, code examples must use **{target_language}**.
        - For non-computer-science subjects, animation descriptions must not require code displays or full-code sections.

    6.  **ZPD Pacing Requirements**:
        - The first lecture_line of each section should activate prior knowledge (e.g., "We already know that... so what happens when...?").
        - Each section should introduce only ONE core new concept — avoid packing multiple new ideas.
        - Between sections, include a bridging sentence that connects the completed topic to the next one.

    ## Input Outline
    {outline}
    """

    cs_json_example = """
    **✅ Correct JSON format example:**
    ```json
    {
        "sections": [
            {
                "id": "section_0_intro",
                "title": "Scene Introduction",
                "estimated_duration": 45,
                "lecture_lines": [
                    "First narration line",
                    "Second narration line"
                ],
                "highlight_groups": [[0], [1]],
                "animations": [
                    "Define Visual Layout: Left-Right Split.",
                    "Visual: FadeIn title at top.",
                    "Visual: Create scene illustration."
                ]
            },
            {
                "id": "section_1",
                "title": "Algorithm Core Steps",
                "estimated_duration": 60,
                "lecture_lines": [
                    "First, we define the algorithm function.",
                    "Then, we enter a loop to process data.",
                    "Inside the loop, we check if the condition is met."
                ],
                "highlight_groups": [[0], [1, 2]],
                "animations": [
                    "Define Visual Layout: Split-Left Layout for code demonstration.",
                    "Code: def algorithm():\\n    for x in data:\\n        if x > 0: pass",
                    "Action: Highlight code line 1 (def algorithm) while narrating first line.",
                    "Action: Highlight code lines 2 and 3 together while narrating the second grouped step.",
                    "Visual: Create data structure visualization."
                ]
            }
        ]
    }
    ```"""

    non_cs_json_example = """
    **✅ Correct JSON format example:**
    ```json
    {
        "sections": [
            {
                "id": "section_0_intro",
                "title": "Scene Introduction",
                "estimated_duration": 45,
                "lecture_lines": [
                    "First narration line",
                    "Second narration line"
                ],
                "highlight_groups": [[0], [1]],
                "animations": [
                    "Define Visual Layout: Left-Right Split.",
                    "Visual: FadeIn title at top.",
                    "Visual: Create scene illustration with labeled diagram."
                ]
            },
            {
                "id": "section_1",
                "title": "Core Concept Explanation",
                "estimated_duration": 60,
                "lecture_lines": [
                    "Explanation step 1",
                    "Explanation step 2",
                    "Explanation step 3"
                ],
                "highlight_groups": [[0], [1, 2]],
                "animations": [
                    "Define Visual Layout: Left-Right Split for lecture and visuals.",
                    "Visual: Create labeled diagram showing key structure.",
                    "Visual: Highlight key formula with MathTex while narrating the grouped second step.",
                    "Visual: Show process flow with arrows and labels."
                ]
            }
        ]
    }
    ```"""

    json_example = cs_json_example if code_layout_required else non_cs_json_example

    base_prompt += """

    ## ⚠️⚠️⚠️ JSON Output Format Requirements (MUST STRICTLY FOLLOW) ⚠️⚠️⚠️

    **🚨 Key Rules:**
    1. **Output pure JSON only**, do not add any explanatory text, markdown markers, or comments
    2. **Escape quotes in strings**: If string content contains double quotes `"`, must write as `\\"`
    3. **Escape newlines in strings**: Use `\\n` instead of actual newlines
    4. **No comma after last array element**
    5. **All sections must include `highlight_groups`**: It must be a JSON array of non-empty integer index arrays, such as `[[0], [1, 2], [3]]`.
       - Every lecture line index must appear exactly once across all groups.
       - If one spoken sentence covers multiple lecture_lines, those line indices must be placed in the same group.
       - Do not guess punctuation-based grouping later; you must declare the grouping explicitly here.
    6. **All strings must use double quotes**, not single quotes
    7. **Ensure JSON can be correctly parsed by Python's json.loads()**
    8. **Please output JSON directly, do not wrap with ```json ```**
    9. **Note: In JSON string content, strictly forbidden to have unescaped double quotes ("), if quoting is needed, use single quotes (') instead.**

    """
    base_prompt += json_example
    base_prompt += """

    **❌ Common Errors (will cause parsing failure):**
    ```
    // Error 1: Comma after last array element
    "lecture_lines": ["First", "Second",]  // ❌ Last comma is wrong

    // Error 2: Unescaped quotes in strings
    "title": "say\\"hello\\""  // ❌ Should be "say\\"hello\\""

    // Error 3: Using single quotes
    'title': 'Title'  // ❌ JSON must use double quotes

    // Error 4: Extra comma
    {
        "id": "section_1",
        "title": "Title",  // ❌ This is the last field, should not have comma
    }
    ```

    **Note**:
    - `estimated_duration` is the estimated duration of this section (seconds), must be an integer
    - Duration should comprehensively consider lecture_lines count, animations complexity, and viewer understanding time
    - Sum of all section durations should roughly match total video duration requirement
    - **Please output JSON directly, do not wrap with ```json ```**
    - Note: In JSON string content, strictly forbidden to have unescaped double quotes ("), if quoting is needed, use single quotes (') instead.
    """
    return base_prompt


def get_prompt_download_assets(storyboard_data):
    return f"""
Analyze this educational video storyboard script and identify up to 4 key visual elements that MUST be represented using downloaded icons/images (instead of manually drawn shapes).

Content:
{storyboard_data}

Selection Criteria:
1. Only select elements that appear in the **Introduction** or **Application** sections, and they must satisfy:
   - Recognizable real-world physical objects
   - Distinct visual characteristics that cannot be conveyed using basic geometric shapes alone
   - Concrete tangible items, not abstract concepts
2. Prefer selecting: specific animals, characters, vehicles, tools, devices, landmarks, or everyday objects.
3. **Ignore and never include**:
   - Abstract concepts (e.g., justice, communication)
   - Symbolic or conceptual icons (e.g., letters, formulas, graphs, data structure trees)
   - Geometric shapes, arrows, or math-related visual elements
   - Any object composed entirely of basic shapes without a unique visual identity

Output format:
- **Output only English keywords** (for search compatibility), one keyword per line, all lowercase, no numbering, no extra text.
"""


def get_prompt_place_assets(asset_mapping, animations_structure):
    return f"""
You need to enhance the animation descriptions by inserting downloaded assets.

Asset list:
{asset_mapping}

Current Animations Data:
{animations_structure}

Instructions:
- For each animation step, decide whether a downloaded asset should be integrated.
- Choose only the single most relevant asset for animation steps that need it.
- Insert the asset using this abstract path format: [Asset: XXX].
- Only use assets in the **Introduction** or **Application** sections.
- Keep the structure unchanged: return a JSON array containing section_index, section_id, and enhanced animations.
- Only modify animation descriptions to include asset references.
- Do not modify section_index or section_id.

Return only the enhanced animation data, and it must be a valid JSON array.
"""
