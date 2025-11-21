# Complete Pipeline Runner

## Overview
Orchestrates all pipeline steps from brand config (or evaluation JSON) to final merged video.

## Pipeline Steps
1. **Step 0**: Generate Concepts (if `start_from='brand_config'`)
2. **Step 1**: Judge/Evaluate Concepts (if `start_from='brand_config'`)
3. **Step 2**: Extract Best Concept from Evaluation
4. **Step 3**: Revise Concept Based on Judge Feedback (with optional re-judging)
5. **Step 4**: Generate Universe and Characters
6. **Step 5**: Generate Reference Images
7. **Step 6**: Generate Scene Prompts
8. **Step 7**: Generate First Frame Images
9. **Step 8**: Generate Video Clips
10. **Step 9**: Merge Video Clips into Final Video

## Configuration
Edit `configs/pipeline_config.yaml` to configure:
- Pipeline mode (start_from, skip options)
- Input files (brand config, evaluation JSON)
- Concept generation settings (ad_styles [fallback only], templates, models)
  - **AD_STYLE Priority**: First uses `AD_STYLE` from brand config, falls back to `ad_styles` list in pipeline config
- Evaluation settings (judge model)
- Output directories
- Video settings (duration, resolution, aspect ratio)
- Model settings (LLM, video, image models)
- Advanced options (skip flags)

## Usage

### Full Pipeline (Brand Config → Video)
```bash
cd run_pipeline/scripts
python run_pipeline_complete.py
```
Uses default `configs/pipeline_config.yaml` with `start_from='brand_config'`

### Video Only (Evaluation → Video)
Edit `configs/pipeline_config.yaml`:
```yaml
pipeline_mode:
  start_from: evaluation_json

input:
  evaluation_json: ../s2_judge_concepts/outputs/rolex_evaluation_claude_4.5_1115_1848.json
```
Then run:
```bash
cd run_pipeline/scripts
python run_pipeline_complete.py
```

### Custom Config
```bash
cd run_pipeline/scripts
python run_pipeline_complete.py ../configs/my_config.yaml
```

## Output Structure
All outputs are organized by step:
- `../s1_generate_concepts/outputs/` - Concepts and prompts
- `../s2_judge_concepts/outputs/` - Evaluations
- `../s3_extract_best_concept/outputs/` - Best concept metadata
- `../s4_revise_concept/outputs/` - Revised concepts with re-evaluation scores
- `../s5_generate_universe/outputs/` - Universe and character descriptions
- `../s6_generate_reference_images/outputs/` - Reference images
- `../s7_generate_scene_prompts/outputs/` - Scene-by-scene video prompts
- `../s8_generate_first_frames/outputs/` - First frame images
- `../s9_generate_video_clips/outputs/` - Video clips
- `../s10_merge_clips/outputs/` - Final merged video

