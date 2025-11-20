# Step 1: Generate Concepts

## Overview
Generates 5-scene ad concepts for all combinations of AD_STYLE, templates, and models. Runs in parallel for speed.

## Inputs
- **Brand config file**: `inputs/configs/{brand}.json`
- **Prompt templates**: `inputs/prompt_templates/`
  - `advanced_structured.md`
  - `generic_simple.md`
- **Creative direction**: Specified in pipeline config

## Outputs
- **Concepts**: `outputs/{brand}_{timestamp}/`
  - `{brand}_{ad_style}_{template}_{model}.txt` - Concept files
  - `{brand}_batch_summary_{timestamp}.json` - Batch summary
- **Prompts**: `outputs/{brand}_{timestamp}/`
  - `{brand}_{ad_style}_{template}_{model}_prompt.txt` - Generated prompts

## Scripts
- `scripts/batch_run_all_styles.py` - Main batch runner
- `scripts/generate_prompt.py` - Prompt generation
- `scripts/execute_llm.py` - LLM execution
- `scripts/run_single_concept.py` - Helper for single concept generation

## Usage
```bash
cd s1_generate_concepts/scripts
python batch_run_all_styles.py \
  ../inputs/configs/rolex.json \
  "Create a 30 second Instagram ad for luxury watches" \
  ../outputs
```

Note: The third argument (output directory) is optional. If omitted, outputs default to `../outputs/`.

Or use the main pipeline:
```bash
cd run_pipeline/scripts
python run_pipeline_complete.py
```

