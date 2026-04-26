import json
from typing import Optional
from .user_profile import UserProfile, get_default_profile


def get_prompt2_storyboard(
    outline: str,
    reference_image_path: Optional[str] = None,
    user_profile: Optional[UserProfile] = None
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
        user_profile = get_default_profile()

    # Get AI-generated user profile prompt
    profile_prompt = user_profile.get_stage2_prompt()
    target_language = user_profile.get_language()

    base_prompt = f"""
    **CRITICAL: All output content (titles, lecture_lines, animations) MUST be in English.**

    You are a **Hardcore Algorithm Visualization Director**. Please convert the outline into a detailed Manim animation script.

    {profile_prompt}

    # Universal Visual Mapping System

    1.  **Multi-dimensional Layout Strategy**:
        - **Smart Layout Branching**:
          - **Case A: Pure Theory/No Code** -> Maintain current state: **Left-Right Split Layout**. Left side for lecture text, right side for visualization animations.
          - **Case B: Code Demonstration Scenario (With Code - DEFAULT for Algorithms)** -> **Use "Split-Left Layout"**:
            - **Rule**: For any section explaining specific algorithm steps (loops, conditionals, swaps, recursion), **must** use this mode to display code snippets. Strictly forbidden to only show code at the end.
            - **Top-Left Area (~30% height)**: Place lecture text (Lecture Notes).
            - **Bottom-Left Area (~70% height)**: Place **{target_language}** code snippet (Code Snippet).
            - **Right Area (Right Half, 100% height)**: Place core visualization/animation (Main Visual).
          - **Case C: Full Code/Pure Code (Full Code - FINAL SECTION ONLY)**:
            - **Rule**: The last section specifically displays complete **{target_language}** source code.
            - **Layout**: **Hide left text** (Lecture Notes opacity=0), enlarge and center code object (`scale(0.8).move_to(ORIGIN)`).
            - **Pagination**: If code exceeds 20 lines, must split into consecutive sub-scenes (e.g., `Scene 12.1`, `Scene 12.2`).

                - **Mandatory Pagination Protocol**:
                    - **Lecture line length limit (hard constraint)**: Each lecture line should not exceed **8 English words** (including punctuation) to fit on one line; only split by semantic meaning when exceeding 8 words. **Forbidden to forcibly split complete short sentences within 8 words into two lines.**
                    - **Lecture line batching rules (hard constraint, must execute in order)**:
                        1) **First check if there's a code block**:
                             - With code block (bottom-left has `create_code_block`) → Maximum **4 lines** per batch
                             - Without code block (pure lecture + right-side animation) → Maximum **8 lines** per batch
                        2) **Then batch by semantic completeness (priority over line limit)**:
                             - One knowledge point can span multiple batches (suggest 2-4 batches, adaptive to duration)
                             - **Different knowledge points cannot be forced into the same batch**
                             - Strictly forbidden to mechanically fill 4 or 8 lines per batch
                        3) **Finally check limit**: If exceeding 4/8 lines, only split within that knowledge point at natural semantic breakpoints, forbidden to splice across knowledge points to fill line count.
                    - **Code volume control**: If code is too long for bottom-left area, **must** split content into consecutive sub-scenes. Better multiple pages than small text.
        - **State Monitor (bottom/corner)**: Real-time display of variable values (Cost, Index, True/False).
        - **Text Zoning Strategy**:
          - **Lecture Lines (narration subtitles)**: Must be strictly limited to the "Subtitle Bar" at the bottom of the screen (Bottom 15% area). Strictly forbidden to place long explanatory text in screen center or mix with graphics.
          - **Labels**: Labels following objects must be brief (Max 2-3 words).
          - **Title**: Each section's title fixed at top-left or top, cannot obstruct Main Visual Area.

    2.  **Abstract Concept Materialization**:
        - **Reference/Pointer**: Must be drawn as arrows (Arrow).
        - **Recursion**: Must be drawn as **Call Stack**, represented by stacked rectangular blocks, with parameter values annotated beside.
        - **Comparison/Condition**: Must display temporary mathematical inequalities on screen (e.g., `dist[B] > new_dist`), disappear after evaluation.
        - **Memoization/Cache**: Draw as a table (Table/Grid), highlight and flash when hit.

    3.  **Script Requirements**:
        - Each narration line (Lecture Line) must correspond to code explanation.
        - Each animation must correspond to data changes (Create, Transform, FadeOut).
        - **Pacing Control**: Adjust according to animation pacing requirements in user profile.

    4.  **Duration Planning**:
        - Each section must include `estimated_duration` field, unit in **seconds**.
        - Duration estimation rules:
          - Each lecture_line approximately 3-5 seconds (based on text length)
          - Each complex animation approximately 2-4 seconds
          - Simple animations (FadeIn/FadeOut) approximately 0.5-1 seconds
          - Code display pages need additional 3-5 seconds for viewer reading
        - Scene introduction (intro) typically 30-60 seconds
        - Core algorithm demonstration sections typically 45-90 seconds
        - Code display sections typically 20-40 seconds
        - **Important**: Duration estimation should be conservative, better to overestimate than underestimate, ensure viewers have sufficient time to understand

    5.  **Language Adaptation Requirements**:
        - All code examples must use **{target_language}**
        - Code syntax highlighting should adapt to {target_language} syntax

    ## Input Outline
    {outline}
    """

    base_prompt += """
    
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
                    "Explanation step 1",
                    "Explanation step 2",
                    "Explanation step 3"
                ],
                "animations": [
                    "Define Visual Layout: Split-Left Layout for code demonstration.",
                    "Code: def algorithm():\\n    pass",
                    "Action: Highlight code line.",
                    "Visual: Create data structure visualization."
                ]
            }
        ]
    }
    ```

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
分析这份教育视频分镜脚本，识别出最多 4 个**必须**使用下载图标/图片（而非手动绘制形状）来表示的关键视觉元素。

内容 (Content):
{storyboard_data}

选择标准 (Selection Criteria):
1. 仅选择出现在**介绍 (Introduction)** 或 **应用 (Application)** 章节中的元素，且必须满足：
   - 现实世界中可识别的物理对象
   - 视觉特征鲜明，仅用通用几何形状不足以表达
   - 具体的实物，而非抽象概念
2. 优先选择：具体的动物、角色、交通工具、工具、设备、地标、日常物品。
3. **忽略且绝不包含**：
   - 抽象概念（如：正义、交流）
   - 思想的符号或图标（如：字母、公式、图表、数据结构树）
   - 几何形状、箭头或数学相关的视觉元素
   - 任何完全由基本形状组成且无独特视觉身份的物体

输出格式 (Output format):
- **仅输出英文关键词**（为了适配搜索引擎），每个关键词占一行，全小写，无编号，无额外文本。
"""


def get_prompt_place_assets(asset_mapping, animations_structure):
    return f"""
你需要通过插入已下载的素材来增强动画描述。

可用素材列表 (Asset list):
{asset_mapping}

当前动画数据 (Current Animations Data):
{animations_structure}

指令 (Instructions):
- 对于每一个动画步骤，判断是否应该融入已下载的素材。
- 仅为需要的动画步骤选择最相关的一个素材。
- 以此格式插入素材的**抽象路径**：[Asset: XXX]。
- **仅限**在**第一个和最后一个**章节中使用素材。
- 保持结构不变：返回一个包含 section_index, section_id 和 enhanced animations 的 JSON 数组。
- 仅修改动画描述以包含素材引用。
- 不要修改 section_index 或 section_id。

仅返回增强后的动画数据，必须是有效的 JSON 数组格式：
"""
