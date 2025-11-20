# Step 4: Revise Concept Based on Judge Feedback

## Overview
Takes the best-scoring concept from Step 3 and revises it to address judge-identified weaknesses. Makes strategic improvements while maintaining core strengths and ensures scenes are appropriately paced for video generation. Optionally re-judges the revised concept to measure improvement.

## Inputs
- **Best concept file**: From Step 3 (extracted from evaluation)
  - Path: `s1_generate_concepts/outputs/{batch_folder}/{concept_name}.txt`
- **Evaluation JSON**: From Step 2
  - Contains weaknesses identified by the judge
  - Path: `s2_judge_concepts/outputs/{brand}_evaluation_{judge_model}_{timestamp}.json`
- **Brand config file**: From Step 1 inputs
  - Path: `s1_generate_concepts/inputs/configs/{brand}.json`
- **Duration**: Video duration in seconds (from pipeline config)
- **LLM model**: Model for revision (from pipeline config)

## Outputs
- **Revised script**: `outputs/{batch_folder}/{concept_name}/{concept_name}_revised.txt`
  - Improved concept addressing judge weaknesses
- **Re-evaluation JSON**: `outputs/{batch_folder}/{concept_name}/{concept_name}_revised_evaluation.json`
  - Comparative evaluation comparing original vs revised
  - Contains improvement score, winner, and recommendation

## Scripts
- `scripts/generate_video_script.py` - Main script with `revise_script_for_video()` function

## Usage

### Standalone (Full Script Generation)
The standalone script does more than just revision - it generates the full video script pipeline:
```bash
cd s4_revise_concept/scripts
python generate_video_script.py \
  ../../s2_judge_concepts/outputs/olin_evaluation_claude_4.5_1119_2338.json \
  ../../s1_generate_concepts/inputs/configs/luxury_watch.json \
  30 \
  anthropic/claude-sonnet-4-5-20250929
```

Arguments:
- `evaluation_json` (required): Path to evaluation JSON from Step 2
- `config_json` (required): Path to brand config JSON file
- `duration` (optional): Video duration in seconds (default: 30)
- `model` (optional): LLM model for revision (default: anthropic/claude-sonnet-4-5-20250929)

**Note:** The standalone script generates revised script, universe/characters, and scene prompts. In the pipeline, these are separate steps.

### Pipeline Integration
In the pipeline, Step 4 only calls the `revise_script_for_video()` function:
```python
from generate_video_script import revise_script_for_video

revised_script = revise_script_for_video(
    concept_content,      # Best concept text
    config_data,          # Brand config
    llm_model,            # Revision model
    duration,             # Video duration
    weaknesses            # List of weaknesses from evaluation
)
```

The pipeline handles:
- Loading the best concept from Step 3
- Extracting weaknesses from evaluation
- Calling the revision function
- Saving the revised script
- Optional comparative re-judging

## Output Format

### Revised Script
The revised script is a text file containing the improved 5-scene concept with:
- Addressed weaknesses from judge feedback
- Maintained core strengths
- Appropriate pacing for video generation
- Enhanced visual clarity and narrative flow

### Re-evaluation JSON
```json
{
  "original_evaluation": {
    "score": 82,
    "weaknesses": [...],
    "strengths": [...],
    ...
  },
  "revised_evaluation": {
    "comparison": {
      "original_score": 82,
      "revised_score": 87,
      "improvement": 5,
      "winner": "revised",
      "explanation": "...",
      "weaknesses_addressed": [...],
      "new_weaknesses_introduced": [],
      "recommendation": "Use revised"
    },
    "judge_model": "anthropic/claude-sonnet-4-5-20250929",
    "method": "comparative"
  },
  "improvement": 5
}
```

## Configuration

In `run_pipeline/configs/pipeline_config.yaml`:
```yaml
pipeline_steps:
  run_step_4: true  # Enable/disable Step 4

video_settings:
  total_duration: 30  # Or use duration_seconds (legacy)
  # Or use clip_duration + num_clips

models:
  llm_model: anthropic/claude-sonnet-4-5-20250929  # Revision model

evaluation:
  judge_model: anthropic/claude-sonnet-4-5-20250929  # Re-judging model

output:
  base_output_dir: s4_revise_concept/outputs  # Output directory
```

## Notes
- The revision process is surgical - it makes minimal changes to address weaknesses while preserving strengths
- Comparative re-judging is always enabled in the pipeline to measure improvement
- If the revised version scores lower, the pipeline uses the original concept for downstream steps
- The standalone script (`generate_video_script.py`) does more than Step 4 - it's a full script generation pipeline that includes universe/character generation and scene prompts

