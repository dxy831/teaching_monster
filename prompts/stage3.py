import os
from typing import Optional
from .user_profile import UserProfile, get_default_profile


def get_prompt3_code(
    regenerate_note: str,
    section,
    section_steps,
    base_class: str,
    user_profile: Optional[UserProfile] = None,
    estimated_duration: Optional[int] = None,
    subject: str = "computer_science",
):
    """
    Generate prompt for Manim code generation

    Args:
        regenerate_note: Regeneration notes
        section: Section information object
        section_steps: Audio step sidecar data
        base_class: Base class code
        user_profile: User profile, optional
        estimated_duration: Estimated duration for this section (seconds), optional

    Returns:
        Complete prompt string
    """
    # If no user profile provided, use default profile
    if user_profile is None:
        user_profile = get_default_profile(subject)

    # Get AI-generated user profile prompt
    profile_prompt = user_profile.get_stage3_prompt()
    target_language = user_profile.get_language()
    subject = (subject or getattr(user_profile, "subject", "computer_science") or "computer_science").strip().lower()
    total_audio_duration = sum(step.get("audio_duration", 0) for step in section_steps)

    # Generate duration guidance
    duration_guidance = ""
    if estimated_duration:
        duration_guidance = f"""
    ### Duration Control Requirements
    - **Target Duration**: This section's estimated duration is **{estimated_duration} seconds**
    - **Pacing Allocation Recommendations**:
        - Given audio ground truth total duration is approximately **{total_audio_duration:.2f} seconds**
        - Each narration's duration must strictly equal the corresponding step's `audio_duration`
        - Remaining {max(0, estimated_duration - total_audio_duration):.2f} seconds are allowed only for extra pauses between narrations or section ending
    - **wait() Usage Guidelines**:
        - Strictly forbidden to use `self.wait()` inside narration segments to replace `audio_duration`
        - Very short pauses allowed between narrations: `self.wait(0.2)` to `self.wait(0.8)`
        - Before section ending, allowed: `self.wait(1)` to `self.wait(2)`
    - **⚠️ Must Strictly Follow**: Narration timeline uses `audio_duration` as the only ground truth, never compress it yourself!
    - **🧠 Cognitive pause for complex content** (use the remaining buffer time wisely):
        - **After displaying a formula setup**: `self.wait(0.8)` — let viewer read the formula
        - **Between algebraic transformation steps**: `self.wait(0.5)` — let viewer verify the step
        - **After showing a calculation result**: `self.wait(1.0)` — let viewer comprehend the answer
        - **After displaying a complex diagram**: `self.wait(1.0)` — let viewer scan all labels
        - **Example flow**: Setup formula → wait(0.8) → Substitute values → wait(0.5) → Calculate → wait(0.5) → Show result → wait(1.0)
        - These pauses should come from the {max(0, estimated_duration - total_audio_duration):.2f} seconds buffer, NOT from narration time
"""

    subject_prompt = f"""
    - Strictly forbidden to generate `self.create_code_block(`, `Code(`, or any code-pane layout for ANY subject.
    - Use diagrams, formulas, labels, arrows, tables, flow/process visuals, and highlighted objects only.
    - The final scene should be a normal `TeachingScene` with `setup_layout()` and `play_synced_step()`, but without any code display objects.
    - **Visualization Strategy: {"symbolic_algebra" if subject == "math" else "flowchart_first" if subject == "computer_science" else "diagram_first"}**
    {"- Prioritize MathTex symbolic transformations, NumberPlane/Axes with FunctionGraph, geometric constructions (Polygon, Arc, Angle). Show algebraic derivation steps sequentially." if subject == "math" else ""}
    {"- Prioritize Arrow (force vectors with labeled magnitudes), Axes/NumberPlane (motion graphs), Dot + Arrow (free-body diagrams), MathTex (formulas with units). Every physical quantity must include its unit on screen." if subject == "physics" else ""}
    {"- Prioritize RoundedRectangle + Text labels (structures), Arrow chains (processes), side-by-side VGroup columns (comparisons). Animate processes chronologically. Every technical term must have a labeled Text object on first use." if subject == "biology" else ""}
    {"- Prioritize flowcharts with RoundedRectangle boxes and Arrow connections (algorithm logic), Square/Circle + Text (data structures with labeled nodes), numbered Text labels with arrows (step-by-step logic), MathTex (Big-O notation), Axes (performance charts). Show state changes with color highlights and pointer arrows." if subject == "computer_science" else ""}
"""

    zpd_pacing_prompt = """
    ## ZPD Pacing Requirements (MANDATORY for all subjects)
    - The first narration (play_synced_step index 0) of each section should connect to prior knowledge (e.g., "We've seen that... now let's explore...").
    - Each section should advance exactly ONE core new concept. If the storyboard packs multiple ideas, split them across batches.
    - Before introducing a new concept, provide a motivation sentence explaining WHY this concept matters or what problem it solves.
    - The concept definition must appear BEFORE the example — never reverse this order.
    - The last narration of the section should bridge to the next section's topic.
    """

    return f"""
    **CRITICAL: All output content (code, comments, lecture_lines) MUST be in English.**

    You are a Python expert proficient in Manim. Write scene code for an educational video segment.
    Subject: {subject}

    {regenerate_note}
    {duration_guidance}

    {profile_prompt}

    ## Subject-specific rules
    {subject_prompt}

    {zpd_pacing_prompt}

    ## 🔴 Factual Accuracy in Manim Code (MANDATORY)
    - Every formula rendered via MathTex MUST be exactly correct — no invented notation or wrong constants.
    - Physical quantities must include units in MathTex (e.g., `r"F = 10 \\text{{ N}}"` not just `r"F = 10"`).
    - Biological terms in Text labels must use standard nomenclature (e.g., "phospholipid bilayer" not "cell cover").
    - Mathematical derivation steps must be logically ordered — no skipping steps.
    - If the narration states a fact or formula, the corresponding visual MUST match exactly.

    ## 🔴🔴🔴 Key Rules Summary (Must Read First!) 🔴🔴🔴

    **Before generating any code, ensure you understand and follow these most important rules:**

    ### Rule 1: Mathematical formulas and special symbols must use MathTex

    **🔴 The following content MUST use MathTex, strictly forbidden to use Text():**
    - All mathematical formulas (e.g., `O(log n)`, `n²`, `2^7`, etc.)
    - Comparison expressions (e.g., `5 > 3`, `mid = 5`, etc.)
    - **Checkmark ✓ and cross mark ✗ / ×** (Text cannot display them reliably in this font setup)

    ```python
    # ✅ Correct: Use MathTex for mathematical expressions
    MathTex(r"O(\log_2 n)", color="#9B6D0B").scale(0.8)
    MathTex(r"2^7 = 128", color="#9B6D0B").scale(0.8)

    # ✅ Correct: Checkmark and cross must use MathTex
    correct_mark = MathTex(r"\checkmark", color="#478211").scale(1.2)  # Green checkmark ✓
    wrong_mark = MathTex(r"\times", color="#C84A2B").scale(1.2)        # Red cross ✗

    # ❌ Wrong: Using Text will display as boxes!
    Text("O(log₂n)")  # ❌ Will display boxes
    Text("✓")         # ❌ Will display boxes
    Text("✗")         # ❌ Will display boxes
    Text("×")         # ❌ Will display boxes
    ```

    ### 🔴🔴🔴 Rule 1.1: The Only Correct Way to Write Checkmarks and Crosses (Violating this rule = Code cannot render = Generation fails) 🔴🔴🔴

    **This is the most error-prone area! AI often incorrectly uses Text("✓") or Text("✗")!**

    **✅ The only correct way (must follow this format exactly):**
    ```python
    # Green checkmark ✓ - indicates correct
    correct_mark = MathTex(r"\\checkmark", color="#478211").scale(1.2)

    # Red cross ✗ - indicates wrong
    wrong_mark = MathTex(r"\\times", color="#C84A2B").scale(1.2)
    ```

    **❌ All of the following are WRONG (will display boxes or garbled text):**
    ```python
    # ❌ Wrong way 1: Using Unicode symbols directly in Text
    Text("✗")           # ❌ Displays boxes
    Text("×")           # ❌ Displays boxes

    # ❌ Wrong way 2: Writing "checkmark" or "cross" in comments then using Text
    # Red cross indicates no swap needed
    wrong_mark = Text("✗", font_size=28, color="#C84A2B")  # ❌ Wrong!
    ```

    **🔍 Self-check: If your code contains any of the following, must change to MathTex:**
    - `Text("✓"` → Change to `MathTex(r"\\checkmark"`
    - `Text("✗"` → Change to `MathTex(r"\\times"`
    - `Text("×"` → Change to `MathTex(r"\\times"`
    - `Text("√"` → Change to `MathTex(r"\\checkmark"`

    ### 🔴🔴🔴 Rule 1.2: Strictly forbidden to replace MathTex with Text for any reason! 🔴🔴🔴

    **The runtime environment has fully configured LaTeX (texlive-full), MathTex will absolutely not have problems!**

    **All of the following excuses are invalid and strictly forbidden:**
    - ❌ "Use Text instead of MathTex to avoid LaTeX file locking issues" — **Environment has no locking issues!**
    - ❌ "Changed to Text for compatibility" — **MathTex is fully compatible!**
    - ❌ "Simplify code, use Text to replace MathTex" — **This will cause boxes!**

    **Whether generating code for the first time or fixing errors, you must use MathTex to render mathematical symbols and special symbols.**
    **If you encounter LaTeX-related errors when fixing code, you should fix the LaTeX syntax itself, not change MathTex to Text!**

    ### 🔴🔴🔴 Rule 1.3: When lecture lines contain mathematical fragments, forbidden to directly output entire sentence as Text(line)! 🔴🔴🔴

    **This is the most common source of `log₂n` rendering failures.**
    If left-side lecture lines contain mathematical/symbol fragments (like `O(`, `log`, `²`, `ₙ`, `₂`, `^`, `=`, `≤`, `≥`, `✓`, `✗`),
    **must split into Text + MathTex mixed layout**, cannot directly use `Text(line, ...)`.

    ```python
    # ❌ Wrong: Entire sentence as Text will cause log₂n / O(log n) and other symbols to render abnormally
    Text("Recursive version is O(log n), max recursion depth is log₂n", font_size=20, color="#2C1608")

    # ✅ Correct: English text uses Text, mathematical fragments use MathTex, then combine
    lecture_line = VGroup(
        Text("Recursive version is", font_size=20, color="#2C1608"),
        MathTex(r"O(\log n)", color="#2C1608").scale(0.65),
        Text(", max recursion depth is", font_size=20, color="#2C1608"),
        MathTex(r"\log_2 n", color="#2C1608").scale(0.65)
    ).arrange(RIGHT, buff=0.06, aligned_edge=DOWN)
    ```

    ### 🔴🔴🔴 Rule 1.4: First batch of lecture lines in `setup_layout()` must NOT contain mathematical symbols! 🔴🔴🔴

    `setup_layout(title_text, lecture_lines)` internally converts `lecture_lines` directly into `Text(...)` line by line.
    Therefore, if the first batch of lecture lines contains `log₂n` / `O(log n)` / `n/2^k`, rendering anomalies will occur (such as boxes, missing characters).

    **Hard requirement: The first batch of `lecture_lines` passed to `setup_layout()` must be pure English natural language, must not contain mathematical notation.**

    ```python
    # ❌ Wrong: First batch of lecture lines directly contains mathematical symbols (will be rendered by Text)
    self.setup_layout("Complexity Analysis", [
        "When 1 element remains, stop, solving k=log₂n"
    ])

    # ✅ Correct: Rewrite first batch as pure English description
    self.setup_layout("Complexity Analysis", [
        "When one element remains, stop, k=logn (base 2)"  # Although it has logn, no mathematical symbols
    ])
    ```

    **If you must display formulas, put them in the right-side animation area using `MathTex`, don't write them into `setup_layout()`'s lecture_lines.**

    ### Rule 2: Element position boundary restrictions (Strictly forbidden to go off-screen!)

    **Screen safe area (Manim coordinate system):**
    - **X-axis range**: [-7.0, 7.0] (left-right boundaries)
    - **Y-axis range**: [-4.0, 4.0] (top-bottom boundaries)

    **Left area (lecture notes):**
    - X ∈ [-7.0, 0]
    - Lecture text: `to_edge(LEFT, buff=0.3)`, height limit 2.5

    **Right area (animation demonstration):**
    - X ∈ [0.3, 6.5], Y ∈ [-3.5, 3.0]
    - Center point: `RIGHT_CENTER = [3.5, -0.5, 0]`
    - Maximum size: width 6.0, height 5.5

    ```python
    # ✅ Correct: Check boundaries after creating element
    obj.move_to(RIGHT_CENTER)
    if obj.width > 6.0: obj.scale_to_fit_width(6.0)
    if obj.height > 5.5: obj.scale_to_fit_height(5.5)

    # Check if exceeding boundaries
    if obj.get_right()[0] > 6.5:
        obj.shift(LEFT * (obj.get_right()[0] - 6.5 + 0.2))
    if obj.get_bottom()[1] < -3.5:
        obj.shift(UP * (-3.5 - obj.get_bottom()[1] + 0.2))
    if obj.get_top()[1] > 3.0:
        obj.shift(DOWN * (obj.get_top()[1] - 3.0 + 0.2))
    ```

    **❌ Common errors:**
    - Array/table too long exceeding right boundary
    - Too much text/code blocks exceeding bottom boundary
    - Animation elements overlapping with title (exceeding top boundary Y=3.0)

    **📐 Right-side element size quick reference table (refer directly when designing to avoid going off-screen!):**
    | Element Type | Max Quantity/Size | Recommended Parameters | Estimated Width |
    |---------|-------------|---------|------------|
    | Horizontal Square array | ≤8 items | side_length=0.6, buff=0.1 | 8×0.7≈5.6 ✅ |
    | Horizontal Square array | ≤10 items | side_length=0.5, buff=0.08 | 10×0.58≈5.8 ✅ |
    | Horizontal Square array | >10 items | ❌ Must split into two rows or shrink | Exceeds 6.0 ❌ |
    | Vertical text labels | ≤6 lines | font_size=18 | Height≈4.2 ✅ |
    | 2D table/matrix | ≤6×6 | cell_size=0.6 | 3.6×3.6 ✅ |
    | Binary tree | ≤4 levels | node radius=0.25 | Height≈4.0 ✅ |
    | Right-side text annotations | - | font_size=16~18 | Single line≤5.0 width |

    **🔴 Hard rules for large right-side graphics (must follow):**
    - When the right side is displaying **large graphics** (such as: horizontal arrays, 2D matrices, binary trees, call stacks, large tables),
        **additional text annotations/explanatory text/title animations (such as `Text(...)`, `MathTex(...)` labels, comparison explanations) are forbidden** to the right of that large graphic.

    **⚠️ How to handle when exceeding the above table limits:**
    - Array exceeds 10 elements → Display in two rows, or use `side_length=0.4`
    - Table exceeds 6 columns → Reduce cell_size or only show key parts
    - Text annotation too long → Line break or reduce font_size

    ### Rule 4: Lecture text must use font_size=20

    **🔴 Left-side lecture text font size must be fixed at 20!**
    **🔴 Lecture text spacing is widened automatically by the base scene. When writing `lecture_lines`, assume slightly wider rendered text and avoid packing lines too tightly.**

    ```python
    # ✅ Correct: Lecture text must use font_size=20
    new_lecture_texts = [
        Text(line, font_size=20, color="#2C1608")
    ]
    new_lecture = VGroup(*new_lecture_texts).arrange(DOWN, aligned_edge=LEFT, buff=0.3)
    new_lecture.align_to(lecture_pos, UL)
    ```

    **Font size specifications:**
    | Element Type | font_size | Description |
    |---------|-----------|------|
    | Main title | 28 | Top title, bold |
    | **Lecture text** | **20** | **Left lecture area, must be fixed** |

    ### Rule 5: construct() must call setup_layout() at the beginning

    **🔴🔴🔴 Strictly forbidden to skip setup_layout()! This is the key to setting background color! 🔴🔴🔴**

    The `setup_layout()` method sets the cream white background color `#FFFDF4`. If not called, the background will be black!

    ```python
    # ✅ Correct: First line of construct() must call setup_layout()
    class MyScene(TeachingScene):
        def construct(self):
            # 🔴 First line must call setup_layout()!
            self.setup_layout("Title text", ["Lecture text 1", "Lecture text 2"])

            # Then create other elements...

    # ❌ Wrong: Not calling setup_layout() will cause black background!
    class MyScene(TeachingScene):
        def construct(self):
            # ❌ Directly creating elements without calling setup_layout()
            title = Text("Title", ...)  # Background is black!
    ```

    ### Rule 6: Narration steps must use play_synced_step()

    **Every narration must call `self.play_synced_step(...)`.**
    It internally plays audio, keeps the corresponding sentence or sentence group highlighted, and runs right-side animations in parallel with audio.

    ```python
    # ✅ Correct: Use actual audio duration as the only time ground truth for narration
    self.play_synced_step(
        steps[0]["highlight_indices"],
        steps[0]["audio_path"],
        steps[0]["audio_duration"],
        Create(array_group)
    )

    # ❌ Wrong: Manual add_sound + wait, or writing narration duration yourself
    self.add_sound(steps[0]["audio_path"])
    self.wait(3)  # ❌ Strictly forbidden to manually write narration duration
    ```

    **Note:**
    - `steps[i]["spoken_script"]` is only used for offline TTS, not allowed to display on screen
    - Only `steps[i]["screen_text"]` can be displayed on screen
    - `steps[i]["highlight_indices"]` defines which lecture lines must stay highlighted for this audio step; if a sentence spans multiple lines, pass the full list directly into `play_synced_step(...)`
    - If right-side animations are needed inside narration segment, must be passed as parallel animations in `play_synced_step(..., *animations)`
    - Strictly forbidden to write extra `self.wait(x)` inside narration segment to align with voice
    - If current batch's `screen_texts` are not enough to cover subsequent narrations, must call `self.replace_lecture_lines(next_batch_lines)` first before continuing

    ---

    ### Core Task: General Algorithm Visualization
    Don't hardcode specific shapes, but choose the most appropriate Manim objects based on algorithm logic.

    ### 1. Dynamic Layout System
    **【Important】Left-side two-layer vertical layout, strictly forbidden to overlap:**
    ```python
    # Left-side vertical layout (top to bottom):
    # Layer 1: Title title -> to_edge(UP, buff=0.2)
    # Layer 2: Lecture text lecture -> Below title, height limit 3.5 units
    # Left area: X ∈ [-7.0, 0], Right area: X ∈ [0.3, 6.5]

    # === Layout Template ===
    LEFT_MAX_WIDTH = 6.5  # Left element max width, prevent overlap with right side

    title.to_edge(UP, buff=0.2)
    # ⚠️ Lecture text starts from top-left corner, strictly forbidden to center on Y-axis
    self.lecture.next_to(title, DOWN, buff=1.0).to_edge(LEFT, buff=0.3)

    if self.lecture.height > 3.5:
        self.lecture.scale_to_fit_height(3.5)
    if self.lecture.width > LEFT_MAX_WIDTH:
        self.lecture.scale_to_fit_width(LEFT_MAX_WIDTH)
    ```

     **【⚠️ Lecture text batch display - Hard rules】**
     - **🔴 Character limit per line**: Each line of lecture text should not exceed **43 characters** (including letters, punctuation, numbers, and spaces). Only when exceeding 43 characters should you split by semantic meaning into multiple lines. **Don't forcibly split a complete short sentence into two lines! If a sentence fits within 43 characters, keep it on one line.** Text exceeding 43 characters will invade the right-side animation area causing overlap!

     ### 🔴🔴🔴 Batching Core Rules (Most error-prone! Must strictly follow!) 🔴🔴🔴

     **All sections use max 9 lecture lines per page** (pure lecture + right-side animation)

     **Execution order (must execute in order, cannot skip steps):**
     1. **Page by simultaneously highlighted groups (more important than line limit!):**
         - Treat each step's `highlight_indices` group as one atomic unit for pagination
         - If adding the next highlighted group would exceed 9 lines on the current page, move that whole group to the next page
         - **Strictly forbidden to split one simultaneously highlighted group across two pages**
         - **Strictly forbidden to mechanically fill every page to 9 lines!**
     2. **Finally check if exceeding the scene limit (9 lines)**
         - If not exceeded: Keep the current page as-is
         - If exceeded: Switch the whole highlighted group to the next page before calling `play_synced_step()`

    - **Top-left alignment**: Lecture text must `.next_to(title, DOWN, buff=0.5).to_edge(LEFT, buff=0.3)`, starting from **top-left corner**, **strictly forbidden to center on Y-axis**
    - **Fixed position**: When first batch appears, record `lecture_pos = self.lecture.get_corner(UL)`, subsequent batches use `.align_to(lecture_pos, UL)` to maintain top-left alignment
    - **Switching method**: Current batch finished → `FadeOut` + `self.remove()` → New batch displays at **original position top-left aligned**

    **【Key】Right-side animation area (Strictly forbidden to go off-screen, must be below title):**
    ```python
    # Right area: center(3.5, -0.5), max width 6.0/height 5.5
    # ⚠️ Y range: [-3.5, 3.0], top boundary must be below title (title at Y≈3.5)
    RIGHT_CENTER = np.array([3.5, -0.5, 0])  # Center point moved down to avoid overlapping with title
    RIGHT_TOP_Y = 3.0    # Right area top boundary (below title)
    RIGHT_BOTTOM_Y = -3.5  # Right area bottom boundary

    # All right-side elements: first move_to(RIGHT_CENTER), then check size and boundaries
    if obj.width > 6.0: obj.scale_to_fit_width(6.0)
    if obj.height > 5.5: obj.scale_to_fit_height(5.5)

    # ⚠️ Check top and bottom boundaries
    if obj.get_top()[1] > RIGHT_TOP_Y:
        obj.shift(DOWN * (obj.get_top()[1] - RIGHT_TOP_Y + 0.2))
    if obj.get_bottom()[1] < RIGHT_BOTTOM_Y:
        obj.shift(UP * (RIGHT_BOTTOM_Y - obj.get_bottom()[1] + 0.2))
    ```

    ### 2. Interaction and Logic Expression
    - **Visual highlighting**: Use `SurroundingRectangle` for precise framing of diagrams, formulas, or data structures.
    - **No Orphan Narrations**: Every time a line is spoken, there MUST be a corresponding visual change or highlight on the right side if the narration refers to a diagram or visual element.
    - **Breathing timing**: After text highlighting ends, must `self.wait(0.5)`, first top-left text → pause → then right-side animation.
    - **Logic externalization**: Conditional judgment displays `MathTex("5 > 3")`, turns green if true/red if false.
    - **Recursion**: Maintain Stack VGroup in screen corner, add rectangle for each recursion level, remove on return

    ### 🔴 Rule 6.1: Lecture text must be automatically highlighted through audio steps 🔴

    **Every sentence of lecture text must be completed through `play_synced_step()`:**
    - When audio starts playing, corresponding sentence starts highlighting.
    - **Visual Sync Requirement**: Any right-side highlighting (e.g., `SurroundingRectangle` on diagrams or data structures) MUST be passed into `play_synced_step` alongside the audio.
    - **Group Highlighting**: If a speaker narrates multiple lecture lines in one sentence, those lecture lines must be placed into the same `highlight_indices` group and passed together to `play_synced_step(...)`.
    - `highlight_indices` across all steps must cover every currently displayed lecture line exactly once for that batch, with no missing indices and no duplicates.
    - Highlighting lasts for entire `audio_duration`.
    - After narration ends, restore original color `#2C1608`.
    - Strictly forbidden to skip any sentence or visual emphasis mentioned in the storyboard.

    ```python
    # ✅ Correct: Right-side highlight syncs perfectly with a grouped spoken step
    self.play_synced_step(
        steps[1]["highlight_indices"],
        steps[1]["audio_path"],
        steps[1]["audio_duration"],
        Transform(highlight, SurroundingRectangle(diagram_element, color=YELLOW))
    )
    ```

    ### 🔴 Rule 7: Correct way to combine squares + text labels (Strictly forbidden to separate with arrange!) 🔴

    **When creating square arrays with text labels, must first combine each square and text into a unit, then arrange the whole.**
    **Strictly forbidden to first move_to to stack text, then call arrange() on VGroup containing squares and text, this will push text to the right of squares!**

    ```python
    # ✅ Correct: Each square and text form a unit, then arrange
    chars = ["a", "b", "c", "d"]
    cells = VGroup()
    for c in chars:
        sq = Square(side_length=0.5, color="#e4c8a6", fill_color="#fff7e8", fill_opacity=0.8)
        txt = Text(c, font_size=18, color="#2C1608")
        txt.move_to(sq)  # Text stacked at square center
        cells.add(VGroup(sq, txt))  # Combine into one unit
    cells.arrange(RIGHT, buff=0.05)  # Arrange the whole

    label = Text("s = ", font_size=20, color="#2C1608")
    row = VGroup(label, cells).arrange(RIGHT, buff=0.2)

    # ❌ Wrong: Squares and text separately put into VGroup then arrange (text will be pushed to the right!)
    squares = VGroup(*[Square(side_length=0.5) for _ in range(4)]).arrange(RIGHT, buff=0.05)
    texts = VGroup(*[Text(c, ...) for c in chars])
    for i, t in enumerate(texts):
        t.move_to(squares[i])  # Stack first
    row = VGroup(label, squares, texts).arrange(RIGHT, buff=0.2)  # ❌ arrange will push texts as a whole to the right of squares!
    ```

    ### 3. Data Structure Mapping
    - **Array/DP Table**: `VGroup` of `Square`, must label Index
    - **Tree/Graph**: `Graph` class or `Circle` + `Line`
    - **Pointer**: `Arrow` pointing to current operation object
    - Forbidden 3D scenes, maintain 2D clear diagrams

    ### Task Input
    - Title: {section.title}
    - Screen text: {[step["screen_text"] for step in section_steps]}
    - Audio step data: {section_steps}
    - Animation instructions: {section.animations}

    ### Code Specifications
    - Inherit `TeachingScene`, define variables before use
    - Pacing: `self.wait(1)` gives audience thinking time
    - No code blocks or code displays allowed for any subject

    ### Reference Code Structure
    ```python
    from manim import *
    {base_class}

    class {section.id.title().replace('_', '')}Scene(TeachingScene):
        def construct(self):
            steps = {section_steps}
            first_page_steps = [step for step in steps if step["page_index"] == 0]
            screen_texts = first_page_steps[0]["page_screen_texts"] if first_page_steps else []
            current_page_indices = first_page_steps[0]["page_line_indices"] if first_page_steps else []

            # 🔴🔴🔴 First line must call setup_layout()! Set background color and basic layout 🔴🔴🔴
            self.setup_layout("{section.title}", screen_texts, lecture_line_indices=current_page_indices)

            # 1. Diagrams and visual elements (NO code blocks for any subject)
            # Use MathTex for formulas, Text for labels, Arrow/Line for relationships
            formula = MathTex(r"F = ma", color="#9B6D0B").scale(0.7)
            formula.move_to([3.5, 2.0, 0])

            # 2. Labeled diagram with shapes
            box1 = RoundedRectangle(width=2, height=0.8, corner_radius=0.1, color="#e4c8a6", fill_color="#fff7e8", fill_opacity=1)
            label1 = Text("Input", font_size=20, color="#2C1608")
            label1.move_to(box1)
            step_group = VGroup(box1, label1).move_to([2.0, 0.5, 0])

            box2 = RoundedRectangle(width=2, height=0.8, corner_radius=0.1, color="#c7e7aa", fill_color="#effce3", fill_opacity=1)
            label2 = Text("Output", font_size=20, color="#2C1608")
            label2.move_to(box2)
            result_group = VGroup(box2, label2).move_to([5.0, 0.5, 0])

            arrow = Arrow(box1.get_right(), box2.get_left(), color="#9B6D0B", buff=0.1)

            # 3. Checkmark and cross marks - 🔴 Must use MathTex, strictly forbidden to use Text!
            correct_mark = MathTex(r"\\\\checkmark", color="#478211").scale(1.2)
            wrong_mark = MathTex(r"\\\\times", color="#C84A2B").scale(1.2)

            # 🔴 Narration must use play_synced_step, based on actual audio duration
            self.play_synced_step(
                steps[0]["highlight_indices"],
                steps[0]["audio_path"],
                steps[0]["audio_duration"],
                FadeIn(formula)
            )

            self.play_synced_step(
                steps[1]["highlight_indices"],
                steps[1]["audio_path"],
                steps[1]["audio_duration"],
                FadeIn(step_group), FadeIn(arrow), FadeIn(result_group)
            )

            self.play_synced_step(
                steps[2]["highlight_indices"],
                steps[2]["audio_path"],
                steps[2]["audio_duration"],
                Indicate(formula, color=YELLOW)
            )

            # If the next step is on a new page, must switch left-side lecture text first
            if len(steps) > 9:
                next_page = [step for step in steps if step["page_index"] == 1]
                if next_page:
                    self.replace_lecture_lines(
                        next_page[0]["page_screen_texts"],
                        lecture_line_indices=next_page[0]["page_line_indices"],
                    )
                    self.play_synced_step(
                        next_page[0]["highlight_indices"],
                        next_page[0]["audio_path"],
                        next_page[0]["audio_duration"]
                    )
            self.wait(2)
    ```

    ### Mandatory Constraints - Fonts and Color Scheme
    **【Font Rules】** Do not explicitly set `font=` for `Text()` in generated scenes.
    **【Spacing Rules】** The base scene automatically widens spaces in title and lecture text by replacing single spaces with double spaces. Write natural English text, but do not assume tight single-space layout when estimating line fit.
    ```python
    # ✅ Correct example
    Text("Title text", font_size=28, color="#BE8944", weight="BOLD")
    Text("Lecture text", font_size=20, color="#2C1608")  # Lecture text must use font_size=20
    ```

    **【🚨🚨🚨 Mathematical Expressions and Special Symbols - Must use MathTex! 🚨🚨🚨】**

    **Complete rules see Rule 1 and Rule 1.1 above, the following is a quick reference:**

    **Core principle:** Text() cannot render mathematical symbols and special symbols (will become boxes), must use MathTex.

    ```python
    # ✅ Correct examples
    MathTex(r"O(\log_2 n)", color="#9B6D0B").scale(0.8)        # Complexity
    MathTex(r"2^7 = 128 > 100", color="#9B6D0B").scale(0.8)    # Mathematical expression
    MathTex(r"\\checkmark", color="#478211").scale(1.2)          # Green checkmark ✓
    MathTex(r"\\times", color="#C84A2B").scale(1.2)              # Red cross ✗

    # ✅ English + math mixed layout
    VGroup(
        Text("Because:",  font_size=20, color="#2C1608"),
        MathTex(r"2^7 = 128 > 100", color="#9B6D0B").scale(0.8)
    ).arrange(RIGHT, buff=0.2)

    # ❌ Wrong: All of the following will display boxes!
    # Text("✓")  Text("✗")  Text("×")  Text("O(n²)")  Text("log₂n")
    ```

    **【Symbols requiring MathTex quick reference table】**
    | Symbol Type | Common Symbols | MathTex Writing |
    |---------|---------|-------------|
    | Superscript/subscript | ², ³, ₂, ₙ | `r"^2"`, `r"^3"`, `r"_2"`, `r"_n"` |
    | Operators | ×, ÷, ≤, ≥, ≠ | `r"\\times"`, `r"\\div"`, `r"\\leq"`, `r"\\geq"`, `r"\\neq"` |
    | Log/infinity | log₂, ∞ | `r"\\log_2"`, `r"\\infty"` |
    | **Checkmark/cross** | **✓, ✗** | **`r"\\checkmark"`(green checkmark), `r"\\times"`(red cross)** |

    **⚠️ Violating this rule = Display boxes = Generation fails**

    **【Color Scheme】** `Background color: #FFFDF4` 【Cream white background, strictly forbidden to use pure black background】
    | Semantic | Text Color | Background Color | Border Color | Style |
    |------|--------|--------|--------|------|
    | Normal text | #2C1608 | - | - | Normal |
    | Main title | #BE8944 | - | - | **Bold weight="BOLD"** |
    | Important concept | #9B6D0B | #FAECD2 | #f2cf7f | - |
    | Warning/error | #C84A2B | #FBDDD6 | #f4b1a1 | - |
    | Emphasis/highlight | #C35101 | #FDDFCA | #f7bc93 | - |
    | Tip/info | #1A7F99 | #ecf6fa | #bde0ee | - |
    | Success/correct | #478211 | #effce3 | #c7e7aa | - |
    | Code block | - | #fff7e8 | #e4c8a6 | **Must use tango + background_config** |

    **🔴 Forbidden low-contrast colors on cream background (#FFFDF4):**

    The following colors have insufficient contrast and will be hard to read:
    - ❌ **Light beige/tan**: #F5E6D3, #E8D7C3, #D4C5B0 — too close to background, text will be nearly invisible
    - ❌ **Light yellow**: #FFFFE0, #FFFACD, #FFF8DC — insufficient contrast for small text
    - ❌ **Pale purple/lavender**: #E6E6FA, #D8BFD8 (especially in font_size < 20) — hard to read
    - ❌ **Light gray**: #D3D3D3, #C0C0C0 — low contrast, avoid for text

    **✅ Minimum contrast requirements:**
    - **Small text (font_size < 20)**: Use dark colors only (#2C1608, #9B6D0B, #C84A2B, #478211, #1A7F99)
    - **Medium text (font_size 20-24)**: Can use medium colors (#BE8944, #C35101)
    - **Large labels (font_size ≥ 28)**: Most colors acceptable except the forbidden list above
    - **Rule of thumb**: If you're unsure, use #2C1608 (dark brown) — it always works

    **Self-check before using a color:**
    1. Is this color in the forbidden list above? → Choose a darker alternative
    2. Is this for small text (< 20)? → Use only dark colors from the approved palette
    3. When in doubt → Use #2C1608 (normal text color)

    **【Color Scheme Principles】**
    - Each scene max 3-4 emphasis colors, ensure overall harmony
    - When lecture text reaches corresponding sentence, only change color, not position or size
    - Small box titles use semantic colors (success box uses green, error box uses red), not allowed to use main title color
    - Top main title color must be #BE8944, and must be bold
    - Border color matches title color
    - Code blocks must use specified light background and tango syntax highlighting theme, cannot use default dark theme and other syntax highlighting themes
    - Forbidden to use pure white/pure black text, forbidden colors outside palette


    ### Anti-obstruction Rules
    - **Width safety**: Text/MathTex set `max_width=5` or `.scale_to_fit_width()`
    - **⚠️ Right boundary hard limit (must follow)**:
        - Right area X ∈ [0.3, 6.5], max width 6.2
        - Check and scale after creating element:
          ```python
          if obj.get_right()[0] > 6.5 or obj.get_left()[0] < 0.3:
              obj.scale_to_fit_width(6.2).move_to([3.4, obj.get_center()[1], 0])
          ```
        - Must check and scale after VGroup's arrange()
    - **Background protection**: Add `.add_background_rectangle(color=BLACK, opacity=0.8)` for overlay labels
    - **Spacing reservation**: VGroup use `.arrange(DOWN, buff=0.5)`

    **🔴 Cleanup check before placing new elements (must follow! Prevent right-side element stacking and overlap):**

    Before placing new main elements (arrays, tables, graphs, large text blocks, etc.) on the right side, must execute the following 3 steps:
    1. **Inventory**: List which elements currently exist on the right side
    2. **Determine**: Which elements are no longer referenced in subsequent animations? (No more Transform, no more move_to, no more reading position)
    3. **Cleanup**: Execute `FadeOut` + `self.remove()` for elements no longer needed, then add new elements

    ```python
    # ✅ Correct: Before placing new array, first cleanup old unused elements
    self.play(FadeOut(old_array), FadeOut(old_labels), FadeOut(old_pointer))
    self.remove(old_array, old_labels, old_pointer)
    # After cleanup, create and add new elements
    new_array = VGroup(*[Square(side_length=0.6) for _ in range(8)]).arrange(RIGHT, buff=0.1)
    new_array.move_to([3.5, -0.5, 0])
    self.play(FadeIn(new_array))

    # ✅ Correct: Keep elements still in use, only cleanup unused ones
    # old_pointer will be used later, so only cleanup old_labels
    self.play(FadeOut(old_labels))
    self.remove(old_labels)
    new_labels = VGroup(...)
    self.play(FadeIn(new_labels))

    # ❌ Wrong: Directly add new elements without cleaning up old ones (causes overlap!)
    new_array = VGroup(...)  # ❌ Old array still in original position, old and new overlap!
    self.play(FadeIn(new_array))
    ```

    ### 🔴🔴🔴 Self-check that must be performed after generating code (Final Check) 🔴🔴🔴

    **🚨 FATAL ERROR Check — Contains any of the following lines = Code is invalid, rendering will definitely fail! 🚨**

    Before outputting code, perform the following searches on your code. If any match is found, must immediately fix, otherwise code cannot run:

    | 🚨 Search this pattern | ⚠️ Problem | ✅ Must change to |
    |----------------|---------|-----------|
    | `Text("✓"` | Will display boxes | `MathTex(r"\\checkmark", color=...).scale(1.2)` |
    | `Text("✔"` | Will display boxes | `MathTex(r"\\checkmark", color=...).scale(1.2)` |
    | `Text("√"` | Will display boxes | `MathTex(r"\\checkmark", color=...).scale(1.2)` |
    | `Text("✗"` | Will display boxes | `MathTex(r"\\times", color=...).scale(1.2)` |
    | `Text("✘"` | Will display boxes | `MathTex(r"\\times", color=...).scale(1.2)` |
    | `Text("×"` | Will display boxes | `MathTex(r"\\times", color=...).scale(1.2)` |
    | `Text("O(` | Math symbol boxes | Split into VGroup of Text + MathTex |
    | `Text("log` | Math symbol boxes | Split into VGroup of Text + MathTex |
    | `Text(".*log₂.*")` | Subscript rendering unstable/boxes | Split into Text + `MathTex(r"\\\\log_2 n")` |
    | `self.create_code_block(` | ❌ Code blocks forbidden for all subjects! | Use flowcharts, diagrams, data structure visualizations |
    | `Code(code_string=` | ❌ Code blocks forbidden for all subjects! | Use flowcharts, diagrams, data structure visualizations |
    | `self.add_to_right(` | ❌ This method has been deleted! | Manual `move_to` + boundary check + `self.play(FadeIn(...))` |
    | `self.remove_from_right(` | ❌ This method has been deleted! | `self.play(FadeOut(...))` + `self.remove(...)` |
    | `self.clear_right_area(` | ❌ This method has been deleted! | Individual `FadeOut` + `self.remove()` |
    | `# Use Text instead of MathTex` | ❌ Strictly forbidden to replace! Environment has configured LaTeX | Keep MathTex, fix LaTeX syntax |
    | `# Avoid LaTeX` | ❌ Strictly forbidden to use this as excuse | Keep MathTex, environment has no LaTeX issues |

    **🔴🔴🔴 Strictly forbidden to use code blocks — No code display for any subject! 🔴🔴🔴**
    Base class `TeachingScene` does not have `add_to_right`, `remove_from_right`, `clear_right_area` methods.
    If these calls appear in your code, runtime will directly crash with `AttributeError`!
    Correct approach: Manual `move_to()` positioning → check boundaries → `self.play(FadeIn(obj))` to add.

    **Complete self-check steps (must execute all):**
    1. Search all `Text(` calls, check if content contains ✓✗×√ or math symbols → Must change to MathTex, otherwise runtime will definitely fail!
    2. Special check all lecture lines: If line text contains `O(`/`log`/`²`/`₂`/`ₙ`/`^`/`=`/`≤`/`≥`/`✓`/`✗`, forbidden to use entire sentence `Text(line, ...)`, must change to Text + MathTex mixed layout (focus on checking `log₂n`)
    3. Check if every narration calls `play_synced_step`
    4. Check if manual `self.wait(x)` is incorrectly written inside narration segments to replace `audio_duration`
    5. Check if each line of lecture text exceeds 43 characters, if exceeded then split lines (short sentences within 43 characters should not be forcibly split)
    6. Check if lecture text batching is split by semantics, different knowledge points cannot be mixed in same batch
    7. Check if right side has "**large graphics + right-side text annotation coexisting**" situation; if so, must delete right-side text or switch scene first then display
    8. Special check first batch lines of `self.setup_layout(..., lecture_lines)`: If contains `O(` / `log` / `²` / `₂` / `ₙ` / `^` / `=` / `≤` / `≥`, must rewrite as pure English description, and move formula to right-side `MathTex`
    9. Check title and lecture line fit using widened spacing behavior; do not rely on single-space density when deciding wrapping or batch sizes
    10. **🆕 Numerical consistency check**: If your code displays the same calculation in multiple places (e.g., in narration, in a MathTex formula, in a summary box):
        - Verify all instances show the EXACT same numbers and operations
        - Example: If step 3 calculates "1.2 × 240 = 288", then step 5's summary MUST also show "1.2 × 240 = 288", NOT "1.2 × 80" or any other variant
        - Search your code for all `MathTex(r".*\d+.*")` and `Text(".*\d+.*")` that display numerical results
        - Cross-check: Do the numbers match the calculation steps? Are the operators consistent?
        - Common error: Copy-pasting a formula box but forgetting to update the numbers inside
"""


