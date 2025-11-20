# Step 3: Extract Best Concept from Evaluation

## Overview
Extracts the highest-scoring concept from the evaluation JSON generated in Step 2. Identifies the best concept based on judge scores and saves metadata for use in downstream steps.

## Inputs
- **Evaluation JSON**: From Step 2 outputs
  - `s2_judge_concepts/outputs/{brand}_evaluation_{judge_model}_{timestamp}.json`

## Outputs
- **Best concept metadata JSON**: `outputs/{brand}_{judge_model}_{timestamp}_best_concept.json`
  - Contains file path, score, model, template, ad_style, strengths, weaknesses

## Scripts
- `scripts/extract_best_concept.py` - Main extraction script

## Usage
```bash
cd s3_extract_best_concept/scripts
python extract_best_concept.py \
  ../../s2_judge_concepts/outputs/olin_evaluation_claude_4.5_1119_2258.json \
  ../outputs
```

Arguments:
- `evaluation_json` (required): Path to evaluation JSON from Step 2
- `output_dir` (optional): Output directory (default: same directory as evaluation file)

Or use the main pipeline:
```bash
cd run_pipeline/scripts
python run_pipeline_complete.py
```

## Output Format
The best concept metadata JSON contains:
- `evaluation_file`: Path to source evaluation
- `extracted_at`: Timestamp when extracted
- `best_concept`: Object with:
  - `file`: Path to concept file
  - `score`: Judge score (0-100)
  - `model`: LLM model used
  - `template`: Template used (generic/advanced)
  - `provider`: LLM provider
  - `ad_style`: Ad style category
  - `brand_name`: Brand name
  - `strengths`: List of strengths identified by judge
  - `weaknesses`: List of weaknesses identified by judge
  - `explanation`: Judge's explanation

