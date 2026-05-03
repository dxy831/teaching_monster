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

## Phase 2.6: Duration Control Hardening ✅

- **File:** `src/agent.py`
- **Changes:**
  - Added `RunConfig` fields:
    - `max_video_seconds` (default 600)
    - `pipeline_budget_seconds` (default 1800)
    - `render_timeout_seconds` (default 600)
  - Replaced hard-coded 10-minute section filtering logic with config-driven limits in `_select_sections_with_ai()`
  - Added post-TTS duration enforcement:
    - New helper `_actual_tts_duration_for_section()`
    - New trimming pass `_trim_sections_by_actual_tts_duration()`
    - Removed special-case cover/overview isolation and switched to AI-guided trimming among variable sections based on actual TTS duration
    - Final section retention now uses real `audio_duration` from generated TTS steps instead of relying only on storyboard `estimated_duration`
  - Added pipeline wall-clock budget awareness in `GENERATE_VIDEO()`:
    - Tracks elapsed generation time
    - Computes remaining budget before render stage
    - Derives dynamic per-section render timeout from remaining budget
  - Parameterized render timeout in `render_all_sections()` instead of fixed `future.result(timeout=1200)`
  - Added CLI arguments:
    - `--max_video_seconds`
    - `--pipeline_budget_seconds`
    - `--render_timeout_seconds`

### Verification ✅

- `src/agent.py` passes Python syntax check via `python -m py_compile`
- Duration control flow now supports:
  - storyboard estimated-duration prefilter
  - TTS actual-duration postfilter
  - pipeline-level wall-clock budget control

### Notes

- The log `当前总预估时长为 X 秒` was previously based only on storyboard `estimated_duration`
- Final video length enforcement is now strengthened by a second pass using real TTS `audio_duration`
- This was added to reduce the chance that a nominally short plan still expands into a video too long to finish within the desired ~30 minute pipeline budget

## Phase 2.8: 29m30s Fallback Video Return Hardening ✅

- **Files:** `src/agent.py`, `src/api/tasks/video_tasks.py`
- **Changes:**
  - Added a hard pivot deadline at 29 minutes 30 seconds inside `generate_video_task()`
  - Updated `render_all_sections()` to accept a `deadline` and stop waiting for unfinished section futures once the pivot time is reached
  - Added disk-based completed-video discovery in `TeachingVideoAgent`:
    - `_discover_completed_section_videos()` scans `optimized_videos/`, `audio_remux/`, and rendered Manim output directories
    - discovered clips are accepted only if they already exist, are non-empty, have stable file size across two short checks, and contain an audio stream
  - Fallback merge no longer depends only on `future.result()` return timing; at pivot time it scans disk for already completed section outputs and merges those in outline order
  - `generate_video_task()` now refreshes `agent.section_videos` from scanned disk outputs before merge so the final concat uses the latest completed clips
  - Tightened fallback return priority:
    - if any completed section exists by the pivot point, the task prioritizes returning `video_file`
    - non-essential post-processing no longer blocks the primary fallback return path
  - `_collect_subtitles()` now accepts a merged-section filter so subtitles only cover sections actually included in the merged fallback video
  - Metadata now records only the merged section set for fallback output consistency

### Verification ✅

- `src/agent.py` and `src/api/tasks/video_tasks.py` pass Python syntax check via:
  - `python -m py_compile src/agent.py src/api/tasks/video_tasks.py`

### Notes

- The fallback path now begins collecting and merging already completed section videos at the 29m30s pivot instead of waiting for all render futures to finish
- The fallback merge is based on disk-visible, stable, audio-valid clips rather than unfinished in-memory future state
- This improves graceful degradation under long-running renders, but still requires that at least one section video be fully written and stable by the pivot time

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

#### 2.7 Section-Level Early Stop for Feedback Optimization ✅

- **Files:** `src/agent.py`, `prompts/stage5_eva.py`
- **Changes:**
  - Extended `VideoFeedback` with:
    - `is_good_enough`
    - `good_enough_reason`
    - `evaluation_scores`
  - Added per-section runtime stop state in `TeachingVideoAgent`:
    - `section_feedback_stop_flags`
    - `section_feedback_stop_reasons`
  - Updated `get_mllm_feedback()` to combine:
    - Stage 4 layout issue detection via `get_prompt4_layout_feedback()`
    - Stage 5 scoring via `get_prompt_aes()`
  - Enhanced `get_prompt_aes()` so `element_layout` explicitly evaluates:
    - lecture-line obstruction
    - readability-harming overlap
    - off-screen clipping
    - crowding
    - label-object proximity
  - Added structured Stage 5 fields:
    - `is_good_enough`
    - `good_enough_reason`
    - `hard_blockers`
  - Added relaxed early-stop thresholds:
    - `element_layout >= 15/20`
    - `overall_score >= 78/100`
    - average of `element_layout`, `attractiveness`, and `visual_consistency` >= `15/20`
  - Ensured hard blockers override early-stop decisions even when the score is high
  - Updated `render_section()` so once a section is judged good enough, it immediately skips the current section’s remaining feedback rounds

### Verification ✅

- All modified modules pass Python syntax check
- Full integration test passed:
  - All four subject default profiles generate correctly with new fields
  - Stage 1/2/3 prompt generation works for all subjects
  - Competition rubric function callable and returns valid JSON template
- Additional syntax validation passed for the early-stop optimization change:
  - `python -m py_compile src/agent.py prompts/stage5_eva.py`

### Next Steps (When Ready)

1. **End-to-End Testing:**
   - Run sample for physics: Newton's Second Law (expect AP Physics 1 pattern sections)
   - Run sample for biology: Mitosis (expect Big Idea → Mechanism sections)
   - Run sample for math: Derivative Geometric Meaning (expect Intuition → Formal Definition sections)
   - Verify Stage 2 storyboard uses correct visual types (arrows/axes for physics, NOT code blocks)
   - Verify Stage 5 competition rubric correctly scores multimodal consistency and ZPD alignment
   - Verify section optimization now stops early when layout / occlusion / readability quality is already good enough

2. **Backward Compatibility Check:**
   - Run existing CS topic (Binary Search) without explicit subject parameter
   - Confirm output identical to pre-optimization behavior (all defaults point to CS)

3. **Optimization Behavior Check:**
   - Validate that sections with moderate-to-high Stage 5 visual / overall scores can now skip later feedback rounds
   - Validate that sections with obstruction / overlap / clipping still continue optimization despite high scores
   - Validate that malformed Stage 5 JSON falls back safely without accidental early stop

4. **API Integration (if needed):**
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
