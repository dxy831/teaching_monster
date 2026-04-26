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