"""
User Profile Configuration Module
Supports generating customized video content through natural language descriptions
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any, Callable


# ============ AI User Profile Analysis Prompts ============

def get_profile_analysis_prompt(user_profile_text: str) -> str:
    """
    Generate prompt for AI to parse user profile text

    Args:
        user_profile_text: Natural language description input by user

    Returns:
        Prompt for AI to analyze user profile
    """
    return f"""
All output must be in English.

You are an educational video production expert. Please analyze the following user profile description, extract key information, and generate detailed guidance for teaching video production.

## User Profile Description
{user_profile_text}

## Important Rules
- **Difficulty level must strictly follow the user's explicit specification**. If the user description contains explicit difficulty requirements (such as "beginner", "intermediate", "advanced", "easy", "hard", etc.), you must adopt them as-is and must not adjust based on user background or learning goals.
- Difficulty mapping reference:
  - "easy"/"beginner"/"simple" → "beginner"
  - "intermediate"/"medium" → "intermediate"
  - "advanced"/"expert"/"hard" → "advanced"
- Only infer difficulty based on user background when the user has not mentioned difficulty at all.

## Analyze and Output in JSON Format

Please output strictly in the following JSON format without any additional text:

{{
    "user_summary": {{
        "age_group": "Inferred age group from description (e.g., high school student/college student/graduate student/working professional)",
        "background": "Inferred knowledge background and existing foundation",
        "learning_goal": "User's learning objective",
        "target_language": "Programming language chosen by user (default to Python if not specified)",
        "difficulty_preference": "User's expected difficulty (beginner/intermediate/advanced)"
    }},
    "stage1_outline_guidance": {{
        "audience_description": "One-sentence description of target audience for outline generation",
        "content_depth": "Content depth requirements (how deep to teach, what to skip)",
        "example_style": "Example style (what kind of examples help this user understand better)",
        "pacing_requirement": "Pacing requirements (fast/medium/slow, whether detailed explanation of each concept is needed)",
        "motivation_hook": "Opening introduction suggestion (what kind of scenario attracts this user)"
    }},
    "stage2_storyboard_guidance": {{
        "visual_complexity": "Visual complexity requirements (simple and clear/moderate/detailed and complex)",
        "animation_pace": "Animation pacing (pause time per step, whether repeated demonstration is needed)",
        "code_display_style": "Code display style (how many comments, whether line-by-line explanation)",
        "lecture_tone": "Lecture tone style (casual and lively/professional and rigorous/patient and guiding)",
        "emphasis_points": "Content that particularly needs emphasis for this user"
    }},
    "stage3_code_guidance": {{
        "code_language": "Code language",
        "code_style": "Code style requirements (concise/detailed comments/show multiple approaches)",
        "variable_naming": "Variable naming style recommendation",
        "comment_density": "Comment density (high/medium/low)",
        "complexity_handling": "Complexity analysis depth (whether mathematical proof is needed)"
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

    return f"""
## User Profile (AI Intelligent Analysis)

### Target Audience
- **Demographic**: {summary.get('age_group', 'Not specified')}
- **Knowledge Background**: {summary.get('background', 'Not specified')}
- **Learning Goal**: {summary.get('learning_goal', 'Not specified')}
- **Expected Difficulty**: {summary.get('difficulty_preference', 'intermediate')}
- **Programming Language**: {summary.get('target_language', 'Python')}

### Teaching Outline Design Guidance
- **Content Depth**: {guidance.get('content_depth', 'Moderate')}
- **Example Style**: {guidance.get('example_style', 'Relatable examples')}
- **Pacing Requirement**: {guidance.get('pacing_requirement', 'Medium pace')}
- **Opening Hook**: {guidance.get('motivation_hook', 'Use relatable scenarios for introduction')}
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

    return f"""
## User Profile (AI Intelligent Analysis)

### Audience Characteristics
- **Target Audience**: {summary.get('age_group', 'Not specified')}
- **Knowledge Background**: {summary.get('background', 'Not specified')}
- **Programming Language**: {summary.get('target_language', 'Python')}

### Storyboard Design Guidance
- **Visual Complexity**: {guidance.get('visual_complexity', 'Moderate')}
- **Animation Pace**: {guidance.get('animation_pace', 'Medium pace, pause at key steps')}
- **Code Display Style**: {guidance.get('code_display_style', 'Moderate comments, step-by-step explanation')}
- **Lecture Tone**: {guidance.get('lecture_tone', 'Clear and professional')}
- **Special Emphasis**: {guidance.get('emphasis_points', 'Core concepts and practical applications')}
"""


def get_stage3_profile_prompt(parsed_profile: Dict[str, Any]) -> str:
    """
    Generate Stage3 (Manim code generation) user profile prompt fragment based on parsed user profile

    Args:
        parsed_profile: User profile dictionary parsed by AI

    Returns:
        User profile prompt for Stage3
    """
    summary = parsed_profile.get("user_summary", )
    guidance = parsed_profile.get("stage3_code_guidance", {})

    return f"""
## User Profile (AI Intelligent Analysis)

### Audience Characteristics
- **Target Audience**: {summary.get('age_group', 'Not specified')}
- **Knowledge Background**: {summary.get('background', 'Not specified')}
- **Expected Difficulty**: {summary.get('difficulty_preference', 'intermediate')}

### Manim Code Generation Guidance
- **Code Language**: {guidance.get('code_language', 'Python')}
- **Code Style**: {guidance.get('code_style', 'Clear and readable, moderate comments')}
- **Variable Naming**: {guidance.get('variable_naming', 'Semantic naming')}
- **Comment Density**: {guidance.get('comment_density', 'Medium')}
- **Complexity Analysis**: {guidance.get('complexity_handling', 'Brief explanation, no deep mathematical proof')}
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

    def __post_init__(self):
        """If there is raw text but no parsed result, set default values"""
        if self.raw_profile_text and not self.parsed_profile:
            # Set default parsed result
            self.parsed_profile = self._get_default_parsed_profile()
            self._generate_stage_prompts()

    def _get_default_parsed_profile(self) -> Dict[str, Any]:
        """Return default parsed result structure"""
        return {
            "user_summary": {
                "age_group": "College/Graduate student",
                "background": "Some programming foundation",
                "learning_goal": "Learn algorithms and data structures",
                "target_language": "Python",
                "difficulty_preference": "advanced"
            },
            "stage1_outline_guidance": {
                "audience_description": "College students with programming foundation",
                "content_depth": "Combine theory and practice, include complexity analysis",
                "example_style": "Use course projects and interview question scenarios",
                "pacing_requirement": "Medium pace, appropriately skip basic concepts",
                "motivation_hook": "Introduce from practical problems, demonstrate practical value of algorithms"
            },
            "stage2_storyboard_guidance": {
                "visual_complexity": "Moderate, detailed display of key steps",
                "animation_pace": "Medium pace, pause and explain at key steps",
                "code_display_style": "Include necessary comments, show standard implementation",
                "lecture_tone": "Professional but understandable",
                "emphasis_points": "Core algorithm ideas and implementation techniques"
            },
            "stage3_code_guidance": {
                "code_language": "Python",
                "code_style": "Pythonic style, clear and readable",
                "variable_naming": "Semantic naming, follow PEP8",
                "comment_density": "Medium, comments at key steps",
                "complexity_handling": "Brief explanation of time and space complexity"
            }
        }
    
    def _generate_stage_prompts(self):
        """Generate prompts for each stage based on parsed results"""
        if self.parsed_profile:
            self.stage1_prompt = get_stage1_profile_prompt(self.parsed_profile)
            self.stage2_prompt = get_stage2_profile_prompt(self.parsed_profile)
            self.stage3_prompt = get_stage3_profile_prompt(self.parsed_profile)

            # Extract target language
            summary = self.parsed_profile.get("user_summary", {})
            self.target_language = summary.get("target_language", "Python")

    def update_with_parsed_profile(self, parsed_profile: Dict[str, Any]):
        """Update user profile with AI-parsed results"""
        self.parsed_profile = parsed_profile
        self._generate_stage_prompts()

        # Update target language
        summary = parsed_profile.get("user_summary", {})
        self.target_language = summary.get("target_language", "Python")

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
            "target_language": self.target_language
        }

    @classmethod
    def from_dict(cls, data: dict) -> "UserProfile":
        """Create UserProfile instance from dictionary"""
        profile = cls(
            raw_profile_text=data.get("raw_profile_text", ""),
            parsed_profile=data.get("parsed_profile"),
            target_language=data.get("target_language", "Python")
        )
        if profile.parsed_profile:
            profile._generate_stage_prompts()
        return profile


def get_default_profile() -> UserProfile:
    """Get default user profile"""
    default_text = "I am a college student with some programming foundation, want to learn algorithms and data structures, using Python, difficulty level is intermediate."
    profile = UserProfile(raw_profile_text=default_text)
    return profile


def create_profile_from_text(profile_text: str) -> UserProfile:
    """
    Create user profile from natural language description (without calling AI, uses default structure)
    Actual AI parsing needs to be called in agent.py

    Args:
        profile_text: Natural language description input by user

    Returns:
        UserProfile instance (with default parsed result, needs subsequent AI update)
    """
    return UserProfile(raw_profile_text=profile_text)


def parse_profile_with_ai_sync(
    profile_text: str,
    api_function: Callable,
    max_retries: int = 5
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

    prompt = get_profile_analysis_prompt(profile_text)

    for attempt in range(1, max_retries + 1):
        try:
            print(f"🔄 Parsing user profile (attempt {attempt}/{max_retries})...")

            response, _ = api_function(prompt, max_tokens=2000)

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

            # Validate parsed result contains necessary fields
            if "user_summary" in parsed and "stage1_outline_guidance" in parsed:
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
