# Project Reorganization Summary

## What Changed

The project has been reorganized into a clear step-by-step structure where each pipeline step has its own folder.

## New Structure

### Step Folders (s1_ through s10_)
Each step folder contains:
- `scripts/` - Main scripts for that step
- `inputs/` - Input files (configs, templates, etc.)
- `docs/` - Documentation explaining how to run the step
- `outputs/` - Generated outputs organized by run

### Main Pipeline Folder
- `run_pipeline/` - Contains the orchestrator script and config

## Key Changes

1. **All scripts moved to step folders**
   - `batch_run_all_styles.py` → `s1_generate_concepts/scripts/`
   - `judge_concepts.py` → `s2_judge_concepts/scripts/`
   - `generate_video_script.py` → `s4_revise_script/scripts/`
   - `generate_universe_images.py` → `s6_generate_reference_images/scripts/`
   - `generate_first_frames.py` → `s8_generate_first_frames/scripts/`
   - `generate_sora2_clip.py` → `s9_generate_video_clips/scripts/`
   - `merge_video_clips_ffmpeg.py` → `s10_merge_clips/scripts/`
   - `run_pipeline_complete.py` → `run_pipeline/scripts/`

2. **All outputs moved to step folders**
   - `results/` → `s1_generate_concepts/outputs/`
   - `prompts_history/` → `s1_generate_concepts/outputs/`
   - `evaluations/` → `s2_judge_concepts/outputs/`
   - `script_generation/` → `s4_revise_script/outputs/`
   - `universe_characters/` → `s6_generate_reference_images/outputs/`
   - `first_frames/` → `s8_generate_first_frames/outputs/`
   - `video_outputs/` → `s9_generate_video_clips/outputs/`

3. **Config files moved**
   - `pipeline_config.yaml` → `run_pipeline/configs/`
   - `configs/` → `s1_generate_concepts/inputs/configs/`
   - `prompt_templates/` → `s1_generate_concepts/inputs/prompt_templates/`

4. **Updated paths**
   - All scripts updated to use new folder structure
   - Pipeline config updated with new paths
   - Imports updated to work with new structure

## How to Use

### Run Full Pipeline
```bash
cd run_pipeline/scripts
python run_pipeline_complete.py
```

### Run Individual Steps
See each step's `docs/README.md` for instructions.

## Benefits

1. **Clear organization** - Each step is self-contained
2. **Easy to understand** - Step folders show pipeline flow
3. **Easy to navigate** - All related files in one place
4. **Better documentation** - Each step has its own README
5. **Easier debugging** - Know exactly where inputs/outputs are

## Migration Notes

- Old paths in configs have been updated
- All existing outputs have been moved to new locations
- Scripts have been updated to work with new structure
- Backward compatibility: Old JSON config still works if paths are updated

