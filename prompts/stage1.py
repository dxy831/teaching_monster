import json
from typing import Optional
from .user_profile import UserProfile, get_default_profile


SUBJECT_LABELS = {
    "computer_science": "Computer Science",
    "physics": "Physics",
    "biology": "Biology",
    "math": "Mathematics",
    "general": "General",
}


def _get_ap_pattern_block(subject: str) -> str:
    if subject == "physics":
        return """
    **Mandatory section sequence for Physics (AP Physics 1 / C):**
    1. **Phenomenon** — Start with an observable, everyday phenomenon that raises a question (e.g., "Why does a heavier object not always fall faster?").
    2. **Driving Question** — Formulate the central question the lesson will answer.
    3. **Model Building** — Introduce the relevant physical model, define variables, state the law/formula with correct notation and units.
    4. **Quantitative Example** — Walk through a complete worked problem with numbers, showing every step of substitution, algebra, and unit checking.
    5. **Verification / Edge Case** — Discuss how the model is validated, limiting cases, or common misconceptions.
    6. **Transfer / Application** — Apply the concept to a new situation or connect to the next topic.

    Key constraints:
    - Every formula must include units (e.g., F = ma, where F is in Newtons, m in kg, a in m/s²).
    - Free-body diagrams or vector diagrams should be described in section content when forces are involved.
    - Distinguish between scalar and vector quantities explicitly.
"""
    elif subject == "biology":
        return """
    **Mandatory section sequence for Biology (AP Biology Big Idea Framework):**
    1. **Big Idea Hook** — Introduce which AP Biology Big Idea this topic connects to (Evolution, Energy, Information, Interactions).
    2. **Essential Question** — State the driving question for the lesson.
    3. **Observation / Case Study** — Present a concrete biological observation, experiment, or case that motivates the mechanism.
    4. **Mechanism** — Explain the molecular, cellular, or organismal mechanism step by step. Use precise terminology (e.g., "phospholipid bilayer", not "cell wall covering").
    5. **Comparison / Broader Context** — Compare with related processes (e.g., mitosis vs. meiosis) or discuss evolutionary/ecological significance.
    6. **Application & Extension** — Connect to real-world applications (medicine, agriculture, biotechnology) or pose a follow-up question.

    Key constraints:
    - Use standard biological nomenclature; every technical term must be defined on first use.
    - Describe processes in chronological or mechanistic order — do not jump between stages.
    - When referencing experiments, they must be real and correctly attributed.
"""
    elif subject == "math":
        return """
    **Mandatory section sequence for Mathematics (AP Calculus AB/BC / Statistics):**
    1. **Numerical Intuition** — Start with concrete numerical examples that hint at the pattern or concept (e.g., compute slopes of secant lines approaching a point).
    2. **Geometric Intuition** — Provide a visual/geometric interpretation (e.g., tangent line on a curve, area under a curve).
    3. **Formal Definition** — State the precise mathematical definition with correct notation and quantifiers.
    4. **Derivation / Proof Sketch** — Show the key steps of the derivation or proof. For AP level, include the logical chain; for standard level, a guided walkthrough is sufficient.
    5. **Worked Example** — Solve a complete problem applying the concept, showing every algebraic step.
    6. **Transfer / Applied Problem** — Apply the concept to a real-world or cross-domain problem (physics, economics, etc.) or connect to the next topic.

    Key constraints:
    - Distinguish between definitions, theorems, and corollaries explicitly.
    - Every derivation step must be logically justified — no "it can be shown that" shortcuts in AP-level content.
    - Coordinate plane / function graph sections must specify axes, scales, and key points.
"""
    else:
        return """
    **Mandatory section sequence for Computer Science (AP CS A / CS Principles):**
    1. **Problem Introduction** — Present a real-world problem that motivates the algorithm or concept.
    2. **Intuition Building** — Develop algorithmic intuition through analogy or brute-force reasoning.
    3. **Execution Trace** — Walk through the algorithm step by step on a concrete example, tracking variable states.
    4. **Implementation** — Present the complete code with line-by-line explanation.
    5. **Complexity / Tradeoff Analysis** — Analyze time and space complexity; compare with alternative approaches.
    6. **Generalization** — Discuss variations, edge cases, and connections to related algorithms or data structures.

    Key constraints:
    - All code must be syntactically correct and runnable.
    - Variable names must be semantically meaningful.
    - Complexity claims must be justified (e.g., "the loop runs n times, and each iteration does O(1) work, so total is O(n)").
"""


