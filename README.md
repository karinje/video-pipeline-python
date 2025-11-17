# Video Generation Pipeline

Complete pipeline for generating AI video ads from brand concepts to final merged video.

## Quick Start

```bash
cd run_pipeline/scripts
python run_pipeline_complete.py
```

## Project Structure

The project is organized into step folders (`s1_` through `s10_`) that clearly show the pipeline flow:

- **s1_generate_concepts/** - Generate ad concepts (generic + advanced prompts, multiple models)
- **s2_judge_concepts/** - Judge/evaluate concepts using LLM
- **s3_extract_best_concept/** - Extract best-scoring concept
- **s4_revise_script/** - Revise script for video timing
- **s5_generate_universe/** - Generate universe/characters
- **s6_generate_reference_images/** - Generate reference images
- **s7_generate_scene_prompts/** - Generate scene prompts
- **s8_generate_first_frames/** - Generate first frame images
- **s9_generate_video_clips/** - Generate video clips
- **s10_merge_clips/** - Merge clips into final video
- **run_pipeline/** - Main pipeline orchestrator

Each step folder contains:
- `scripts/` - Main scripts for that step
- `inputs/` - Input files (configs, templates, etc.)
- `docs/` - Documentation for that step
- `outputs/` - Generated outputs (organized by run)

## Configuration

Edit `run_pipeline/configs/pipeline_config.yaml` to configure:
- Pipeline mode (start_from, skip options)
- Input files (brand config, evaluation JSON)
- Concept generation settings
- Model settings
- Output directories
- Video settings

## Documentation

- **PROJECT_STRUCTURE.md** - Detailed project structure overview
- **REORGANIZATION_SUMMARY.md** - What changed in the reorganization
- **run_pipeline/docs/README.md** - Complete pipeline documentation
- **{step}/docs/README.md** - Individual step documentation

## Requirements

See `requirements.txt` for Python dependencies.

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up environment variables (`.env`):
```
OPENAI_API_KEY=your_key
ANTHROPIC_API_KEY=your_key
REPLICATE_API_TOKEN=your_token
```

3. Run the pipeline:
```bash
cd run_pipeline/scripts
python run_pipeline_complete.py
```

