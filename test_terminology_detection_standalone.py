#!/usr/bin/env python3
"""
独立测试术语检测系统 - Phase 1验证脚本（无依赖版本）

直接复制核心逻辑进行测试，避免导入整个audio_steps模块
"""

# 复制TERMINOLOGY_DICT
TERMINOLOGY_DICT = {
    "biology": {
        "heuristic": "rule-driven approach",
        "inference engine": "reasoning system",
        "translocation": "two-way transport",
        "lignin": "rigid cell wall material",
        "meiosis": "cell division that produces sex cells",
        "chromosome": "DNA package",
        "polyploidy": "chromosome doubling",
        "2n": "diploid number, meaning two sets of chromosomes",
        "gamete": "sex cell like sperm or egg",
        "zygote": "fertilized egg cell",
        "allele": "gene variant",
        "phenotype": "observable trait",
        "genotype": "genetic makeup",
    },
    "math": {
        "marginal": "step-by-step change",
        "tangent line": "flat line touching the curve",
        "vertex": "highest or lowest point",
        "derivative": "rate of change",
        "integral": "accumulated sum",
        "asymptote": "line the curve approaches but never touches",
        "inflection point": "where the curve changes from bending up to bending down",
    },
    "statistics": {
        "mse": "Mean Squared Error",
        "ridge": "penalty method that shrinks coefficients",
        "lasso": "penalty method that zeros out coefficients",
        "homoscedasticity": "equal variance",
        "heteroscedasticity": "unequal variance",
        "multicollinearity": "when predictors are highly correlated",
        "residual": "prediction error",
    },
    "physics": {
        "kinematic": "motion-related",
        "invariant": "unchanging quantity",
        "momentum": "mass times velocity",
        "inertia": "resistance to motion change",
    },
    "computer_science": {
        "heuristic": "rule of thumb",
        "inference": "logical reasoning",
        "algorithm": "step-by-step procedure",
        "recursion": "function calling itself",
    }
}


def _detect_and_define_terms(text: str, subject: str, grade_level: str) -> str:
    """
    检测文本中的专业术语并返回定义提示
    """
    subject_terms = TERMINOLOGY_DICT.get(subject, {})
    if not subject_terms:
        return ""

    found_terms = []
    text_lower = text.lower()

    # 按术语长度降序排序，优先匹配长术语
    sorted_terms = sorted(subject_terms.items(), key=lambda x: len(x[0]), reverse=True)

    for term, definition in sorted_terms:
        if term.lower() in text_lower:
            # 根据年级调整定义插入方式
            if grade_level == "middle_school":
                found_terms.append(
                    f"- When you say '{term}', immediately add: 'which means {definition}'"
                )
            elif grade_level == "high_school":
                found_terms.append(
                    f"- When you say '{term}', add: '({definition})'"
                )
            else:  # ap_college
                found_terms.append(
                    f"- When you say '{term}', briefly add: 'that is, {definition}'"
                )

    if found_terms:
        return "\n".join(found_terms)
    return ""


def test_case_1_evolution():
    """测试案例1：進化（1）- 染色体数字2n=63"""
    print("=" * 70)
    print("测试案例1：進化（1）- 染色体术语检测")
    print("=" * 70)

    screen_text = "Chromosome number: 2n = 63"
    subject = "biology"
    grade_level = "high_school"

    result = _detect_and_define_terms(screen_text, subject, grade_level)

    print(f"屏幕文本: {screen_text}")
    print(f"学科: {subject}")
    print(f"年级: {grade_level}")
    print(f"\n检测结果:")
    print(result if result else "（未检测到术语）")
    print()


def test_case_2_marginal():
    """测试案例2：函數建模（2）- Marginal Thinking"""
    print("=" * 70)
    print("测试案例2：函數建模（2）- Marginal术语检测")
    print("=" * 70)

    screen_text = "Marginal Thinking: How does output change?"
    subject = "math"
    grade_level = "high_school"

    result = _detect_and_define_terms(screen_text, subject, grade_level)

    print(f"屏幕文本: {screen_text}")
    print(f"学科: {subject}")
    print(f"年级: {grade_level}")
    print(f"\n检测结果:")
    print(result if result else "（未检测到术语）")
    print()


def test_case_3_regression():
    """测试案例3：迴歸（1）- Ridge/Lasso"""
    print("=" * 70)
    print("测试案例3：迴歸（1）- Ridge/Lasso术语检测")
    print("=" * 70)

    screen_text = "Ridge and Lasso Regression"
    subject = "statistics"
    grade_level = "high_school"

    result = _detect_and_define_terms(screen_text, subject, grade_level)

    print(f"屏幕文本: {screen_text}")
    print(f"学科: {subject}")
    print(f"年级: {grade_level}")
    print(f"\n检测结果:")
    print(result if result else "（未检测到术语）")
    print()


def test_grade_level_variations():
    """测试不同年级的定义方式"""
    print("=" * 70)
    print("测试案例4：不同年级的定义方式")
    print("=" * 70)

    screen_text = "The derivative shows the rate of change"
    subject = "math"

    for grade in ["middle_school", "high_school", "ap_college"]:
        result = _detect_and_define_terms(screen_text, subject, grade)
        print(f"\n年级: {grade}")
        print(f"定义方式:\n{result}")
    print()


def test_multiple_terms():
    """测试多个术语同时出现"""
    print("=" * 70)
    print("测试案例5：多个术语同时检测")
    print("=" * 70)

    screen_text = "MSE measures residual errors in Ridge regression"
    subject = "statistics"
    grade_level = "high_school"

    result = _detect_and_define_terms(screen_text, subject, grade_level)

    print(f"屏幕文本: {screen_text}")
    print(f"学科: {subject}")
    print(f"年级: {grade_level}")
    print(f"\n检测结果:")
    print(result if result else "（未检测到术语）")
    print()


def show_dictionary_coverage():
    """显示术语词典覆盖范围"""
    print("=" * 70)
    print("术语词典覆盖范围统计")
    print("=" * 70)

    for subject, terms in TERMINOLOGY_DICT.items():
        print(f"\n{subject}: {len(terms)}个术语")
        for term, definition in sorted(terms.items()):
            print(f"  - {term}: {definition}")
    print()


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("Phase 1 术语检测系统测试")
    print("=" * 70 + "\n")

    # 运行所有测试
    test_case_1_evolution()
    test_case_2_marginal()
    test_case_3_regression()
    test_grade_level_variations()
    test_multiple_terms()
    show_dictionary_coverage()

    print("=" * 70)
    print("✅ 测试完成")
    print("=" * 70)
