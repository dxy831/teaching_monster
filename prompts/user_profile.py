"""
User Profile Configuration Module
Supports generating customized video content through natural language descriptions
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any, Callable


SUBJECT_DISPLAY_NAMES = {
    "computer_science": "Computer Science",
    "physics": "Physics",
    "biology": "Biology",
    "math": "Mathematics",
    "general": "General",
}
NON_CS_SUBJECTS = {"physics", "biology", "math", "general"}


def _normalize_subject(subject: Optional[str]) -> str:
    subject = (subject or "computer_science").strip().lower()
    return subject if subject in SUBJECT_DISPLAY_NAMES else "computer_science"


def _default_target_language(subject: str) -> str:
    return "Python" if _normalize_subject(subject) == "computer_science" else "Not applicable"


def _default_evidence_preference(subject: str) -> str:
    if _normalize_subject(subject) in {"physics", "biology", "math"}:
        return "definition / law / experiment / textbook theorem"
    return "definition / textbook rule / worked example"


def _default_known_concepts(subject: str) -> list:
    mapping = {
        "physics": ["basic algebra", "units", "simple motion", "proportional reasoning"],
        "biology": ["cells", "basic inheritance", "organs and tissues", "simple cause and effect"],
        "math": ["basic algebra", "functions", "coordinate plane", "solving equations"],
        "computer_science": ["variables", "loops", "conditionals", "basic arrays"],
        "general": ["basic school-level concepts", "simple cause and effect", "reading charts"],
    }
    return mapping.get(_normalize_subject(subject), ["basic school-level concepts"])


def _default_forbidden_jargon(subject: str) -> list:
    mapping = {
        "physics": ["lagrangian", "partial differential equation", "tensor field"],
        "biology": ["epigenetic regulation", "allosteric modulation", "phylogenetic incongruence"],
        "math": ["epsilon-delta proof", "measure theory", "partial differential equation"],
        "computer_science": ["amortized analysis", "monad", "red-black tree invariant"],
        "general": ["specialized jargon", "graduate-level terminology"],
    }
    return mapping.get(_normalize_subject(subject), ["advanced jargon"])


def _default_stage2_guidance(subject: str) -> Dict[str, Any]:
    normalized_subject = _normalize_subject(subject)
    if normalized_subject in NON_CS_SUBJECTS:
        return {
            "visual_complexity": "Moderate, with clear diagrams and visual emphasis on key relationships",
            "animation_pace": "Medium pace, pause at key transitions and comparisons",
            "code_display_style": "No code blocks allowed; use flowcharts, data structure diagrams, and step-by-step natural language descriptions",
            "lecture_tone": "Clear, encouraging, and concept-focused",
            "emphasis_points": "Core concepts, causal relationships, and representative examples",
            "primary_visual_type": "diagrams, labels, formulas",
            "avoid_visual_types": "code_blocks, code syntax, execution traces on code lines",
            "max_new_terms_per_section": 3,
            "retrieval_pause_frequency": "every 2 sections",
        }
    return {
        "visual_complexity": "Moderate, detailed display of key steps",
        "animation_pace": "Medium pace, pause and explain at key steps",
        "code_display_style": "No code blocks allowed; use flowcharts, data structure visualizations, and step-by-step natural language descriptions",
        "lecture_tone": "Professional but understandable",
        "emphasis_points": "Core algorithm ideas and implementation techniques",
        "primary_visual_type": "flowcharts, data_structure_diagrams, algorithm_step_boxes",
        "avoid_visual_types": "code_blocks, code syntax",
        "max_new_terms_per_section": 3,
        "retrieval_pause_frequency": "every 2 sections",
    }


def _default_stage3_guidance(subject: str) -> Dict[str, Any]:
    normalized_subject = _normalize_subject(subject)
    if normalized_subject in NON_CS_SUBJECTS:
        return {
            "code_language": "Not applicable",
            "code_style": "Prefer diagrams, formulas, arrows, tables, and highlighted labels instead of code",
            "variable_naming": "Use semantic object names that match the subject concepts",
            "comment_density": "Low",
            "complexity_handling": "Explain formulas or reasoning only when helpful to understanding",
            "visualization_strategy": {
                "physics": "diagram_first",
                "biology": "diagram_first",
                "math": "symbolic_algebra",
                "general": "diagram_first",
            }.get(normalized_subject, "diagram_first"),
            "manim_objects_priority": {
                "physics": ["Arrow", "Vector", "Axes", "NumberPlane", "MathTex", "Dot"],
                "biology": ["RoundedRectangle", "Arrow", "Circle", "Ellipse", "Text", "MathTex"],
                "math": ["NumberPlane", "FunctionGraph", "MathTex", "Polygon", "Angle", "Axes"],
                "general": ["MathTex", "Arrow", "Text", "RoundedRectangle"],
            }.get(normalized_subject, ["MathTex", "Arrow", "Text", "RoundedRectangle"]),
        }
    return {
        "code_language": "Not applicable",
        "code_style": "Use flowcharts and data structure visualizations instead of code",
        "variable_naming": "Semantic naming for diagram elements",
        "comment_density": "Low",
        "complexity_handling": "Brief explanation of time and space complexity using Big-O notation in MathTex",
        "visualization_strategy": "flowchart_first",
        "manim_objects_priority": ["RoundedRectangle", "Square", "Circle", "Arrow", "MathTex", "Graph"],
    }


def _coerce_string(value: Any, default: str) -> str:
    if isinstance(value, str):
        normalized = value.strip()
        return normalized or default
    return default


def _coerce_list_of_strings(value: Any, default: list) -> list:
    if not isinstance(value, list):
        return list(default)
    normalized_items = []
    for item in value:
        if item is None:
            continue
        text = str(item).strip()
        if text:
            normalized_items.append(text)
    return normalized_items or list(default)


def _coerce_positive_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _build_default_profile_schema(subject: str) -> Dict[str, Any]:
    normalized_subject = _normalize_subject(subject)
    if normalized_subject in NON_CS_SUBJECTS:
        subject_name = SUBJECT_DISPLAY_NAMES[normalized_subject]
        default_learning_goal = (
            f"Build a solid conceptual understanding of {subject_name}"
            if normalized_subject != "general"
            else "Build a clear conceptual understanding of the topic"
        )
        default_background = (
            f"Interested in {subject_name} with a general school-level foundation"
            if normalized_subject != "general"
            else "Interested in the topic with a general school-level foundation"
        )
        default_audience = (
            f"Middle or high school learners studying {subject_name}"
            if normalized_subject != "general"
            else "Middle or high school learners exploring a general topic"
        )
        default_hook = (
            f"Start from an everyday or classroom scenario that makes the {subject_name} idea feel useful"
            if normalized_subject != "general"
            else "Start from an everyday or classroom scenario that makes the topic feel useful"
        )
        return {
            "user_summary": {
                "age_group": "Middle or high school student",
                "background": default_background,
                "learning_goal": default_learning_goal,
                "target_language": "Not applicable",
                "difficulty_preference": "intermediate",
                "ap_level": "standard",
                "zpd_prior_knowledge": "General school-level foundation in the subject",
                "zpd_learning_target": default_learning_goal,
                "known_concepts": _default_known_concepts(normalized_subject),
                "forbidden_jargon": _default_forbidden_jargon(normalized_subject),
            },
            "stage1_outline_guidance": {
                "audience_description": default_audience,
                "content_depth": "Focus on intuition first, then core principles and representative examples",
                "example_style": "Use school-level scenarios, diagrams, and concrete examples",
                "pacing_requirement": "Medium pace with clear step-by-step explanation",
                "motivation_hook": default_hook,
                "ap_teaching_pattern": {
                    "physics": "Phenomenon → Driving Question → Model Building → Quantitative Example → Verification / Edge Case → Transfer",
                    "biology": "Big Idea → Essential Question → Observation / Case → Mechanism → Broader Context → Application",
                    "math": "Numerical Intuition → Geometric Intuition → Formal Definition → Derivation / Proof Sketch → Worked Example → Transfer",
                    "general": "Concept Introduction → Core Explanation → Worked Example → Summary",
                }.get(normalized_subject, "Concept Introduction → Core Explanation → Worked Example → Summary"),
                "factuality_anchors": [],
                "zpd_bridge_strategy": "Start from what the learner already knows and build toward the new concept step by step",
                "must_master_outcomes": ["Understand the core idea", "Explain the main process or rule"],
                "likely_misconceptions": ["May confuse related terms if they are introduced too quickly"],
                "evidence_preference": _default_evidence_preference(normalized_subject),
            },
            "stage2_storyboard_guidance": _default_stage2_guidance(normalized_subject),
            "stage3_code_guidance": _default_stage3_guidance(normalized_subject),
        }

    return {
        "user_summary": {
            "age_group": "College/Graduate student",
            "background": "Some programming foundation",
            "learning_goal": "Learn algorithms and data structures",
            "target_language": "Python",
            "difficulty_preference": "advanced",
            "ap_level": "AP",
            "zpd_prior_knowledge": "Understands basic programming, loops, conditionals, and simple data types",
            "zpd_learning_target": "Master the algorithm idea, implementation, and complexity analysis",
            "known_concepts": _default_known_concepts(normalized_subject),
            "forbidden_jargon": _default_forbidden_jargon(normalized_subject),
        },
        "stage1_outline_guidance": {
            "audience_description": "College students with programming foundation",
            "content_depth": "Combine theory and practice, include complexity analysis",
            "example_style": "Use course projects and interview question scenarios",
            "pacing_requirement": "Medium pace, appropriately skip basic concepts",
            "motivation_hook": "Introduce from practical problems, demonstrate practical value of algorithms",
            "ap_teaching_pattern": "Problem → Intuition → Execution Trace → Implementation → Complexity / Tradeoff → Generalization",
            "factuality_anchors": [],
            "zpd_bridge_strategy": "Start from a familiar problem scenario, then formalize into algorithmic thinking",
            "must_master_outcomes": ["Explain the core algorithm idea", "Reason about time and space complexity"],
            "likely_misconceptions": ["May memorize steps without understanding why the algorithm works"],
            "evidence_preference": _default_evidence_preference(normalized_subject),
        },
        "stage2_storyboard_guidance": _default_stage2_guidance(normalized_subject),
        "stage3_code_guidance": _default_stage3_guidance(normalized_subject),
    }


def _normalize_profile_schema(parsed: Dict[str, Any], subject: Optional[str]) -> Dict[str, Any]:
    normalized_subject = _normalize_subject(subject)
    defaults = _build_default_profile_schema(normalized_subject)

    user_summary = parsed.get("user_summary") if isinstance(parsed.get("user_summary"), dict) else {}
    stage1 = parsed.get("stage1_outline_guidance") if isinstance(parsed.get("stage1_outline_guidance"), dict) else {}
    stage2 = parsed.get("stage2_storyboard_guidance") if isinstance(parsed.get("stage2_storyboard_guidance"), dict) else {}
    stage3 = parsed.get("stage3_code_guidance") if isinstance(parsed.get("stage3_code_guidance"), dict) else {}

    normalized = {
        "user_summary": {
            "age_group": _coerce_string(user_summary.get("age_group"), defaults["user_summary"]["age_group"]),
            "background": _coerce_string(user_summary.get("background"), defaults["user_summary"]["background"]),
            "learning_goal": _coerce_string(user_summary.get("learning_goal"), defaults["user_summary"]["learning_goal"]),
            "target_language": _coerce_string(user_summary.get("target_language"), defaults["user_summary"]["target_language"]),
            "difficulty_preference": _coerce_string(user_summary.get("difficulty_preference"), defaults["user_summary"]["difficulty_preference"]),
            "ap_level": _coerce_string(user_summary.get("ap_level"), defaults["user_summary"]["ap_level"]),
            "zpd_prior_knowledge": _coerce_string(user_summary.get("zpd_prior_knowledge"), defaults["user_summary"]["zpd_prior_knowledge"]),
            "zpd_learning_target": _coerce_string(user_summary.get("zpd_learning_target"), defaults["user_summary"]["zpd_learning_target"]),
            "known_concepts": _coerce_list_of_strings(user_summary.get("known_concepts"), defaults["user_summary"]["known_concepts"]),
            "forbidden_jargon": _coerce_list_of_strings(user_summary.get("forbidden_jargon"), defaults["user_summary"]["forbidden_jargon"]),
        },
        "stage1_outline_guidance": {
            "audience_description": _coerce_string(stage1.get("audience_description"), defaults["stage1_outline_guidance"]["audience_description"]),
            "content_depth": _coerce_string(stage1.get("content_depth"), defaults["stage1_outline_guidance"]["content_depth"]),
            "example_style": _coerce_string(stage1.get("example_style"), defaults["stage1_outline_guidance"]["example_style"]),
            "pacing_requirement": _coerce_string(stage1.get("pacing_requirement"), defaults["stage1_outline_guidance"]["pacing_requirement"]),
            "motivation_hook": _coerce_string(stage1.get("motivation_hook"), defaults["stage1_outline_guidance"]["motivation_hook"]),
            "ap_teaching_pattern": _coerce_string(stage1.get("ap_teaching_pattern"), defaults["stage1_outline_guidance"]["ap_teaching_pattern"]),
            "factuality_anchors": _coerce_list_of_strings(stage1.get("factuality_anchors"), defaults["stage1_outline_guidance"]["factuality_anchors"]),
            "zpd_bridge_strategy": _coerce_string(stage1.get("zpd_bridge_strategy"), defaults["stage1_outline_guidance"]["zpd_bridge_strategy"]),
            "must_master_outcomes": _coerce_list_of_strings(stage1.get("must_master_outcomes"), defaults["stage1_outline_guidance"]["must_master_outcomes"]),
            "likely_misconceptions": _coerce_list_of_strings(stage1.get("likely_misconceptions"), defaults["stage1_outline_guidance"]["likely_misconceptions"]),
            "evidence_preference": _coerce_string(stage1.get("evidence_preference"), defaults["stage1_outline_guidance"]["evidence_preference"]),
        },
        "stage2_storyboard_guidance": {
            "visual_complexity": _coerce_string(stage2.get("visual_complexity"), defaults["stage2_storyboard_guidance"]["visual_complexity"]),
            "animation_pace": _coerce_string(stage2.get("animation_pace"), defaults["stage2_storyboard_guidance"]["animation_pace"]),
            "code_display_style": _coerce_string(stage2.get("code_display_style"), defaults["stage2_storyboard_guidance"]["code_display_style"]),
            "lecture_tone": _coerce_string(stage2.get("lecture_tone"), defaults["stage2_storyboard_guidance"]["lecture_tone"]),
            "emphasis_points": _coerce_string(stage2.get("emphasis_points"), defaults["stage2_storyboard_guidance"]["emphasis_points"]),
            "primary_visual_type": _coerce_string(stage2.get("primary_visual_type"), defaults["stage2_storyboard_guidance"]["primary_visual_type"]),
            "avoid_visual_types": _coerce_string(stage2.get("avoid_visual_types"), defaults["stage2_storyboard_guidance"]["avoid_visual_types"]),
            "max_new_terms_per_section": _coerce_positive_int(stage2.get("max_new_terms_per_section"), defaults["stage2_storyboard_guidance"]["max_new_terms_per_section"]),
            "retrieval_pause_frequency": _coerce_string(stage2.get("retrieval_pause_frequency"), defaults["stage2_storyboard_guidance"]["retrieval_pause_frequency"]),
        },
        "stage3_code_guidance": {
            "code_language": _coerce_string(stage3.get("code_language"), defaults["stage3_code_guidance"]["code_language"]),
            "code_style": _coerce_string(stage3.get("code_style"), defaults["stage3_code_guidance"]["code_style"]),
            "variable_naming": _coerce_string(stage3.get("variable_naming"), defaults["stage3_code_guidance"]["variable_naming"]),
            "comment_density": _coerce_string(stage3.get("comment_density"), defaults["stage3_code_guidance"]["comment_density"]),
            "complexity_handling": _coerce_string(stage3.get("complexity_handling"), defaults["stage3_code_guidance"]["complexity_handling"]),
            "visualization_strategy": _coerce_string(stage3.get("visualization_strategy"), defaults["stage3_code_guidance"]["visualization_strategy"]),
            "manim_objects_priority": _coerce_list_of_strings(stage3.get("manim_objects_priority"), defaults["stage3_code_guidance"]["manim_objects_priority"]),
        },
    }

    if normalized_subject in NON_CS_SUBJECTS:
        normalized["user_summary"]["target_language"] = "Not applicable"
        normalized["stage3_code_guidance"]["code_language"] = "Not applicable"

    return normalized



def get_profile_analysis_prompt(user_profile_text: str, subject: Optional[str] = None) -> str:
    """
    Generate prompt for AI to parse user profile text

    Args:
        user_profile_text: Natural language description input by user
        subject: Subject area for the lesson

    Returns:
        Prompt for AI to analyze user profile
    """
    normalized_subject = _normalize_subject(subject)
    subject_name = SUBJECT_DISPLAY_NAMES[normalized_subject]
    language_rule = (
        'Set `target_language` to "Not applicable" unless the user explicitly asks for a programming language.'
        if normalized_subject in NON_CS_SUBJECTS
        else 'Set `target_language` to the user\'s requested programming language, default to Python if not specified.'
    )
    code_display_style_hint = (
        "No code block should be required; focus on diagrams, formulas, labels, and process explanations."
        if normalized_subject in NON_CS_SUBJECTS
        else "No code blocks allowed; use flowcharts, data structure visualizations, and step-by-step natural language descriptions."
    )
    code_language_hint = _default_target_language(normalized_subject)
    return f"""
