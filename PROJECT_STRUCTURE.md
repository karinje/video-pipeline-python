# Project Structure

## Overview
The project is organized into step folders (`s1_`, `s2_`, etc.) that clearly show the pipeline flow. Each step folder contains:
- `scripts/` - Main scripts for that step
- `inputs/` - Input files (configs, templates, etc.)
- `docs/` - Documentation for that step
- `outputs/` - Generated outputs (organized by run)

## Folder Structure

```
video-gen/
├── s1_generate_concepts/          # Step 1: Generate ad concepts
│   ├── scripts/
│   │   ├── batch_run_all_styles.py
│   │   ├── generate_prompt.py
│   │   ├── execute_llm.py
│   │   └── run_single_concept.py
│   ├── inputs/
│   │   ├── configs/               # Brand configs (rolex.json, nike.json)
│   │   └── prompt_templates/       # Prompt templates
│   ├── docs/
│   │   └── README.md
│   └── outputs/                    # Concepts and prompts
│       └── {brand}_{timestamp}/
│           ├── {brand}_{ad_style}_{template}_{model}.txt
│           ├── {brand}_batch_summary_{timestamp}.json
│           └── {brand}_{ad_style}_{template}_{model}_prompt.txt
│
├── s2_judge_concepts/              # Step 2: Judge/evaluate concepts
│   ├── scripts/
│   │   └── judge_concepts.py
│   ├── inputs/                     # References s1 outputs (no copying)
│   ├── docs/
│   │   └── README.md
│   └── outputs/                    # Evaluations
│       ├── {brand}_evaluation_{judge_model}_{timestamp}.json
│       └── {brand}_scores_{judge_model}_{timestamp}.csv
│
├── s3_extract_best_concept/        # Step 3: Extract best concept
│   ├── scripts/
│   ├── inputs/
│   ├── docs/
│   └── outputs/
│
├── s4_revise_script/               # Step 4: Revise script for video
│   ├── scripts/
│   │   └── generate_video_script.py
│   ├── inputs/
│   ├── docs/
│   └── outputs/                    # Revised scripts, universe, scene prompts
│       └── {brand}_{timestamp}/
│           └── {concept_name}/
│               ├── {concept_name}_revised.txt
│               ├── {concept_name}_universe_characters.json
│               └── {concept_name}_scene_prompts.json
│
├── s5_generate_universe/           # Step 5: Generate universe/characters
│   ├── scripts/
│   ├── inputs/
│   ├── docs/
│   └── outputs/
│
├── s6_generate_reference_images/  # Step 6: Generate reference images
│   ├── scripts/
│   │   └── generate_universe_images.py
│   ├── inputs/
│   ├── docs/
│   └── outputs/                    # Reference images
│       └── {concept_name}/
│           ├── characters/
│           ├── locations/
│           ├── props/
│           └── image_generation_summary.json
│
├── s7_generate_scene_prompts/      # Step 7: Generate scene prompts
│   ├── scripts/
│   ├── inputs/
│   ├── docs/
│   └── outputs/
│
├── s8_generate_first_frames/       # Step 8: Generate first frame images
│   ├── scripts/
│   │   └── generate_first_frames.py
│   ├── inputs/
│   ├── docs/
│   └── outputs/                    # First frame images
│       └── {concept_name}/
│           ├── {concept_name}_p{scene_num}_first_frame.jpg
│           └── debug/
│
├── s9_generate_video_clips/        # Step 9: Generate video clips
│   ├── scripts/
│   │   └── generate_sora2_clip.py
│   ├── inputs/
│   ├── docs/
│   └── outputs/                    # Video clips
│       └── {concept_name}/
│           ├── {concept_name}_p{scene_num}_{model}.mp4
│           └── debug/
│
├── s10_merge_clips/                # Step 10: Merge video clips
│   ├── scripts/
│   │   └── merge_video_clips_ffmpeg.py
│   ├── inputs/
│   ├── docs/
│   └── outputs/                    # Final merged video
│
└── run_pipeline/                   # Main pipeline orchestrator
    ├── scripts/
    │   └── run_pipeline_complete.py
    ├── configs/
    │   └── pipeline_config.yaml
    └── docs/
        └── README.md
```

## Key Principles

1. **Step folders are alphabetically sorted** - `s1_`, `s2_`, etc. show pipeline order
2. **Each step is self-contained** - Has its own scripts, inputs, docs, outputs
3. **Inputs reference previous outputs** - No copying, just references
4. **Outputs organized by run** - Each run gets a folder named by input config/run
5. **Clear separation** - Easy to understand what each step does

## Running the Pipeline

### Full Pipeline
```bash
cd run_pipeline/scripts
python run_pipeline_complete.py
```

### Individual Steps
Each step can be run independently - see `{step}/docs/README.md` for details.