def get_prompt1_outline(
    knowledge_point: str,
    duration: int = 5,
    reference_image_path: Optional[str] = None,
    user_profile: Optional[UserProfile] = None,
    forced_difficulty_level: Optional[str] = None,
    subject: str = "computer_science",
):
    """
    Generate teaching outline prompt

    Args:
        knowledge_point: Knowledge point/algorithm to explain
        duration: Video duration (minutes)
        reference_image_path: Reference image path (optional)
        user_profile: User configuration, optional, defaults to default profile

    Returns:
        Complete prompt string
    """
    # Use default profile if none provided
    if user_profile is None:
        user_profile = get_default_profile(subject)

    # Get AI-generated user profile prompt
    profile_prompt = user_profile.get_stage1_prompt()
    target_language = user_profile.get_language()
    subject = (subject or getattr(user_profile, "subject", "computer_science") or "computer_science").strip().lower()
    subject_label = SUBJECT_LABELS.get(subject, "Computer Science")

    difficulty_field_instruction = (
        forced_difficulty_level
        if forced_difficulty_level
        else "difficulty level determined by user profile"
    )

    force_difficulty_prompt = ""
    if forced_difficulty_level:
        force_difficulty_prompt = f"""
    ## 🔴 Difficulty Hard Constraint (MUST STRICTLY FOLLOW)
    - Specified difficulty for this request: **{forced_difficulty_level}**
    - When outputting JSON, the `difficulty_level` field MUST and ONLY equal **\"{forced_difficulty_level}\"**
    - Strictly forbidden to rewrite this value based on user profile, additional information, or model preference
"""

    base_prompt = f"""
    **CRITICAL: All output content (topic, titles, descriptions, content) MUST be in English.**

    You are a **{subject_label} Education Architect** designing a teaching outline for a middle or high school audience.

    Target topic: "{knowledge_point}"
    Subject: {subject_label}
    
    ## ⏱️ Duration & Structure Constraints (MANDATORY)
    1. **Target Video Duration**: EXACTLY {duration} minutes ({duration * 60} seconds).
    2. **Section Count**: You must plan exactly 6 to 9 sections based on the topic's complexity.
    3. **The 50% Buffer Rule**: Actual voiceover TTS and animations will expand the planned duration by approximately 50%. 
       - Therefore, the sum of all sections' `estimated_duration` MUST be approximately **{int((duration * 60) / 1.5)} seconds**.
    4. **Duration Allocation**: You must decide the exact `estimated_duration` (in seconds) for every section. Do not just divide them equally; allocate more time for complex core concepts and examples.

    {profile_prompt}
    {force_difficulty_prompt}

    This means you need to:
    1. Design sufficient sections (typically 6-9 sections).
    2. Keep the lesson coherent from intuition to core ideas, worked examples, and summary.
    3. Ensure the explanation style matches the subject and school-level audience.

    # 🔴 Factual Accuracy & Zero-Hallucination Constraint (MANDATORY — Competition Standard)

    1. Every formula, law name, biological term, mathematical theorem, and physical constant MUST be exactly correct. No approximations or invented notations.
    2. When citing numeric values (e.g., g ≈ 9.8 m/s², Avogadro's number 6.022×10²³, speed of light c ≈ 3×10⁸ m/s), they MUST match standard textbook values.
    3. You MUST NOT invent mechanisms, theorems, experiments, or biological processes that do not exist.
    4. In each section's `content` field, verifiable facts MUST reference their source principle or law (e.g., "derived from Newton's Second Law", "follows from the base-pairing rules of DNA").
    5. When uncertain about a fact: omit it entirely rather than fabricate. Say "beyond the scope of this video" rather than give an incorrect explanation.
    6. For AP-level videos, clearly distinguish between definitions, theorems, and corollaries — never conflate them.

    # AP Subject-Specific Teaching Pattern (MANDATORY — Follow the pattern for this subject)

    **You MUST structure sections according to the AP teaching pattern below. Each phase of the pattern should correspond to one or more sections.**

    {"" if subject == "computer_science" else ""}{"## Physics (AP Physics 1 / C Inquiry-Based Pattern)" if subject == "physics" else "## Biology (AP Biology Big Idea Framework)" if subject == "biology" else "## Mathematics (AP Calculus / Statistics Pattern)" if subject == "math" else "## Computer Science (AP CS A / CS Principles Pattern)"}

    {_get_ap_pattern_block(subject)}

    # Core Instructions (Universal Analysis Protocol)

    0.  **Scene Introduction & Intuition Building (Conceptual Hook - MANDATORY)**:
        - Before entering technical details, you MUST design a real-life or classroom analogy scenario.
        - The scenario must match the audience's daily life experience and cognitive level.
        - Contrast a naive understanding with the more powerful formal idea you will teach.
        - Output structure adjustment: In the JSON sections list, the first section's id must be section_0_intro.

    1.  **Subject-aware decomposition**:
        - For computer_science: explain algorithm idea, state changes, boundary cases, complexity, and final runnable code.
        - For physics: emphasize observable phenomenon, variables, laws/formulas, worked example, and takeaway.
        - For biology: emphasize structures, processes, causal relationships, comparisons, and takeaway.
        - For math: emphasize intuition, definitions, derivation/proof sketch, worked example, and takeaway.
        - Adjust content depth and explanation style according to user profile.

    2.  **Case Design (Case Engineering)**:
        - Design a minimal but complete example or scenario.
        - The case should be concrete enough to reveal the core idea without overloading the viewer.

    3.  **Variable / Concept Tracking List**:
        - List the core concepts, variables, structures, or quantities that the video needs to track visually.

    4.  **Discipline Constraints**:
        - For computer_science, all code must be written in **{target_language}**.
        - For non-computer-science subjects, do not require code snippets or programming-language-centered explanation.

    5.  **ZPD (Zone of Proximal Development) Section-Level Requirements**:
        - Each section MUST start by activating prior knowledge (connect to what the learner already knows).
        - Each section should introduce exactly ONE core new concept — do not pack multiple new ideas into one section.
        - Examples and analogies must be calibrated to the learner profile's level — avoid cross-level jumps.
        - The last content section should include a "forward connection" that hints how this topic leads to the next concept.

    6.  **Ending Structure Requirements (Strict Ending Structure)**:
        - Second-to-last section: summary and key review only.
        - Last section:
          - For computer_science: complete runnable **{target_language}** source code.
          - For non-computer-science subjects: final recap sheet with formulas, key terms, or process map only.

    # Output Format (JSON)

    ## ⚠️⚠️⚠️ JSON Output Format Requirements (MUST STRICTLY FOLLOW) ⚠️⚠️⚠️

    **🚨 Key Rules:**
    1. **Output pure JSON only**, do not add any explanatory text, markdown markers, or comments
    2. **Escape quotes in strings**: If string content contains double quotes `"`, must write as `\\"`
    3. **Escape newlines in strings**: Use `\\n` instead of actual newlines
    4. **No comma after last array element**
    5. **All strings must use double quotes**, not single quotes
    6. **Ensure JSON can be correctly parsed by Python's json.loads()**
    7. **Please output JSON directly, do not wrap with ```json ```**
    8. **Note: In JSON string content, strictly forbidden to have unescaped double quotes ("), if quoting is needed, use single quotes (') instead.**

    Please strictly output in the following format:
    {{
        "topic": "Video title in English",
        "target_audience": "Describe target audience based on user profile",
        "subject": "{subject}",
        {f'"programming_language": {json.dumps(target_language)},' if subject == 'computer_science' else ''}
        "difficulty_level": "{difficulty_field_instruction}",
        "data_case_definition": "Define the teaching case, phenomenon, or worked example in detail",
        "algorithm_components": ["List tracked concepts, variables, formulas, structures, or stages"],
        "sections": [
            {{
                "id": "section_0_intro",
                "title": "Scene Introduction",
                "content": "Real-life or classroom introduction that motivates the topic.",
                "estimated_duration": 30{f',{chr(10)}                "code_mapping": "None"' if subject == 'computer_science' else ''}
            }},
            {{
                "id": "section_1",
                "title": "Core Concept",
                "content": "Introduce the main concept and key mechanism.",
                "estimated_duration": 45{f',{chr(10)}                "code_mapping": "Describe which code segment this section maps to"' if subject == 'computer_science' else ''}
            }}
        ]
    }}

    **❌ Common Errors (will cause parsing failure):**
    - Comma after last array element: `["a", "b",]` ❌
    - Unescaped quotes in strings: `"say\"hello\""` ❌ should be `"say\"hello\""`
    - Using single quotes: `'title'` ❌ JSON must use double quotes
    - Comma after last object field: `{{"id": "1",}}` ❌
    - Returning markdown fences like ```json ... ``` ❌
    """

    if reference_image_path:
        base_prompt += f"\nNote: Please refer to the provided image to decide the visual style of data structures (e.g., whether trees are drawn as circles or squares).\n"

    return base_prompt