All output must be in English.

You are an educational video production expert. Please analyze the following user profile description, extract key information, and generate detailed guidance for teaching video production.

## Lesson Subject
{subject_name}

## User Profile Description
{user_profile_text}

## Important Rules
- **Difficulty level must strictly follow the user's explicit specification**. If the user description contains explicit difficulty requirements (such as "beginner", "intermediate", "advanced", "easy", "hard", etc.), you must adopt them as-is and must not adjust based on user background or learning goals.
- Difficulty mapping reference:
  - "easy"/"beginner"/"simple" → "beginner"
  - "intermediate"/"medium" → "intermediate"
  - "advanced"/"expert"/"hard" → "advanced"
- Only infer difficulty based on user background when the user has not mentioned difficulty at all.
- {language_rule}
- For non-computer-science subjects, avoid steering the profile toward coding practice unless the user explicitly requests it.

## Analyze and Output in JSON Format

Please output strictly in the following JSON format without any additional text:

{{
    "user_summary": {{
        "age_group": "Inferred age group from description (e.g., high school student/college student/graduate student/working professional)",
        "background": "Inferred knowledge background and existing foundation",
        "learning_goal": "User's learning objective",
        "target_language": "Programming language chosen by user (default {code_language_hint})",
        "difficulty_preference": "User's expected difficulty (beginner/intermediate/advanced)",
        "ap_level": "Calibration tier: AP / honors / standard / middle_school — infer from age, background, and goal",
        "zpd_prior_knowledge": "One concise sentence: what the learner provably already knows (infer from age, grade, background). E.g. 'Understands algebraic equations and basic function concepts'",
        "zpd_learning_target": "One concise sentence: the specific new conceptual step this video must close. E.g. 'Understand the geometric meaning of derivatives and differentiate simple polynomials'",
        "known_concepts": ["3-8 concepts the learner can already use confidently"],
        "forbidden_jargon": ["Terms that are above this learner's current level unless explicitly defined in plain English"]
    }},
    "stage1_outline_guidance": {{
        "audience_description": "One-sentence description of target audience for outline generation",
        "content_depth": "Content depth requirements (how deep to teach, what to skip)",
        "example_style": "Example style (what kind of examples help this user understand better)",
        "pacing_requirement": "Pacing requirements (fast/medium/slow, whether detailed explanation of each concept is needed)",
        "motivation_hook": "Opening introduction suggestion (what kind of scenario attracts this user)",
        "ap_teaching_pattern": "Subject-specific AP teaching sequence. Physics: Phenomenon → Driving Question → Model → Quantitative Example → Verification → Transfer. Biology: Big Idea → Essential Question → Observation → Mechanism → Broader Context → Application. CS: Problem → Intuition → Execution Trace → Implementation → Complexity → Generalization. Math: Numerical Intuition → Geometric Intuition → Formal Definition → Derivation → Worked Example → Transfer.",
        "factuality_anchors": ["List the exact key formulas, constants, laws, or terms for this topic that must appear verbatim and correctly. E.g. F=ma, g≈9.8 m/s², Avogadro's number 6.022×10²³"],
        "zpd_bridge_strategy": "How to explicitly activate prior knowledge before introducing new material. E.g. 'Start from the concept of slope that students already know, then transition to the idea of instantaneous rate of change'",
        "must_master_outcomes": ["2-4 measurable outcomes the learner should achieve by the end of the video"],
        "likely_misconceptions": ["Topic-specific misunderstandings this learner is likely to have"],
        "evidence_preference": "Preferred evidence style: definition / law / experiment / textbook theorem / worked example"
    }},
    "stage2_storyboard_guidance": {{
        "visual_complexity": "Visual complexity requirements (simple and clear/moderate/detailed and complex)",
        "animation_pace": "Animation pacing (pause time per step, whether repeated demonstration is needed)",
        "code_display_style": "{code_display_style_hint}",
        "lecture_tone": "Lecture tone style (casual and lively/professional and rigorous/patient and guiding)",
        "emphasis_points": "Content that particularly needs emphasis for this user",
        "primary_visual_type": "Dominant Manim visual category for this subject. Physics: vector_arrows, free_body_diagrams, motion_graphs. Biology: flow_diagrams, structure_diagrams, comparison_charts. CS: flowcharts, data_structure_diagrams, algorithm_step_boxes. Math: coordinate_planes, function_graphs, symbolic_transformations.",
        "avoid_visual_types": "Visual types inappropriate for this subject. E.g. all subjects should avoid code_blocks and code syntax displays; use diagrams and flowcharts instead.",
        "max_new_terms_per_section": 3,
        "retrieval_pause_frequency": "How often to add a brief pause/checkpoint for the learner, e.g. every 2 sections"
    }},
    "stage3_code_guidance": {{
        "code_language": "{code_language_hint}",
        "code_style": "Code style requirements (concise/detailed comments/show multiple approaches)",
        "variable_naming": "Variable naming style recommendation",
        "comment_density": "Comment density (high/medium/low)",
        "complexity_handling": "Complexity analysis depth (whether mathematical proof is needed)",
        "visualization_strategy": "Primary Manim strategy: diagram_first (physics/biology — use Arrow, Axes, flow diagrams), flowchart_first (CS — use RoundedRectangle boxes, Arrow connections, data structure visualizations with labeled nodes), symbolic_algebra (math — use MathTex transformations, NumberPlane, geometric constructions). No code blocks for any subject.",
        "manim_objects_priority": ["Ordered list of preferred Manim objects. Physics: Arrow, Vector, Axes, NumberPlane, MathTex. Biology: RoundedRectangle, Arrow, Circle, Text labels. CS: RoundedRectangle, Square, Circle, Arrow, MathTex (for Big-O), Graph. Math: NumberPlane, FunctionGraph, MathTex, Polygon, Angle"]
    }}
}}
"""


def get_stage1_profile_prompt(parsed_profile: Dict[str, Any]) -> str:
    """
    Generate Stage1 (Teaching Outline) user profile prompt fragment based on parsed user profile

    Args:
        parsed_profile: User profile dictionary parsed by AI

    Returns:
        User profile prompt for Stage1
    """
    summary = parsed_profile.get("user_summary", {})
    guidance = parsed_profile.get("stage1_outline_guidance", {})
    target_language = summary.get("target_language", "Not applicable")

    return f"""
