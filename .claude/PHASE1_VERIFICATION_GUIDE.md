# Phase 1 验证指南

## 快速验证方法

### 方法1：运行测试脚本
```bash
python3 test_terminology_detection_standalone.py
```

预期输出：5个测试案例全部通过，显示术语检测结果

---

### 方法2：生成一个测试视频

选择以下任一典型视频重新生成，观察术语定义是否自动插入：

#### 测试视频1：進化（1）
```bash
# 使用原始输入重新生成
# 关键检查点：[04:10] "2n=63"是否有定义
```

**预期改进：**
- 原文："Chromosome number: 2n = 63"
- 改进后："Chromosome number: 2n (diploid number, meaning two sets of chromosomes) equals 63"

---

#### 测试视频2：函數建模（2）
```bash
# 使用原始输入重新生成
# 关键检查点：[05:12] "Marginal"是否有定义
```

**预期改进：**
- 原文："Marginal Thinking"
- 改进后："Marginal (step-by-step change) Thinking"

---

#### 测试视频3：迴歸（1）
```bash
# 使用原始输入重新生成
# 关键检查点：[04:40] "Ridge/Lasso"是否有定义
```

**预期改进：**
- 原文："Ridge and Lasso Regression"
- 改进后："Ridge (penalty method that shrinks coefficients) and Lasso (penalty method that zeros out coefficients) Regression"

---

## 验证指标

### 成功标准
- ✅ 术语首次出现时自动添加定义
- ✅ 定义简洁（3-8个单词）
- ✅ 不影响正确性和逻辑流畅度
- ✅ 适配度评分提升至4.4+

### 失败标准（需要回滚）
- ❌ 正确性下降超过0.2分
- ❌ 逻辑流畅下降超过0.2分
- ❌ 适配度没有提升或反而下降
- ❌ 术语定义过长影响节奏

---

## 回滚方案

如果验证失败，执行以下命令回滚到v5：

```bash
# 查看当前commit
git log --oneline -3

# 回滚到Phase 1之前的commit
git reset --hard cb7983f

# 或者只回滚audio_steps.py
git checkout cb7983f -- src/audio_steps.py
```

---

## 下一步

验证通过后，继续实施Phase 2：公式缓冲机制

**修改文件：** prompts/stage2.py  
**预期效果：** 适配度 4.4-4.6 → 4.5-4.7
