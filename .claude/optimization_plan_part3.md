# 优化方案详细设计 - Part 3

## 五、具体优化方案（基于v5）

### 方案A：术语即时定义系统（优先级：高）

#### **目标**
在术语首次出现时，自动插入简短定义，减少术语密度惩罚

#### **实施位置**
`src/audio_steps.py` 的 `expand_screen_text_to_spoken_script()` 函数

#### **实施方法**

**步骤1：建立术语词典**
```python
# 在 audio_steps.py 顶部添加
TERMINOLOGY_DICT = {
    "biology": {
        "heuristic": "rule-driven approach",
        "inference engine": "reasoning system",
        "translocation": "two-way transport",
        "lignin": "rigid cell wall material",
        "meiosis": "cell division that produces sex cells",
        "chromosome": "DNA package",
    },
    "math": {
        "marginal": "step-by-step change",
        "tangent line": "flat line touching the curve",
        "vertex": "highest or lowest point",
        "derivative": "rate of change",
    },
    "statistics": {
        "MSE": "Mean Squared Error",
        "Ridge": "penalty method that shrinks coefficients",
        "Lasso": "penalty method that zeros out coefficients",
        "homoscedasticity": "equal variance",
    },
    "physics": {
        "kinematic": "motion-related",
        "invariant": "unchanging quantity",
    },
    "computer_science": {
        "heuristic": "rule of thumb",
        "inference": "logical reasoning",
    }
}
```

**步骤2：修改expand_screen_text_to_spoken_script()函数**
```python
def expand_screen_text_to_spoken_script(
    screen_text: str,
    api_func: Callable,
    max_retries: int = 3,
    max_tokens: int = 300,
    user_profile: Optional['UserProfile'] = None,
    subject: str = "computer_science",
) -> str:
    # ... 现有代码 ...
    
    # 新增：术语检测和定义插入
    terminology_hints = _detect_and_define_terms(screen_text, subject, grade_level)
    
    if terminology_hints:
        terminology_instruction += f"\n\n**Terminology Definitions (MANDATORY):**\n{terminology_hints}"
    
    # ... 其余代码保持不变 ...
```

**步骤3：添加术语检测函数**
```python
def _detect_and_define_terms(text: str, subject: str, grade_level: str) -> str:
    """检测文本中的术语并返回定义提示"""
    subject_terms = TERMINOLOGY_DICT.get(subject, {})
    found_terms = []
    
    for term, definition in subject_terms.items():
        if term.lower() in text.lower():
            found_terms.append(f"- When you say '{term}', add: '({definition})'")
    
    if found_terms:
        return "\n".join(found_terms)
    return ""
```

#### **预期效果**
- 术语密度惩罚：-0.5 → -0.1（减少0.4分损失）
- 适配度提升：4.0-4.2 → 4.4-4.6

---

### 方案B：公式引入缓冲机制（优先级：高）

#### **目标**
在复杂公式出现前，增加过渡句，减少数学符号惩罚

#### **实施位置**
1. `prompts/stage2.py` - 增加公式检测指令
2. `src/audio_steps.py` - 在TTS生成时增加停顿

#### **实施方法**

**步骤1：修改stage2.py的prompt**
在`get_prompt2_storyboard()`函数中添加：
```python
# 在现有prompt中添加公式缓冲指令
formula_buffer_instruction = """
**Formula Introduction Protocol (MANDATORY):**
- Before introducing a complex formula (LaTeX with Greek letters, summation, fractions):
  1. Add a transition lecture_line: "Let's express this mathematically" or "The formula looks like this"
  2. Mark the formula line with a special flag: `formula_needs_buffer: true`
- Examples:
  - Before MSE formula: "Now, let's see the mathematical form of Mean Squared Error"
  - Before Ridge/Lasso: "Mathematically, we add a penalty term to the equation"
"""
```