## User Profile (AI Intelligent Analysis)

### Target Audience
- **Demographic**: {summary.get('age_group', 'Not specified')}
- **Knowledge Background**: {summary.get('background', 'Not specified')}
- **Learning Goal**: {summary.get('learning_goal', 'Not specified')}
- **Expected Difficulty**: {summary.get('difficulty_preference', 'intermediate')}
- **AP Level**: {summary.get('ap_level', 'standard')}
- **Programming Language**: {target_language}

### Zone of Proximal Development (ZPD)
- **Prior Knowledge (what the learner already knows)**: {summary.get('zpd_prior_knowledge', 'Not specified')}
- **Learning Target (new concept to master)**: {summary.get('zpd_learning_target', 'Not specified')}
- **Bridge Strategy**: {guidance.get('zpd_bridge_strategy', 'Start from what the learner already knows and build toward the new concept step by step')}

### Teaching Outline Design Guidance
- **Content Depth**: {guidance.get('content_depth', 'Moderate')}
- **Example Style**: {guidance.get('example_style', 'Relatable examples')}
- **Pacing Requirement**: {guidance.get('pacing_requirement', 'Medium pace')}
- **Opening Hook**: {guidance.get('motivation_hook', 'Use relatable scenarios for introduction')}
- **AP Teaching Pattern**: {guidance.get('ap_teaching_pattern', 'Not specified')}
- **Factuality Anchors**: {guidance.get('factuality_anchors', [])}
- **Known Concepts**: {summary.get('known_concepts', [])}
- **Forbidden Jargon**: {summary.get('forbidden_jargon', [])}
- **Must Master Outcomes**: {guidance.get('must_master_outcomes', [])}
- **Likely Misconceptions**: {guidance.get('likely_misconceptions', [])}
- **Evidence Preference**: {guidance.get('evidence_preference', 'definition / law / experiment / textbook theorem / worked example')}
"""


def get_stage2_profile_prompt(parsed_profile: Dict[str, Any]) -> str:
    """
    Generate Stage2 (Storyboard) user profile prompt fragment based on parsed user profile

    Args:
        parsed_profile: User profile dictionary parsed by AI

    Returns:
        User profile prompt for Stage2
    """
    summary = parsed_profile.get("user_summary", {})
    guidance = parsed_profile.get("stage2_storyboard_guidance", {})
    target_language = summary.get("target_language", "Not applicable")

    return f"""