def get_regenerate_note(attempt, MAX_REGENERATE_TRIES, error_message: str = None):
    """
    Generate retry prompt (only for runtime failure cases)

    Args:
        attempt: Current attempt number
        MAX_REGENERATE_TRIES: Maximum attempt count
        error_message: Runtime failure error message (optional)
    """
    base_note = f"""⚠️ Note: This is attempt {attempt}/{MAX_REGENERATE_TRIES} to generate code.

"""

    if error_message:
        # Runtime failure case - Provide error message, require fix but maintain animation effects
        return base_note + f"""**Previous code runtime failed, error message as follows:**
```
{error_message}
```

## 🔴🔴🔴 Fix Requirements (Must strictly follow!) 🔴🔴🔴

**1. Only fix errors, don't delete content!**
- Only fix specific problems pointed out in error message
- **Strictly forbidden to delete any lecture text, animation steps, or wait() calls**
- **Strictly forbidden to shorten video duration or reduce content**
- **Strictly forbidden to simplify complex animations to only display title and text**

**2. Completeness check checklist:**
- [ ] Are all original lecture texts preserved?
- [ ] Are all original animation steps preserved?
- [ ] Is total duration of wait() calls similar to original?
- [ ] Is data structure visualization (arrays, pointers, highlights, diagrams, etc.) complete?

**3. Correct ways to fix common errors:**
| Error Type | ✅ Correct Approach | ❌ Wrong Approach |
|---------|-----------|-----------|
| Variable undefined | Add variable definition | Delete code using that variable |
| Index out of bounds | Fix index calculation or add boundary check | Reduce array element count |
| Object attribute error | Correct attribute name or method call | Delete that object |
| Animation conflict | Adjust animation order or use AnimationGroup | Delete animation |
| LaTeX error | Fix LaTeX syntax | Change to plain text (will display boxes) |
| **MathTex error** | **Fix LaTeX syntax itself** | **Change MathTex to Text (strictly forbidden!)** |
| **Quote nesting error** | Inner use single quotes `'` | Inner use Chinese double quotes `"` |

**🔴 Quote nesting rules (very important!):**
- If Text() outer layer uses double quotes `"`, inner layer must use **English single quotes** `'`
- ❌ Wrong: `Text("The largest number 'floats' to the end!")` - Chinese double quotes will cause syntax error
- ✅ Correct: `Text("The largest number 'floats' to the end!")` - Use English single quotes

**4. If really cannot fix a complex animation:**
- Replace with equivalent simple animation, rather than directly deleting
- Maintain same lecture content and duration
- Example: Complex array swap animation → Simple FadeOut + FadeIn, but preserve display of value changes

**5. Absolutely forbidden behaviors:**
- ❌ Delete entire animation demonstration part, only keep title and lecture text
- ❌ Shorten 30-second video to 5 seconds
- ❌ Delete data structure visualization
- ❌ Use code blocks or code displays for any subject
"""

    else:
        # Generic prompt when no specific information
        return base_note + """Please check and improve code:
- Ensure all variables are defined before use
- Check if `self.wait()` is sufficient
- **Keep animation effects complete, don't over-simplify**
- **Strictly forbidden to delete any lecture text, animation steps, or data structure visualization**
"""

