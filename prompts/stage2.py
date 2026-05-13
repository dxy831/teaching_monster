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
    **Computer Science Visual Strategy (Algorithm & Data Structure Topics):**
    - **Algorithm Logic**: Use flowcharts with RoundedRectangle boxes and Arrow connections to show decision flow and process steps
    - **Data Structures**: Use `Square`/`Circle` + `Text` for arrays, trees, graphs, stacks, queues. Index labels are mandatory for arrays. Animate with color changes and pointer arrows.
    - **State Changes**: Animate pointer movements, value swaps, and structural modifications step by step using Transform and color highlights
    - **Complexity**: Use `MathTex` for Big-O notation (e.g., r"O(n \\log n)") and `Axes` for performance comparison charts
    - **Step-by-step Logic**: Use numbered Text labels with arrows to show algorithm steps in natural language (e.g., "1. Compare elements", "2. Swap if needed")
    - **FORBIDDEN**: Code blocks, code syntax, programming language keywords, execution traces on code lines
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
    subject_directive = "Use left-right split layout: left side for lecture text, right side for diagrams, formulas (MathTex), labeled structures, process flows, and animations. No code blocks or programming syntax allowed."

    base_prompt = f"""
    **CRITICAL: All output content (titles, lecture_lines, animations) MUST be in English.**

    You are a subject-aware teaching storyboard director. Convert the outline into a detailed Manim animation script.

    Subject: {subject}
    {profile_prompt}

    # 🔴 Terminology Calibration (MANDATORY — Grade-Appropriate Vocabulary)

    **All technical terms must match the user's grade level and background:**
    - **Middle school (6th-8th grade)**: Use everyday language. Define every technical term on first use with a simple analogy. Avoid graduate-level jargon entirely.
    - **High school (9th-10th grade)**: Use standard high school vocabulary. Replace advanced jargon with simpler alternatives:
      - ❌ "marginal gain" → ✅ "extra benefit" or "additional gain"
      - ❌ "tangent line" → ✅ "flat line at the peak" or "horizontal at the top"
      - ❌ "kinematic formula" → ✅ "motion formula" or "equation for movement"
      - ❌ "inference engine" → ✅ "reasoning system" or "decision-making logic"
      - ❌ "heuristics" → ✅ "rules of thumb" or "practical shortcuts"
    - **AP/College level**: Standard academic terminology is acceptable, but still define specialized terms on first use.
    - **First-use rule**: When introducing a new technical term, the lecture_line must include a brief plain-English definition or analogy in the same sentence.

    **Examples of grade-appropriate terminology:**
    - Middle school: "The ball speeds up as it falls" (not "The ball experiences constant acceleration due to gravity")
    - High school: "The ball accelerates at 9.8 m/s² downward" (not "The ball's velocity vector undergoes uniform temporal differentiation")
    - AP/College: "The ball experiences constant gravitational acceleration g ≈ 9.8 m/s²" (technical terms OK, but define on first use)

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
        - **All subjects**: Left side displays lecture text; right side uses diagrams, formulas (MathTex), labeled structures, process flows, comparison tables, and animated visualizations
        - **For algorithm/CS topics**: Use flowcharts, data structure animations (arrays with indices, trees with labeled nodes), and step-by-step natural language descriptions with numbered labels

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
        - Remember the 40% buffer rule from the outline: planned durations should sum to approximately {int(duration * 60 / 1.4)} seconds across all sections.
        - **Formula derivation buffer**: When a section involves step-by-step formula derivation, algebraic manipulation, or numerical calculation:
          - Allocate 20-30% extra time compared to simple concept explanation
          - Each derivation step should have its own lecture_line (minimum 3-4 seconds per step)
          - Example: A 60-second concept section becomes 75-80 seconds if it includes a 3-step derivation
        - **Math-heavy sections pacing**: For sections with multiple formulas or calculations:
          - Setup formula: 4-5 seconds
          - Each substitution/transformation step: 3-4 seconds
          - Final result display: 4-5 seconds
          - Do NOT rush through "obvious" algebraic steps — the viewer needs time to verify each step mentally
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
        - **Interactive pause points (optional but recommended)**: Before revealing the solution to a worked example, consider adding a lecture_line like "Pause the video here and try it yourself" or "Can you figure out what happens next?" with the corresponding animation showing the problem setup. This activates retrieval practice and improves learning retention.
        - **Concept-before-example rule**: Always introduce the concept definition or principle FIRST, then follow with the worked example. Never show an example before explaining what concept it demonstrates.
        - **Motivation-before-definition rule**: Before defining a new concept, provide a 1-sentence motivation explaining WHY this concept is useful or what problem it solves. This helps the learner understand the purpose before diving into details.
        - Respect the outline's `prior_knowledge_activation`, `new_concept`, `evidence_basis`, and `bridge_to_next` fields when writing lecture lines.
        - The first lecture line MUST realize the outline's prior-knowledge activation in learner-appropriate language.
        - Each section MUST include at least one lecture line that states why the key claim is valid, based on a definition, law, theorem, experiment, or worked-example rule.
        - The section's vocabulary must stay within the learner profile's `max_new_terms_per_section` and avoid `forbidden_jargon` unless immediately explained.

    7.  **Traceability Requirements (MANDATORY)**:
        - Each section must include `evidence_lines_indices` listing the lecture line indices that state evidence, justification, or source principles.
        - Each section must include `zpd_check_line_index` pointing to the lecture line that activates prior knowledge.
        - Each section must include `bridge_line_index` pointing to the lecture line that bridges to the next idea or next section.
        - Each section must include `new_terms_introduced`, listing only the genuinely new technical terms introduced in that section.
        - `new_terms_introduced` must be short, learner-level-appropriate, and consistent with the single `new_concept` for the section.

    ## Input Outline
    {outline}
    """

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
                "evidence_lines_indices": [1],
                "zpd_check_line_index": 0,
                "bridge_line_index": 1,
                "new_terms_introduced": ["example term"],
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
                "evidence_lines_indices": [1, 2],
                "zpd_check_line_index": 0,
                "bridge_line_index": 2,
                "new_terms_introduced": ["key term", "second term"],
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

    json_example = non_cs_json_example

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