## User Profile (AI Intelligent Analysis)

### Audience Characteristics
- **Target Audience**: {summary.get('age_group', 'Not specified')}
- **Knowledge Background**: {summary.get('background', 'Not specified')}
- **Programming Language**: {target_language}

### Zone of Proximal Development (ZPD)
- **Prior Knowledge**: {summary.get('zpd_prior_knowledge', 'Not specified')}
- **Learning Target**: {summary.get('zpd_learning_target', 'Not specified')}

### Storyboard Design Guidance
- **Visual Complexity**: {guidance.get('visual_complexity', 'Moderate')}
- **Animation Pace**: {guidance.get('animation_pace', 'Medium pace, pause at key steps')}
- **Code Display Style**: {guidance.get('code_display_style', 'Moderate comments, step-by-step explanation')}
- **Lecture Tone**: {guidance.get('lecture_tone', 'Clear and professional')}
- **Special Emphasis**: {guidance.get('emphasis_points', 'Core concepts and practical applications')}
- **Primary Visual Type**: {guidance.get('primary_visual_type', 'Not specified')}
- **Avoid Visual Types**: {guidance.get('avoid_visual_types', 'None')}
- **Max New Terms Per Section**: {guidance.get('max_new_terms_per_section', 3)}
- **Retrieval Pause Frequency**: {guidance.get('retrieval_pause_frequency', 'every 2 sections')}
"""


def get_stage3_profile_prompt(parsed_profile: Dict[str, Any]) -> str:
    """
    Generate Stage3 (Manim code generation) user profile prompt fragment based on parsed user profile

    Args:
        parsed_profile: User profile dictionary parsed by AI

    Returns:
        User profile prompt for Stage3
    """
    summary = parsed_profile.get("user_summary", {})
    guidance = parsed_profile.get("stage3_code_guidance", {})
    code_language = guidance.get('code_language', 'Not applicable')

    return f"""
