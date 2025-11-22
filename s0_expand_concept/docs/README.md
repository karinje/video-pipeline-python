# Step 0: Expand Concept (Direct Concept Pipeline)

**Purpose**: Takes a high-level ad concept (2-3 sentences) and expands it into a full scene-by-scene narrative, optionally judges and revises it, then proceeds directly to video generation (Step 5+).

This step provides a fast-track alternative to the full pipeline (Steps 1-4), allowing you to start with your own creative concept instead of generating and evaluating many variations.

---

## Overview

Step 0 consists of three sub-steps:

### Step 0a: Expand Concept
- **Input**: High-level concept (2-3 sentences)
- **Output**: Detailed scene-by-scene narrative (5+ scenes)
- **What it does**: Expands your concept into full scenes with eyewear integration, maintaining the same output format as Step 1

### Step 0b: Judge Concept (Optional)
- **Input**: Expanded concept from Step 0a
- **Output**: Evaluation with scores and feedback
- **What it does**: Uses the same judge logic from Step 2 to evaluate your concept

### Step 0c: Revise Concept (Optional)
- **Input**: Expanded concept + judge evaluation
- **Output**: Improved concept addressing weaknesses
- **What it does**: Revises the concept based on judge feedback

---

## When to Use Step 0

**Use Step 0 when:**
- You have a specific creative concept in mind
- You want to skip the multi-concept generation phase
- You want faster iteration (skip Steps 1-4)
- You're testing a single concept idea

**Use Full Pipeline (Steps 1-4) when:**
- You want to explore multiple creative directions
- You want to compare different ad styles
- You want to test multiple LLM models
- You need comprehensive concept evaluation

---

## Usage

### Option 0: Complete Pipeline (Recommended - All Steps in One)

Run all three steps (expand, judge, revise) in sequence with a single command:

```bash
cd s0_expand_concept/scripts

python run_step0_complete.py \
  inputs/concepts/world_comes_into_focus.txt \
  ../../s1_generate_concepts/inputs/configs/sunglasses.json \
  anthropic/claude-opus-4-1-20250805
```

**Or with concept text directly:**
```bash
python run_step0_complete.py \
  "The World Comes Into Focus. A character puts on the stylish eyewear..." \
  ../../s1_generate_concepts/inputs/configs/sunglasses.json \
  anthropic/claude-opus-4-1-20250805
```

**With custom video settings:**
```bash
python run_step0_complete.py \
  inputs/concepts/world_comes_into_focus.txt \
  ../../s1_generate_concepts/inputs/configs/sunglasses.json \
  anthropic/claude-opus-4-1-20250805 \
  --num-clips 5 \
  --clip-duration 8
```

**Features:**
- Runs Step 0a, 0b, and 0c sequentially
- Uses the same LLM model for all steps (default: Opus 4.1)
- Automatically passes outputs between steps
- Provides summary with original score and all file paths
- Configurable video settings via CLI flags

**Output**: Refined concept ready for video generation (go to Step 5)

**Arguments:**
- `concept_text_or_file`: High-level concept text or path to concept file
- `brand_config` (optional): Path to brand config JSON (default: `../../s1_generate_concepts/inputs/configs/sunglasses.json`)
- `llm_model` (optional): LLM model for all steps (default: `anthropic/claude-opus-4-1-20250805`)
- `output_dir` (optional): Output directory (default: `s0_expand_concept/outputs/`)
- `--num-clips N` (optional): Number of scenes/clips to generate (default: 5)
- `--clip-duration N` (optional): Duration per clip in seconds (default: 8)

---

### Option 1: Expand Only (Fastest)
```bash
cd s0_expand_concept/scripts

python expand_concept.py \
  "The World Comes Into Focus. A character puts on the stylish eyewear and the previously bland world is suddenly full of vibrant colors, confident people, and subtle visual gags." \
  ../../s1_generate_concepts/inputs/configs/sunglasses.json \
  openai/gpt-5.1 \
  ../outputs
```

**Output**: Expanded concept ready for video generation (go to Step 5)

### Option 2: Expand + Judge (Get Feedback)
```bash
# Step 0a: Expand
python expand_concept.py \
  "Your concept text..." \
  ../../s1_generate_concepts/inputs/configs/sunglasses.json \
  openai/gpt-5.1 \
  ../outputs

# Step 0b: Judge
python judge_concept.py \
  ../outputs/brand_timestamp/concept_expanded.txt \
  ../outputs/brand_timestamp/concept_metadata.json \
  anthropic/claude-sonnet-4-5-20250929
```

**Output**: Expanded concept + evaluation scores (go to Step 5 or revise first)

### Option 3: Full Refinement (Expand + Judge + Revise)
```bash
# Step 0a: Expand
python expand_concept.py "Your concept..." ../../s1_generate_concepts/inputs/configs/sunglasses.json

# Step 0b: Judge
python judge_concept.py \
  ../outputs/brand_timestamp/concept_expanded.txt \
  ../outputs/brand_timestamp/concept_metadata.json

# Step 0c: Revise
python revise_concept.py \
  ../outputs/brand_timestamp/concept_expanded.txt \
  ../outputs/brand_timestamp/concept_evaluation.json \
  ../../s1_generate_concepts/inputs/configs/sunglasses.json
```

**Output**: Refined concept ready for video generation (go to Step 5)

---

## Configuration

### Video Settings

