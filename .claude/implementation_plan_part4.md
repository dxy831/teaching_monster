# 实施计划与代码修改指南 - Part 4

## 六、实施计划（分阶段）

### Phase 1：术语定义系统（低风险高收益）

#### **修改文件1：src/audio_steps.py**

**位置1：在文件顶部添加术语词典（约第30行后）**
```python
# 在 TTS_MODEL_MAX_WORKERS = 16 后添加

# ── Terminology Dictionary for Instant Definitions ──────────────────
TERMINOLOGY_DICT = {
    "biology": {
        "heuristic": "rule-driven approach",
        "inference engine": "reasoning system",
        "translocation": "two-way transport",
        "lignin": "rigid cell wall material",
        "meiosis": "cell division that produces sex cells",
        "chromosome": "DNA package",
        "polyploidy": "chromosome doubling",
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

**位置2：添加术语检测函数（约第220行，在expand_screen_text_to_spoken_script之前）**
```python
def _detect_and_define_terms(text: str, subject: str, grade_level: str) -> str:
    """
    检测文本中的术语并返回定义提示
    
    Args:
        text: 屏幕文本
        subject: 学科
        grade_level: 年级水平
    
    Returns:
        术语定义提示字符串
    """
    subject_terms = TERMINOLOGY_DICT.get(subject, {})
    found_terms = []
    
    text_lower = text.lower()
    for term, definition in subject_terms.items():
        if term.lower() in text_lower:
            # 根据年级调整定义方式
            if grade_level == "middle_school":
                found_terms.append(f"- When you say '{term}', immediately add: 'which means {definition}'")
            elif grade_level == "high_school":
                found_terms.append(f"- When you say '{term}', add: '({definition})'")
            else:  # ap_college
                found_terms.append(f"- When you say '{term}', briefly add: '{definition}'")
    
    if found_terms:
        return "\n".join(found_terms)
    return ""
```

**位置3：修改expand_screen_text_to_spoken_script函数（约第175行）**
在构建terminology_instruction之后，添加：
```python
    # 新增：术语检测和定义插入
    terminology_hints = _detect_and_define_terms(screen_text, subject, grade_level)
    
    if terminology_hints:
        terminology_instruction += f"\n\n**Detected Terms - Add Definitions:**\n{terminology_hints}"
```

---

### Phase 2：公式缓冲机制（中等风险中等收益）

#### **修改文件2：prompts/stage2.py**

**位置：在get_prompt2_storyboard函数中（约第85行，在Terminology Calibration之后）**
```python
    # 在现有的 Terminology Calibration 部分之后添加
    
    # 🔴 Formula Introduction Protocol (MANDATORY)
    
    **Before introducing complex formulas:**
    - Complex formula = LaTeX with Greek letters, summation (Σ), fractions, or multiple variables
    - Add a transition lecture_line BEFORE the formula line:
      - "Let's express this mathematically"
      - "The formula looks like this"
      - "Mathematically, we can write"
    - Examples:
      - Before MSE formula: "Now, let's see the mathematical form"
      - Before Ridge/Lasso: "We add a penalty term to the equation"
      - Before chromosome notation: "In genetic notation, we write this as"
```

---

### Phase 3：认知检查点（中等风险）

#### **修改文件3：src/agent.py**

**位置：在build_section_steps函数中（需要先定位zpd_check_line_index的使用位置）**

查找zpd_check_line_index的使用：
```bash
grep -n "zpd_check_line" src/agent.py
```

在对应位置添加认知检查点逻辑。

---

## 七、测试验证计划

### 7.1 测试用例

使用3个典型视频的原始输入重新生成：
1. 進化（1）- 当前适配度4.0，目标4.5+
2. 函數建模（2）- 当前适配度4.2，目标4.5+
3. 用於解釋的迴歸（1）- 当前适配度4.75，目标保持

### 7.2 验证指标

| 视频 | v5适配度 | 目标适配度 | 关键检查点 |
|------|---------|-----------|-----------|
| 進化（1） | 4.0 | 4.5+ | [04:10] 染色体数字是否有缓冲 |
| 函數建模（2） | 4.2 | 4.5+ | [05:12] "Marginal"是否有定义 |
| 迴歸（1） | 4.75 | 4.75+ | [04:40] Ridge/Lasso是否有过渡 |

### 7.3 回滚条件

如果出现以下情况，立即回滚到v5：
- 正确性下降超过0.2分
- 逻辑流畅下降超过0.2分
- 适配度没有提升或反而下降

---

## 八、风险控制清单

### 8.1 禁止修改的部分（已获得"exceptional"评价）

❌ **不要修改：**
- `src/overview_scene.py` 的核心结构（保持v5的5-12项列表）
- 视觉质量相关代码（Signaling系统）
- 节奏控制逻辑（Pacing系统）

### 8.2 必须保留的v5特性

✅ **必须保留：**
- Overview intro: "This video will be divided into the following parts"
- Overview ending: "Alright, let's now begin with the detailed content"
- 序号结构："the first part", "the second part"
- 5-12项的详细章节列表

---

## 九、成功标准

### 9.1 量化指标

- **适配度提升**：平均从4.15提升到4.5+（提升0.35+）
- **稳定性保持**：正确性和逻辑流畅保持在4.5+
- **认知摩擦点减少**：从平均2个减少到1个以下

### 9.2 定性指标

- 评测反馈中不再出现"术语无定义"的批评
- 评测反馈中不再出现"公式突然出现"的批评
- 保持"exceptional signaling"和"ideal pacing"的评价

---

**文件创建时间：** 2026-05-15
**实施优先级：** Phase 1 > Phase 2 > Phase 3
**预计完成时间：** Phase 1（1-2天），Phase 2（2-3天），Phase 3（3-4天）