## User Profile (AI Intelligent Analysis)

### Audience Characteristics
- **Target Audience**: {summary.get('age_group', 'Not specified')}
- **Knowledge Background**: {summary.get('background', 'Not specified')}
- **Expected Difficulty**: {summary.get('difficulty_preference', 'intermediate')}

### Zone of Proximal Development (ZPD)
- **Prior Knowledge**: {summary.get('zpd_prior_knowledge', 'Not specified')}
- **Learning Target**: {summary.get('zpd_learning_target', 'Not specified')}

### Manim Code Generation Guidance
- **Visualization Strategy**: {guidance.get('visualization_strategy', 'diagram_first')}
- **Preferred Manim Objects**: {guidance.get('manim_objects_priority', [])}
- **Code Display**: No code blocks or code syntax allowed for any subject; use flowcharts, diagrams, and data structure visualizations instead
"""


@dataclass
class UserProfile:
    """User Profile - Based on natural language description"""

    # Original user input
    raw_profile_text: str = ""

    # AI-parsed structured data
    parsed_profile: Optional[Dict[str, Any]] = None

    # User profile prompts for each stage (generated by AI)
    stage1_prompt: str = ""
    stage2_prompt: str = ""
    stage3_prompt: str = ""

    # Extracted key information (for direct access)
    target_language: str = "Python"
    subject: str = "computer_science"

    def __post_init__(self):
        self.subject = _normalize_subject(self.subject)
        self.target_language = _default_target_language(self.subject)
        """If there is raw text but no parsed result, set default values"""
        if self.raw_profile_text and not self.parsed_profile:
            # Set default parsed result
            self.parsed_profile = self._get_default_parsed_profile()
            self._generate_stage_prompts()

    def _default_ap_pattern(self) -> str:
        patterns = {
            "physics": "Phenomenon → Driving Question → Model Building → Quantitative Example → Verification / Edge Case → Transfer",
            "biology": "Big Idea → Essential Question → Observation / Case → Mechanism → Broader Context → Application",
            "math": "Numerical Intuition → Geometric Intuition → Formal Definition → Derivation / Proof Sketch → Worked Example → Transfer",
            "computer_science": "Problem → Intuition → Execution Trace → Implementation → Complexity / Tradeoff → Generalization",
        }
        return patterns.get(self.subject, "Concept Introduction → Core Explanation → Worked Example → Summary")

    def _default_primary_visual_type(self) -> str:
        types = {
            "physics": "vector_arrows, free_body_diagrams, motion_graphs, MathTex formulas",
            "biology": "flow_diagrams, structure_diagrams, comparison_charts, labeled processes",
            "math": "coordinate_planes, function_graphs, symbolic_transformations, geometric_constructions",
            "computer_science": "flowcharts, data_structure_diagrams, algorithm_step_boxes, labeled nodes",
        }
        return types.get(self.subject, "diagrams, labels, formulas")

    def _default_visualization_strategy(self) -> str:
        strategies = {
            "physics": "diagram_first",
            "biology": "diagram_first",
            "math": "symbolic_algebra",
            "computer_science": "flowchart_first",
        }
        return strategies.get(self.subject, "diagram_first")

    def _default_manim_objects(self) -> list:
        objects = {
            "physics": ["Arrow", "Vector", "Axes", "NumberPlane", "MathTex", "Dot"],
            "biology": ["RoundedRectangle", "Arrow", "Circle", "Ellipse", "Text", "MathTex"],
            "math": ["NumberPlane", "FunctionGraph", "MathTex", "Polygon", "Angle", "Axes"],
            "computer_science": ["RoundedRectangle", "Square", "Circle", "Arrow", "MathTex", "Graph"],
        }
        return objects.get(self.subject, ["MathTex", "Arrow", "Text", "RoundedRectangle"])

    def _get_default_parsed_profile(self) -> Dict[str, Any]:
        """Return default parsed result structure"""
        return _build_default_profile_schema(self.subject)
    
    def _generate_stage_prompts(self):
        """Generate prompts for each stage based on parsed results"""
        if self.parsed_profile:
            self.stage1_prompt = get_stage1_profile_prompt(self.parsed_profile)
            self.stage2_prompt = get_stage2_profile_prompt(self.parsed_profile)
            self.stage3_prompt = get_stage3_profile_prompt(self.parsed_profile)

            # Extract target language
            summary = self.parsed_profile.get("user_summary", {})
            self.target_language = summary.get("target_language") or _default_target_language(self.subject)

    def update_with_parsed_profile(self, parsed_profile: Dict[str, Any]):
        """Update user profile with AI-parsed results"""
        self.parsed_profile = parsed_profile
        self._generate_stage_prompts()

        # Update target language
        summary = parsed_profile.get("user_summary", {})
        self.target_language = summary.get("target_language") or _default_target_language(self.subject)

    def get_stage1_prompt(self) -> str:
        """Get user profile prompt for Stage1 (Teaching Outline generation)"""
        return self.stage1_prompt

    def get_stage2_prompt(self) -> str:
        """Get user profile prompt for Stage2 (Storyboard generation)"""
        return self.stage2_prompt

    def get_stage3_prompt(self) -> str:
        """Get user profile prompt for Stage3 (Manim code generation)"""
        return self.stage3_prompt

    def get_language(self) -> str:
        """Get target programming language"""
        return self.target_language

    def to_dict(self) -> dict:
        """Convert to dictionary format for serialization"""
        return {
            "raw_profile_text": self.raw_profile_text,
            "parsed_profile": self.parsed_profile,
            "target_language": self.target_language,
            "subject": self.subject,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "UserProfile":
        """Create UserProfile instance from dictionary"""
        profile = cls(
            raw_profile_text=data.get("raw_profile_text", ""),
            parsed_profile=data.get("parsed_profile"),
            target_language=data.get("target_language", "Python"),
            subject=data.get("subject", "computer_science"),
        )
        if profile.parsed_profile:
            profile._generate_stage_prompts()
        return profile


def get_default_profile(subject: Optional[str] = None) -> UserProfile:
    """Get default user profile"""
    normalized_subject = _normalize_subject(subject)
    if normalized_subject in NON_CS_SUBJECTS:
        default_text = f"I am a middle school or high school student learning {SUBJECT_DISPLAY_NAMES[normalized_subject]}, and I want a clear intermediate-level explanation with diagrams and examples."
    else:
        default_text = "I am a college student with some programming foundation, want to learn algorithms and data structures, using Python, difficulty level is intermediate."
    profile = UserProfile(raw_profile_text=default_text, subject=normalized_subject)
    return profile


def create_profile_from_text(profile_text: str, subject: Optional[str] = None) -> UserProfile:
    """
    Create user profile from natural language description (without calling AI, uses default structure)
    Actual AI parsing needs to be called in agent.py

    Args:
        profile_text: Natural language description input by user
        subject: Subject area for the lesson

    Returns:
        UserProfile instance (with default parsed result, needs subsequent AI update)
    """
    return UserProfile(raw_profile_text=profile_text, subject=_normalize_subject(subject))


def parse_profile_with_ai_sync(
    profile_text: str,
    api_function: Callable,
    max_retries: int = 5,
    subject: Optional[str] = None
) -> Dict[str, Any]:
    """
    Parse user profile text using AI (synchronous version with retry mechanism)

    Args:
        profile_text: Natural language description input by user
        api_function: API call function
        max_retries: Maximum retry attempts, default 5

    Returns:
        Parsed user profile dictionary
    """
    import json
    import time

    prompt = get_profile_analysis_prompt(profile_text, subject=subject)

    for attempt in range(1, max_retries + 1):
        try:
            print(f"🔄 Parsing user profile (attempt {attempt}/{max_retries})...")

            response, _ = api_function(prompt, max_tokens=4000)

            if response is None:
                print(f"⚠️ Attempt {attempt}: API returned empty response")
                if attempt < max_retries:
                    time.sleep(1)  # Wait 1 second before retry
                continue

            # Try to extract text from response
            try:
                content = response.candidates[0].content.parts[0].text
            except Exception:
                try:
                    content = response.choices[0].message.content
                except Exception:
                    content = str(response)

            # Extract JSON
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            # Try to parse JSON
            parsed = json.loads(content)
            parsed = _normalize_profile_schema(parsed, subject)

            # Validate parsed result contains necessary fields
            if all(key in parsed for key in ("user_summary", "stage1_outline_guidance", "stage2_storyboard_guidance", "stage3_code_guidance")):
                return parsed
            else:
                print(f"⚠️ Attempt {attempt}: Parsed result missing required fields")
                if attempt < max_retries:
                    time.sleep(1)
                continue

        except json.JSONDecodeError as e:
            print(f"⚠️ Attempt {attempt}: JSON parsing error - {e}")
            if attempt < max_retries:
                time.sleep(1)
            continue
        except Exception as e:
            print(f"⚠️ Attempt {attempt}: Parsing failed - {e}")
            if attempt < max_retries:
                time.sleep(1)
            continue

    print(f"❌ AI user profile parsing failed after {max_retries} attempts")
    return None
