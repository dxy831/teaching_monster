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
You are an educational content evaluation expert specializing in instructional videos, particularly skilled at analyzing videos that contain synchronized presentations and animations. Please conduct an in-depth analysis of the provided educational video from six key dimensions and provide detailed scores.

{prefix}

**EVALUATION FRAMEWORK:**

**1. Element Layout - 20 points**
Evaluate the spatial arrangement and organization of visual elements:
- Clarity and readability of the left-side presentation (text/diagrams)
- Whether lecture lines on the left are blocked, crowded, or visually obstructed by animation elements
- Whether animation elements, formulas, labels, and shapes overlap in a way that harms readability
- Whether any element is off-screen, clipped, or visibly cut off
- Whether labels stay close enough to their corresponding objects to remain understandable
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
- Whether each section introduces only one core new concept
- Whether each section clearly bridges from prior knowledge to the next target idea
- Whether the video makes clear *why the next idea is needed*, not just what comes next
- Whether the explanation shows a limitation, unanswered question, or motivation before introducing a new method, mechanism, or representation
- Whether a unified example or recurring case helps hold the progression together rather than presenting disconnected facts

**4. Accuracy and Depth - 20 points**
Evaluate content quality and educational value:
- Factual correctness of all presented information
- Appropriate depth and complexity for the knowledge point
- Comprehensive coverage of key concepts in the knowledge point
- Clarity of explanations and concept definitions
- Effectiveness of examples and illustrations supporting the knowledge point
- Alignment of video content with intended learning objectives
- Whether major claims are explicitly supported by a definition, law, theorem, experiment, or worked-example rule
- Whether formulas, laws, terminology, and quantitative statements remain textbook-correct throughout
- Whether analogies are clearly framed as intuition-building aids rather than full formal definitions
- Whether the explanation avoids turning a helpful simplification into a misleading or false claim

**5. Learner Fit & ZPD - 20 points**
Evaluate adaptation to the intended learner:
- Whether the explanation activates prior knowledge before introducing a new concept
- Whether terminology matches the learner's likely age and background
- Whether new vocabulary load stays manageable for the target learner
- Whether analogies, pacing, and examples are appropriate for the learner profile
- Whether misconceptions are proactively addressed before they become confusion
- Whether unfamiliar abstract terms are first introduced through plain-language intuition before formal wording
- Whether the section gives the learner enough cognitive buffer before stacking another new abstraction

**6. Visual Consistency - 20 points**
Evaluate overall unity and coherence:
- Consistency of visual style across all elements
- Unified color palette and design language
- Coherent animation style and timing
- Consistent typography and formatting
- Smooth integration between static and dynamic elements

**Scoring Instructions:**
- Provide a score for each dimension (decimals allowed)
- Calculate the total score out of 120
- Provide specific English feedback for each dimension
- Evaluate whether the video effectively teaches the specified knowledge point
- Decide whether this section is already good enough to stop further optimization
- Treat the following as hard blockers that prevent `is_good_enough=true`: lecture-line obstruction, readability-harming overlap, off-screen clipping, obvious rendering failure, severely crowded layout, unsupported factual claims, age-inappropriate unexplained jargon, or broken instructional scaffolding
- For abstract or technical topics, a section is NOT good enough if it does not explain why the next idea is needed, introduces unfamiliar abstract terms without a plain-language bridge, or stacks too many new ideas before the learner has processed the previous one
- Use `critical_failures` for severe pedagogy/factuality problems even if visuals are acceptable
- Minor polish suggestions are allowed even when the section is already good enough

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
    "feedback": "Analysis of instructional structure...",
    "scaffold_continuity_feedback": "Comment on prior-knowledge activation, transition quality, one-concept-per-section discipline, and whether the video clearly explains why the next idea is needed.",
    "causal_bridge_feedback": "State whether each major transition is motivated by a limitation, unanswered question, or need that makes the next idea feel necessary."
}},
"accuracy_depth": {{
    "score": [0-20],
    "feedback": "Evaluation of content quality...",
    "unsupported_claim_count": 0,
    "anchor_coverage_summary": "Explain how well the video grounds its key claims in named definitions, laws, theorems, experiments, or textbook rules.",
    "analogy_boundary_feedback": "State whether analogies are clearly separated from strict definitions and whether any simplification becomes misleading."
}},
"learner_fit_zpd": {{
    "score": [0-20],
    "feedback": "Evaluation of learner adaptation and ZPD fit...",
    "jargon_bridge_feedback": "State whether unfamiliar abstract terms are introduced only after a plain-language bridge and whether learner load stays manageable."
}},
"visual_consistency": {{
    "score": [0-20],
    "feedback": "Evaluation of visual unity..."
}},
"overall_score": [0-120],
"is_good_enough": true,
"good_enough_reason": "Explain briefly why this section should or should not stop further optimization.",
"hard_blockers": ["List hard blockers such as obstruction, overlap, clipping, rendering failure, severe crowding, unsupported factual claims, or broken scaffolding. Use an empty list when none exist."],
"critical_failures": ["List severe pedagogy/factuality failures such as unsupported factual claims, multiple new concepts packed together, learner-inappropriate jargon, or missing transitions. Use an empty list when none exist."],
"summary": "Overall evaluation and key recommendations...",
"strengths": ["List of notable strengths"],
"improvements": ["List of suggested improvements"]
}}
"""
