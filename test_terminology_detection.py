#!/usr/bin/env python3
"""
测试术语检测系统 - Phase 1验证脚本

测试三个典型案例：
1. 進化（1）- 染色体术语检测
2. 函數建模（2）- Marginal术语检测
3. 迴歸（1）- Ridge/Lasso术语检测
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.audio_steps import _detect_and_define_terms, TERMINOLOGY_DICT


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
        print(f"定义方式: {result}")
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
    print("测试完成")
    print("=" * 70)
