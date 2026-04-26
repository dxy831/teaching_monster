# prompts/stage4.py

def get_prompt4_layout_feedback(section, position_table):
    return f"""
1. ANALYSIS REQUIREMENTS:
- Please analyze this Manim educational video solely from the perspective of **Layout** and **Spatial Positioning**.
- Refer to the provided grid diagram for precise spatial analysis.
- Core objective: Eliminate obstruction, overlap, and optimize grid space utilization.

2. Content Context:
- Title: {section.title}
- Lecture Lines: {'; '.join(section.lecture_lines)}
- Current Grid Occupancy: {position_table}

3. Visual Anchor System (6×6 grid, right area only):
lecture | A1 A2 A3 A4 A5 A6 | B1 B2 B3 B4 B5 B6 | C1 C2 C3 C4 C5 C6 | D1 D2 D3 D4 D5 D6 | E1 E2 E3 E4 E5 E6 | F1 F2 F3 F4 F5 F6

- Point positioning: self.place_at_grid(obj, 'B2', scale_factor=0.8)
- Area positioning: self.place_in_area(obj, 'A1', 'C3', scale_factor=0.7)

4. Layout Evaluation (check all items):
- **Obstruction**: Do animation elements obstruct the lecture lines on the left? [Critical]
- **Overlap**: Do animation elements (formulas, labels, shapes) overlap with each other?
- **Off-screen**: Are elements cut off or beyond the visible screen area? [Especially long text labels]
- **Grid Violation**: Is space utilization unreasonable (too crowded or too sparse)?
- **Not Disappeared**: Check if there are elements that should have faded out but didn't.

5. Mandatory Constraints:
- Color: Point out areas where colors are unclear.
- Font/Scale: Adjust font size and asset scaling based on grid position.
- Consistency: **Do NOT** apply any position or size animations to lecture lines on the left; only change color.
- Proximity: Ensure label text is within 1 grid unit of its corresponding object.

6. Lecture Line Batching Rules Verification (Hard Constraint):
- Each lecture line should not exceed **8 English words** (including punctuation, letters, numbers) to fit on one line; only split by semantic meaning when exceeding 8 words.
- Prohibit forcibly splitting complete short sentences under 8 words into two lines.
- First determine if there is a code block:
    - With code block (bottom-left has `create_code_block`) → Maximum **4 lines** per batch
    - Without code block (pure lecture + right-side animation) → Maximum **8 lines** per batch
- Batching must prioritize semantic completeness:
    - The same knowledge point can span multiple batches (recommended 2-4 batches, adaptive to duration), but cannot be merged with the next knowledge point in the same batch
    - Different knowledge points cannot be forcibly combined into the same batch
    - Strictly prohibit mechanically filling each batch to 4 or 8 lines
- If violations of the above rules are found, you must provide executable fix suggestions in `improvements` (including object and code modification direction).

7. Rendering Failure Detection (Hard Constraint, New):
- Must check for "character rendering failure" phenomenon: small squares/hollow boxes/garbled placeholders appearing on screen.
- Focus on checking: mathematical formulas, superscripts/subscripts, comparison symbols (such as ≤ ≥ ≠), and checkmark/cross symbols (✓ ✗ × √).
- If the above issues are found, `layout.has_issues` must be true, and clearly specify in `improvements`:
    - Problem object (e.g., a certain title, label, lecture line, formula)
    - Trigger cause (e.g., incorrectly using `Text("✓")`, mixing mathematical fragments into entire `Text` sentence)
    - Fix solution (change to `MathTex`, or Text+MathTex mixed layout)
- For checkmark/cross symbols, must provide the only recommended fix:
    - Checkmark: `MathTex(r"\\checkmark", color="#478211")`
    - Cross: `MathTex(r"\\times", color="#C84A2B")`

8. Important: Must strictly output according to the following JSON structure:
{{
    "layout": {{
        "has_issues": true,  // true if there are obvious layout issues
        "improvements": [
            {{
                "problem": "Specific problem description (English)",
                "solution": "Suggested code logic modification, e.g.: Move circle from C3 to E3",
                "line_number": X, // Estimated code line number
                "object_affected": "Name of affected object"
            }},
            ...
        ]
    }}
}}

9. Solution Requirements:
- Provide specific grid coordinate suggestions in the solution.
- Only list the top 3 layout issues that most affect visual experience!
- Do not provide video timestamps.
- Problem descriptions should be concise, solutions should be specific and executable.
"""


def get_feedback_list_prefix(feedback_improvements):
    """
    Generate prefix description for feedback list
    """
    return f"""
MLLM Visual Feedback Suggestions: Based on analysis of the generated video, please resolve the following layout issues:
{chr(10).join([f"- {improvement}" for improvement in feedback_improvements])}
"""


def get_feedback_improve_code(feedback, code):
    return f"""
You are a Manim v0.19.0 educational animation expert.

**MANDATORY**:
- Modify the current Manim code based on the following feedback.
- Use bright, high-contrast colors for animations and labels!
- **Strictly prohibit** applying any position or size animations to lecture lines on the left; only allow color changes (highlight).
- Lecture line batching must be consistent with upstream rules:
    - Each line should not exceed 8 words (only split by semantic meaning when exceeding)
    - With code block: ≤4 lines per batch; without code block: ≤8 lines per batch
    - Batching prioritizes semantic completeness, strictly prohibit mechanically filling line counts
- If character rendering failure exists (small squares/garbled placeholders):
    - Mathematical and symbol content must be changed to `MathTex`
    - Entire sentence text containing mathematical fragments should be changed to Text+MathTex mixed layout
    - Checkmark/cross symbols must use:
        - `MathTex(r"\\checkmark", color="#478211")`
        - `MathTex(r"\\times", color="#C84A2B")`
- Only output the updated complete Python code. No explanation needed.

Feedback:
{feedback}

---

Current Code:
```python
{code}
"""
