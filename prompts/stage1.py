from typing import Optional
from .user_profile import UserProfile, get_default_profile


def get_prompt1_outline(
    knowledge_point: str,
    duration: int = 5,
    reference_image_path: Optional[str] = None,
    user_profile: Optional[UserProfile] = None,
    forced_difficulty_level: Optional[str] = None
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
        user_profile = get_default_profile()

    # Get AI-generated user profile prompt
    profile_prompt = user_profile.get_stage1_prompt()
    target_language = user_profile.get_language()

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

    You are a **Computer Science Education Architect**. You need to design an in-depth algorithm teaching outline **based on Execution Trace**.

    Target algorithm: "{knowledge_point}"
    Required total video duration: at least {duration} minutes.

    {profile_prompt}
    {force_difficulty_prompt}

    This means you need to:
    1. Design sufficient sections (typically 8-12 sections).
    2. Each section must be comprehensive, covering initialization, each iteration step, boundary condition handling, complexity analysis, and summary.
    3. Especially for binary search, you cannot just explain one successful search. You must include:
       - Scene introduction (dictionary lookup / number guessing).
       - Core algorithm concept (divide and conquer).
       - Detailed code initialization (low, high, mid pointers).
       - Multiple iteration processes (left search, right search).
       - Search failure case (how pointers cross when element not found).
       - Boundary cases (empty array, single element, target at beginning/end).
       - Complexity analysis (why O(log n)).
       - Real-world application scenarios.

    # Core Instructions (Universal Analysis Protocol)
    
    0.  **Scene Introduction & Intuition Building (Conceptual Hook - MANDATORY)**:
        - Before entering code details, you MUST design a real-life analogy scenario.
        - Specific requirements:
          - Scenario-based: For example, when teaching binary search, you must first describe scenarios like "finding a book by number in a library" or "looking up a dictionary".
          - **Important**: The scenario choice must align with the target audience's life experience and cognitive level.
          - Contrast pain points: You must demonstrate the inefficiency of "naive approach" (e.g., flipping page by page, linear search) to introduce the necessity of "optimized approach" (binary search).
          - Zero code: At this stage, no code or complex variables are allowed, only discuss logic and intuition.
        - Output structure adjustment: In the JSON sections list, the first section's id must be section_0_intro, and content must be the above analogy.

    1.  **Algorithm Decomposition**:
        - If this is a basic algorithm (like sorting), directly show the process.
        - If this is a **complex/composite algorithm** (like A* search, red-black tree insertion, DP with memoization):
          - Must divide the video into: **"Base State" -> "Problem/Bottleneck Encountered" -> "Optimization Strategy/Core Operation" -> "Final State"**.
          - Or: **"Data Structure A Maintenance" + "Data Structure B Coordination"** (e.g., LRU Cache = HashMap + DoubleLinkedList).
        - **Adjust content depth and explanation style according to user profile**.

    2.  **Case Design (Case Engineering)**:
        - Design a **"Minimal Complete Case"**.
        - This case cannot be too simple (making optimization points invisible) or too complex (making the video lengthy).
        - **Adjust example complexity according to user profile**.
        - *Key*: If it's an optimization algorithm, the case must trigger that "optimization logic" (e.g., when teaching pruning algorithms, must construct a branch that can be pruned).

    3.  **Variable Tracking List**:
        - List all core variables (Trace Variables). For complex algorithms, may include: recursion stack depth, current Cost, Hash table contents, PQ queue state, etc.

    4.  **Code Display Requirements**:
        - All code must be written in **{target_language}**
        - Code style and comment detail level adjusted according to user profile

    5.  **Ending Structure Requirements (Strict Ending Structure)**:
        - **Second-to-last section (Summary)**: Only contains text summary, complexity review, pros and cons analysis. **Code is forbidden**.
        - **Last section (Full Source Code)**: Only displays complete, runnable {target_language} source code. **Long explanatory text is forbidden**. This part is specifically for viewers to pause and screenshot or read the complete logic.

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

    Please strictly output in the following format:
    {{
        "topic": "Video title (reflecting depth and hardcore nature, e.g., 'From Scratch: Memory-Level Demonstration of XXX Algorithm')",
        "target_audience": "Describe target audience based on user profile",
        "programming_language": "{target_language}",
        "difficulty_level": "{difficulty_field_instruction}",
        "data_case_definition": "Define input data in detail. For example: 'Graph G: nodes A-E, edge weights as follows...; heuristic function h(n)=...'",
        "algorithm_components": ["List involved data structures, e.g., 'Min-Heap', 'Adjacency List', 'Visited Set'"],
        "sections": [
            {{
                "id": "section_0_intro",
                "title": "Scene Introduction",
                "content": "Describe real-life analogy scenario, such as dictionary lookup, to introduce algorithm necessity.",
                "code_mapping": "None"
            }},
            {{
                "id": "section_1",
                "title": "Structure Definition and Initialization",
                "content": "Show which basic data structures are combined, initial state.",
                "code_mapping": "Class Definition / Init function"
            }},
            {{
                "id": "section_2",
                "title": "Core Logic/Optimization Point Demonstration",
                "content": "Demonstrate the most essential part of the algorithm (e.g., rotation, relaxation, pruning). Must show data changes.",
                "code_mapping": "Core Loop / Recursion / State Transition"
            }}
        ]
    }}

    **❌ Common Errors (will cause parsing failure):**
    - Comma after last array element: `["a", "b",]` ❌
    - Unescaped quotes in strings: `"say\\"hello\\""` ❌ should be `"say\\"hello\\""`
    - Using single quotes: `'title'` ❌ JSON must use double quotes
    - Comma after last object field: `{{"id": "1",}}` ❌
    """

    if reference_image_path:
        base_prompt += f"\nNote: Please refer to the provided image to decide the visual style of data structures (e.g., whether trees are drawn as circles or squares).\n"

    return base_prompt
