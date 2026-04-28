# prompts/stage5_eva.py
import json

def get_prompt_aes(knowledge_point):
    # Context prefix
    prefix = ""
    if knowledge_point:
        prefix = f"""
**Knowledge Point Background:**
This educational video aims to teach: "{knowledge_point}"

Please specifically evaluate the effectiveness of this video in teaching this particular knowledge point. Consider whether its content, animations, and presentation style are appropriate for conveying this specific concept.
"""

    return f"""
You are an educational content evaluation expert specializing in instructional videos, particularly skilled at analyzing videos that contain synchronized presentations and animations. Please conduct an in-depth analysis of the provided educational video from five key dimensions and provide detailed scores.

{prefix}

**EVALUATION FRAMEWORK:**

**1. Element Layout - 20 points**
Evaluate the spatial arrangement and organization of visual elements:
- Clarity and readability of the left-side presentation (text/diagrams)
- Optimal positioning and sizing of right-side animation content
- Balance between presentation area and animation area
- Appropriate use of whitespace and visual hierarchy
- Consistency in font size, color, and element positioning
- Overall aesthetics and professional appearance

**2. Attractiveness - 20 points**
Evaluate visual appeal and engagement factors:
- Harmony of color scheme and its suitability for educational content
- Quality of visual design and modern aesthetics
- Engaging animation style and effects
- Creative use of visual metaphors and illustrations
- Ability to capture and maintain learner attention

**3. Logical Flow - 20 points**
Analyze instructional structure and content progression:
- Clear introduction, development, and summary of concepts
- Logical sequence of information presentation
- Smooth transitions between topics and concepts
- Appropriate pacing for learning comprehension
- Coherent connection between presentation content and animations
- Progressive complexity building (scaffolded instruction)

**4. Accuracy and Depth - 20 points**
Evaluate content quality and educational value:
- Factual correctness of all presented information
- Appropriate depth and complexity for the knowledge point
- Comprehensive coverage of key concepts in the knowledge point
- Clarity of explanations and concept definitions
- Effectiveness of examples and illustrations supporting the knowledge point
- Alignment of video content with intended learning objectives

**5. Visual Consistency - 20 points**
Evaluate overall unity and coherence:
- Consistency of visual style across all elements
- Unified color palette and design language
- Coherent animation style and timing
- Consistent typography and formatting
- Smooth integration between static and dynamic elements

**Scoring Instructions:**
- Provide a score for each dimension (decimals allowed)
- Calculate the total score
- Provide specific English feedback for each dimension
- Evaluate whether the video effectively teaches the specified knowledge point

**Response Format:**
Must strictly output in the following JSON format:

{{
"element_layout": {{
    "score": [0-20],
    "feedback": "Detailed English analysis of layout quality..."
}},
"attractiveness": {{
    "score": [0-20],
    "feedback": "Evaluation of visual appeal..."
}},
"logic_flow": {{
    "score": [0-20],
    "feedback": "Analysis of instructional structure..."
}},
"accuracy_depth": {{
    "score": [0-20],
    "feedback": "Evaluation of content quality..."
}},
"visual_consistency": {{
    "score": [0-20],
    "feedback": "Evaluation of visual unity..."
}},
"overall_score": [0-100],
"summary": "Overall evaluation and key recommendations...",
"strengths": ["List of notable strengths"],
"improvements": ["List of suggested improvements"]
}}
"""