Both expansion and revision use video settings that can be configured via CLI arguments:

**Default values:**
```python
video_settings = {
    "num_clips": 5,        # Number of scenes to generate
    "clip_duration": 8     # Duration per scene in seconds
}
```

**Customize via CLI:**
```bash
python run_step0_complete.py concept.txt config.json model --num-clips 4 --clip-duration 6
```

These are dynamically inserted into prompts, so the LLM generates the correct number of scenes with appropriate pacing. Note: Duration values are used to guide the LLM but are not written into the final concept output file.

### Temperature Settings

**Current temperature settings:**
- **Step 0a (Expand)**: `temperature=1.0` - Higher temperature for more creative variation
- **Step 0b (Judge)**: `temperature=1.0` - Higher temperature for more creative evaluation
- **Step 0c (Revise)**: `temperature=1.0` - Higher temperature for more creative revision

These settings are hardcoded in the scripts. To change them, edit:
- `s0_expand_concept/scripts/expand_concept.py` (line 144)
- `s2_judge_concepts/scripts/judge_concepts.py` (line 216)
- `s0_expand_concept/scripts/revise_concept.py` (line 158)

### Brand Config

All eyewear specifications come from brand config:
- `FRAME_STYLE`: Frame style (e.g., "Aviator Classic")
- `LENS_TYPE`: Lens type (e.g., "Polarized Sunglasses")
- `STYLE_PERSONA`: Style persona (e.g., "Timeless Cool")
- `WEARING_OCCASION`: Occasions (e.g., "Driving, Beach, City Life")

If fields are missing, the LLM determines appropriate values based on the concept.

---

## Output Structure

```
s0_expand_concept/outputs/
  brand_timestamp/
    concept_name_expanded.txt           # Step 0a output
    concept_name_metadata.json          # Step 0a metadata
    concept_name_evaluation.json        # Step 0b output
    concept_name_revised.txt            # Step 0c output
    concept_name_revision_metadata.json # Step 0c metadata
```

---

## Integration with Pipeline

After Step 0, the pipeline skips directly to Step 5:

```
Step 0a: Expand concept → 5 scenes
Step 0b: Judge (optional)
Step 0c: Revise (optional)
↓
Step 5: Generate universe/characters
Step 6: Generate reference images
Step 7: Generate scene prompts
Step 8: Generate first frames
Step 9: Generate video clips
Step 10: Merge clips
```

**Steps 1-4 are skipped** when using Step 0.

---

## Example Concepts

### Example 1: The World Comes Into Focus
```
A character puts on the stylish eyewear and the previously bland world 
is suddenly full of vibrant colors, confident people, and subtle visual 
gags. Each lens change shifts the overall vibe (cool, classy, playful), 
highlighting different styles while implying that the right frames 
change how you see yourself.
```

### Example 2: Accidental Style Icon
```
A totally average person keeps getting mistaken for a celebrity, 
influencer, or fashion model everywhere they go—just because of 
their eyewear. Paparazzi, VIP treatment, and red-carpet moments 
pile up, while the character insists they're just running errands.
```

### Example 3: Signature Discovery
```
Someone tries on dozens of frames searching for "the one." Each pair 
changes their reflection and how others see them. Finally, they find 
the frames that feel like they've always been theirs—the signature 
look they didn't know they were missing.
```

---

## Prompt Templates

### Expand Template (`inputs/prompt_templates/expand_concept_template.md`)
- Takes high-level concept
- Generates {{num_clips}} scenes
- Each scene {{clip_duration}} seconds
- Maintains eyewear focus
- No camera/lighting details (comes later in Step 7)

### Revise Template (`inputs/prompt_templates/revise_concept_template.md`)
- Takes original concept + judge feedback
- Addresses specific weaknesses
- Maintains strengths
- Keeps same scene count and duration

---

## Quick Reference

### Complete Script (All Steps)
```bash
python run_step0_complete.py <concept_file_or_text> [brand_config] [llm_model]
```

### Individual Steps
```bash
# Step 0a: Expand
python expand_concept.py <concept_text_or_file> [brand_config] [llm_model] [output_dir]
# Default: 5 clips, 8 seconds each

# Step 0b: Judge
python judge_concept.py <expanded_file> <metadata_file> [judge_model] [output_dir]
# Uses temperature=1.0 for evaluation

# Step 0c: Revise
python revise_concept.py <expanded_file> <evaluation_file> [brand_config] [llm_model] [output_dir]
# Default: 5 clips, 8 seconds each
```

---

## Notes

- **Complete script available**: Use `run_step0_complete.py` to run all three steps with one command
- **Same model for all steps**: The complete script uses the same LLM model for expand, judge, and revise
- **No hardcoded values**: All scene counts and durations come from config
- **Reuses judge logic**: Step 0b uses the same evaluation criteria as Step 2
- **Same output format**: Step 0 outputs match Step 1 format, so Step 5+ works unchanged
- **Optional steps**: You can skip 0b/0c and go straight to video generation
- **Multiple concepts**: Run Step 0 multiple times for different concepts, then compare results

---

## Next Steps

After Step 0, use the revised (or expanded) concept file as input to Step 5:

```bash
# From pipeline runner
python run_pipeline_complete.py --start-from step5 --concept-file s0_expand_concept/outputs/brand_timestamp/concept_revised.txt
```

Or integrate into full pipeline config with `start_from: direct_concept`.

