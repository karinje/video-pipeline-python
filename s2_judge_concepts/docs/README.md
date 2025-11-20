# Step 2: Judge/Evaluate Concepts

## Overview
Evaluates each concept separately (parallel) using an LLM judge. Scores 0-100 based on:
- Narrative Quality (20 points)
- Emotional Impact (20 points)
- Brand Integration (15 points)
- Memorability (15 points)
- Visual Clarity (15 points)
- Success Likelihood (15 points)

## Inputs
- **Batch summary JSON**: From Step 1 outputs
  - `s1_generate_concepts/outputs/{brand}_{timestamp}/{brand}_batch_summary_{timestamp}.json`

## Outputs
- **Evaluation JSON**: `outputs/{brand}_evaluation_{judge_model}_{timestamp}.json`
- **Scores CSV**: `outputs/{brand}_scores_{judge_model}_{timestamp}.csv`

## Scripts
- `scripts/judge_concepts.py` - Main judging script

## Usage
```bash
cd s2_judge_concepts/scripts
python judge_concepts.py \
  ../../s1_generate_concepts/outputs/rolex_1115_1833/rolex_batch_summary_1115_1833.json \
  anthropic/claude-sonnet-4-5-20250929 \
  ../outputs
```

Arguments:
- `batch_summary.json` (required): Path to batch summary from Step 1
- `judge_model` (optional): Model to use for judging (default: `anthropic/claude-sonnet-4-5-20250929`)
- `output_dir` (optional): Output directory (default: `../outputs`)

Or use the main pipeline:
```bash
cd run_pipeline/scripts
python run_pipeline_complete.py
```