def get_prompt_competition_rubric(knowledge_point, subject_domain=None):
    """
    Competition-aligned evaluation rubric with four dimensions matching the judging criteria:
    (1) Factual Accuracy & Evidence Basis
    (2) Pedagogical Logic & Scaffolding
    (3) Learner Adaptation & ZPD Fit
    (4) Engagement & Multimodal Consistency
    """
    subject_hint = ""
    if subject_domain:
        subject_map = {
            "physics": "Physics (AP Physics 1/C reference)",
            "biology": "Biology (AP Biology reference)",
            "math": "Mathematics (AP Calculus/Statistics reference)",
            "computer_science": "Computer Science (AP CS A/Principles reference)",
        }
        subject_hint = f"\n**Subject Domain:** {subject_map.get(subject_domain, subject_domain)}\n"

    prefix = ""
    if knowledge_point:
        prefix = f"""
**Knowledge Point:** "{knowledge_point}"
{subject_hint}
Please evaluate this educational video specifically for its effectiveness in teaching this knowledge point, using the AP curriculum as a reference standard for content depth and accuracy.
"""

    return f"""
You are an expert educational content judge evaluating a teaching video for a competition. Apply the following four-criterion rubric strictly. Each criterion is scored out of 25 points (total 100).

{prefix}

**EVALUATION RUBRIC:**

**1. Factual Accuracy & Evidence Basis — 25 points**
This is the non-negotiable foundation of teaching quality.

- **Zero-Hallucination Check (0-10):** Are ALL technical terms, formulas, derivation steps, historical data, constants, and code examples exactly correct? Any fabricated, misleading, or approximately-correct information is a critical failure. Score 0 if any hallucinated fact is found.
- **Knowledge Depth & Verification (0-8):** Does the content reach core principles rather than just surface-level term-stacking? Are referenced academic cases, experiments, or examples real and highly relevant to the topic?
- **Citation & Attribution (0-7):** Are external facts properly attributed to their source concepts (e.g., "from Newton's Second Law", "by the Central Limit Theorem")? No plagiarism or copyright violations.

**2. Pedagogical Logic & Scaffolding — 25 points**
Evaluates the structural quality of knowledge delivery.

- **Scaffolding Construction (0-12):** Does the video follow a "simple to complex" progression? Does it start from concepts the learner already knows and gradually build bridges to new knowledge? Or does it abruptly jump to advanced concepts?
- **Narrative Coherence (0-8):** Are transitions between paragraphs/sections natural and smooth? Do knowledge points interlock to form a complete logical chain, rather than fragmented information assembly?
- **AP Pattern Compliance (0-5):** Does the teaching structure follow the AP-standard pattern for this subject? (Physics: Phenomenon→Model→Predict→Verify; Biology: BigIdea→Mechanism→Application; Math: Intuition→Definition→Derivation→Example; CS: Problem→Trace→Implement→Analyze)

**3. Learner Adaptation & ZPD Fit — 25 points**
Evaluates the system's understanding of and response to the learner profile.

- **Zone of Proximal Development Recognition (0-10):** Does the AI accurately identify the learner's knowledge boundary? (e.g., for a high school student who only knows algebra, the system should avoid unexplained partial differential equations and instead use intuitive geometric illustrations.)
- **Language & Analogy Calibration (0-9):** Are the explanation style, vocabulary depth, and examples appropriate for the target audience's life experience and cognitive level?
- **Prior Knowledge Activation (0-6):** Does each new concept section begin by connecting to something the learner already knows? Is the progression from known to unknown explicit?

**4. Engagement & Multimodal Consistency — 25 points**
Evaluates the material's attractiveness and delivery efficiency.

- **Narrative Appeal (0-7):** Does the video weave dry knowledge into vivid cases or metaphors? Does it spark learning motivation and create an intrinsic drive to "keep watching"?
- **Cognitive Focus Maintenance (0-8):** Does the video employ effective teaching strategies (suspense design, Socratic questioning, periodic mini-summaries) to maintain high-intensity attention and avoid monotonous one-way output?
- **Multimodal Alignment (0-10):** Do the visual elements (diagrams, animations, cursor traces) and audio narration synchronize and reinforce each other? Visuals should not be mere decoration — they must concretely aid understanding of abstract concepts (e.g., when discussing matrix rotation, the screen should simultaneously show a rotation animation).

**Scoring Instructions:**
- Provide a score for each sub-criterion and each main dimension
- Calculate the total score out of 100
- Provide specific English feedback for each dimension
- Flag any factual errors found (list them explicitly)
- Note any instances where narration and visuals are misaligned

**Response Format:**
Must strictly output in the following JSON format:

{{
"factual_accuracy": {{
    "zero_hallucination": {{"score": "[0-10]", "feedback": "..."}},
    "knowledge_depth": {{"score": "[0-8]", "feedback": "..."}},
    "citation_attribution": {{"score": "[0-7]", "feedback": "..."}},
    "dimension_score": "[0-25]",
    "factual_errors_found": ["List any specific factual errors detected, or empty if none"]
}},
"pedagogical_logic": {{
    "scaffolding": {{"score": "[0-12]", "feedback": "..."}},
    "narrative_coherence": {{"score": "[0-8]", "feedback": "..."}},
    "ap_pattern_compliance": {{"score": "[0-5]", "feedback": "..."}},
    "dimension_score": "[0-25]"
}},
"learner_adaptation": {{
    "zpd_recognition": {{"score": "[0-10]", "feedback": "..."}},
    "language_calibration": {{"score": "[0-9]", "feedback": "..."}},
    "prior_knowledge_activation": {{"score": "[0-6]", "feedback": "..."}},
    "dimension_score": "[0-25]"
}},
"engagement_multimodal": {{
    "narrative_appeal": {{"score": "[0-7]", "feedback": "..."}},
    "cognitive_focus": {{"score": "[0-8]", "feedback": "..."}},
    "multimodal_alignment": {{"score": "[0-10]", "feedback": "..."}},
    "dimension_score": "[0-25]"
}},
"overall_score": "[0-100]",
"summary": "Overall evaluation and key recommendations...",
"strengths": ["List of notable strengths"],
"critical_issues": ["List of critical issues that must be fixed, especially any factual errors or major pedagogical gaps"]
}}
"""