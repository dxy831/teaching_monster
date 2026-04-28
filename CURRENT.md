# Project Status

## Phase 1: English Migration ✅ COMPLETED
All prompts and code logic translated to English. See commit 209571e for details.

---

## Phase 2: Multi-Subject AP-Aligned Prompt Optimization 🔄 IN PROGRESS

### Context
Transform the teaching video generation system from CS-algorithm-centric to support multiple subjects (physics, biology, computer science, mathematics) with AP-standard pedagogy, zero hallucination constraints, ZPD modeling, and rubric-aligned evaluation.

### Completed (Commit Ready)

#### 2.1 Extended User Profile Schema ✅
- **File:** `prompts/user_profile.py`
- **Changes:**
  - Added to `get_profile_analysis_prompt()` JSON schema:
    - `subject_domain`, `ap_level`, `zpd_prior_knowledge`, `zpd_learning_target` (in `user_summary`)
    - `ap_teaching_pattern`, `factuality_anchors`, `zpd_bridge_strategy` (in `stage1_outline_guidance`)
    - `primary_visual_type`, `avoid_visual_types` (in `stage2_storyboard_guidance`)
    - `visualization_strategy`, `manim_objects_priority` (in `stage3_code_guidance`)
  - Updated all three stage profile getters to expose new fields
  - Added helper methods: `_default_ap_pattern()`, `_default_primary_visual_type()`, `_default_visualization_strategy()`, `_default_manim_objects()`
  - Updated CS and non-CS default profiles with new field defaults

#### 2.2 Stage 1 Prompt Redesign ✅
- **File:** `prompts/stage1.py`
- **Changes:**
  - Added `_get_ap_pattern_block(subject)` helper function with four AP teaching patterns:
    - Physics: Phenomenon → Driving Question → Model Building → Quantitative Example → Verification → Transfer
    - Biology: Big Idea → Essential Question → Observation → Mechanism → Comparison → Application
    - Math: Numerical Intuition → Geometric Intuition → Formal Definition → Derivation → Worked Example → Transfer
    - CS: Problem → Intuition → Execution Trace → Implementation → Complexity → Generalization
  - Injected AP pattern block into main prompt
  - Added mandatory zero-hallucination & factuality constraint block
  - Added ZPD section-level requirements (prior knowledge activation, one concept per section, forward bridging)

#### 2.3 Stage 2 Prompt Redesign ✅
- **File:** `prompts/stage2.py`
- **Changes:**
  - Added `_get_subject_visual_strategy(subject, target_language)` helper with subject-specific visual rules:
    - Physics: force vectors, motion graphs, free-body diagrams, formula derivations with units
    - Biology: structures, process flows, comparisons, chronological mechanism animation, standardized terminology
    - Math: coordinate planes, function graphs, symbolic transformations, geometric constructions, proof steps
    - CS: code blocks, execution traces, data structures (existing pattern)
  - Injected subject visual strategy block into main prompt
  - Added multimodal consistency constraint block
  - Added ZPD pacing requirements (prior knowledge activation, single concept per section, section bridging)

#### 2.4 Stage 3 Prompt Enhancement ✅
- **File:** `prompts/stage3.py`
- **Changes:**
  - Expanded `subject_prompt` from binary (CS vs. non-CS) to four-subject differentiation with visualization strategies
  - Added `zpd_pacing_prompt` with mandatory requirements for each section
  - Added factual accuracy constraints for Manim code (formulas, units, biological terms, derivation order)

#### 2.5 Stage 5 Evaluation Extension ✅
- **File:** `prompts/stage5_eva.py`
- **Changes:**
  - Added `get_prompt_competition_rubric(knowledge_point, subject_domain)` function
  - Four-dimension rubric (25 points each):
    1. **Factual Accuracy & Evidence Basis:** Zero-hallucination check, knowledge depth verification, citation attribution
    2. **Pedagogical Logic & Scaffolding:** Scaffolding construction, narrative coherence, AP pattern compliance
    3. **Learner Adaptation & ZPD Fit:** ZPD recognition, language calibration, prior knowledge activation
    4. **Engagement & Multimodal Consistency:** Narrative appeal, cognitive focus maintenance, multimodal alignment
  - Structured JSON output with per-sub-criterion scores and factual error flagging

### Verification ✅
- All modified modules pass Python syntax check
- Full integration test passed:
  - All four subject default profiles generate correctly with new fields
  - Stage 1/2/3 prompt generation works for all subjects
  - Competition rubric function callable and returns valid JSON template

### Next Steps (When Ready)
1. **End-to-End Testing:**
   - Run sample for physics: Newton's Second Law (expect AP Physics 1 pattern sections)
   - Run sample for biology: Mitosis (expect Big Idea → Mechanism sections)
   - Run sample for math: Derivative Geometric Meaning (expect Intuition → Formal Definition sections)
   - Verify Stage 2 storyboard uses correct visual types (arrows/axes for physics, NOT code blocks)
   - Verify Stage 5 competition rubric correctly scores multimodal consistency and ZPD alignment

2. **Backward Compatibility Check:**
   - Run existing CS topic (Binary Search) without explicit subject parameter
   - Confirm output identical to pre-optimization behavior (all defaults point to CS)

3. **API Integration (if needed):**
   - Add `subject` field to `VideoGenerateRequest` schema
   - Thread subject through `src/api/tasks/video_tasks.py` into profile parsing

---

## Files Modified
- `prompts/user_profile.py` — Schema expansion + helper methods
- `prompts/stage1.py` — AP patterns + zero-hallucination + ZPD constraints
- `prompts/stage2.py` — Subject visual strategy + multimodal consistency + ZPD pacing
- `prompts/stage3.py` — Visualization strategy + ZPD rhythm constraints
- `prompts/stage5_eva.py` — Competition rubric function

---

## Success Criteria
- ✅ All new schema fields properly integrated into default profiles
- ✅ All four subjects can generate outlines with subject-appropriate AP teaching patterns
- ✅ Stage 2 outlines show correct visual types (no code blocks for non-CS)
- ✅ Competition rubric successfully evaluates videos on four dimensions
- ✅ Backward compatibility maintained (CS default behavior unchanged)
- ⏳ End-to-end video generation tests for each subject
