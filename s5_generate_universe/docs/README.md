# Step 5: Generate Universe and Characters

## Overview
Generates detailed descriptions for characters, props, and locations that need visual consistency across multiple scenes. Creates structured JSON with image generation prompts for each element.

## Purpose
- **Visual Consistency**: Ensures characters, props, and locations look the same across scenes
- **Multi-Version Support**: Handles elements that transform (e.g., young → old character, abandoned → restored location)
- **Reference Generation**: Creates detailed prompts for AI image generation (used in Step 6)

## What It Does

### Input
- **Revised concept script** (from Step 4)
- **Brand config file** (brand context)
- **LLM model** (for generation)

### Output
- **`{concept_name}_universe_characters.json`**: Structured JSON containing:
  - **Characters**: All characters with physical descriptions
  - **Props**: Objects appearing in 2+ scenes
  - **Locations**: Settings appearing in 2+ scenes
  - **Versions**: Multiple states for transforming elements

### Key Features
1. **Multi-Scene Filtering**: Only tracks elements appearing in 2+ scenes
2. **Version Tracking**: Handles transformations (e.g., "Early Workshop" → "Master's Workshop")
3. **Image Prompts**: Each element includes detailed prompts for nano-banana image generation
4. **Hyper-Realistic Focus**: Prompts emphasize photorealistic, documentary-style imagery

## JSON Structure

```json
{
  "universe": {
    "locations": [
      {
        "name": "Workshop",
        "scenes_used": [1, 3, 5],
        "has_multiple_versions": true,
        "versions": [
          {
            "version_name": "Early Workshop",
            "scenes_used": [1, 3],
            "description": "Detailed visual description",
            "image_generation_prompt": "Complete prompt for nano-banana",
            "is_original": true
          },
          {
            "version_name": "Master's Workshop",
            "scenes_used": [5],
            "description": "Transformed version description",
            "image_generation_prompt": "Complete prompt with transformation",
            "is_original": false,
            "references_original_version": "Early Workshop"
          }
        ]
      }
    ],
    "props": [...],
  },
  "characters": [...]
}
```

## Usage

### Standalone
```bash
python s5_generate_universe/scripts/generate_universe.py \
  <revised_concept_file> \
  <config_file> \
  <output_file> \
  [model]
```

**Example:**
```bash
python s5_generate_universe/scripts/generate_universe.py \
  "s4_revise_concept/outputs/olin_1120_0012/olin_achievement_inspirational_advanced_claude_sonnet_4.5/olin_achievement_inspirational_advanced_claude_sonnet_4.5_revised.txt" \
  "s1_generate_concepts/inputs/configs/luxury_watch.json" \
  "s5_generate_universe/outputs/test_universe.json" \
  "anthropic/claude-sonnet-4-5-20250929"
```

### Via Pipeline
Set in `pipeline_config.yaml`:
```yaml
pipeline_steps:
  run_step_5: true

models:
  llm_model: anthropic/claude-sonnet-4-5-20250929
```

## Advanced Features

### 1. Anthropic Prompt Caching (2025)
- **Caches** schema and instructions (reduce costs by 90% on repeated calls)
- **Automatic**: Enabled for Claude models
- **Benefits**: 
  - Cache reads: 10% of base input token cost
  - Latency reduction: Up to 85% faster
  - 5-minute TTL (resets on each use)

### 2. Extended Thinking
- **Claude**: Uses `thinking=10000` tokens for deep reasoning
- **GPT**: Uses `reasoning_effort="high"` for max thinking
- **Result**: More comprehensive, well-structured universe descriptions

### 3. Structured Output (GPT-4o/5+)
- **JSON Schema Validation**: Guarantees valid JSON matching schema
- **Zero Parsing Errors**: No trailing commas or malformed JSON
- **Automatic**: Enabled for GPT-4o and GPT-5+ models

### 4. Robust JSON Parsing
- **Handles ThinkingBlocks**: Filters out Claude's internal reasoning
- **Auto-fixes**: Removes trailing commas, comments, extra text
- **Debug Mode**: Saves failed responses to `outputs/debug/` for inspection

## Configuration

### LLM Model Selection
```yaml
models:
  llm_model: anthropic/claude-sonnet-4-5-20250929  # or openai/gpt-5.1
```

**Recommended Models:**
- **Claude Sonnet 4.5**: Best for detailed, creative descriptions (with caching)
- **GPT-5.1**: Fast, structured output with guaranteed valid JSON

### Output Directory
```yaml
output:
  # Step 5 outputs go to separate directory
  # (Not in base_output_dir - has its own structure)
```

**Output Path:**
```
s5_generate_universe/outputs/{batch_folder}/{concept_name}/
  └── {concept_name}_universe_characters.json
```

## Implementation Details

### Prompt Caching (Claude)
```python
system = [
    {
        "type": "text",
        "text": "Schema and instructions...",
        "cache_control": {"type": "ephemeral"}  # Cache this part
    }
]
```

### ThinkingBlock Handling
```python
# Skip thinking blocks, extract only text content
for block in response.content:
    if hasattr(block, 'type') and block.type == 'thinking':
        continue  # Skip internal reasoning
    if hasattr(block, 'text'):
        content_parts.append(block.text)
```

### JSON Schema (OpenAI Structured Outputs)
```python
universe_schema = {
    "type": "object",
    "properties": {
        "universe": {...},
        "characters": {...}
    },
    "required": ["universe", "characters"],
    "additionalProperties": False
}
```

## Performance

**Typical Execution:**
- **Time**: 60-100 seconds (with extended thinking)
- **Cost**: ~$0.10-0.30 per run (with caching: ~$0.01-0.03 on cache hits)
- **Output**: 15-25KB JSON file
- **Elements**: 3-8 characters, 2-5 props, 1-3 locations

## Error Handling

### Common Issues

**1. JSON Parsing Errors**
- **Cause**: Trailing commas, malformed JSON from LLM
- **Solution**: Automatic fixes applied (regex cleanup)
- **Debug**: Check `s5_generate_universe/outputs/debug/failed_response.txt`

**2. Empty Response**
- **Cause**: Only ThinkingBlocks returned (no text content)
- **Solution**: Filter logic extracts text blocks only
- **Error**: "No text content found in Anthropic API response"

**3. Token Limits**
- **Cause**: Very long concepts or complex universes
- **Solution**: Increase `max_tokens` parameter (default: 16000)

## Best Practices

1. **Use Extended Thinking**: Better quality universe descriptions
2. **Enable Caching**: Saves 90% on costs for repeated runs
3. **Review Output**: Check JSON structure before Step 6
4. **Multi-Version Elements**: Clearly define transformation states
5. **Detailed Prompts**: More detail = better reference images in Step 6

## Next Step
→ **Step 6**: Generate Reference Images (uses universe JSON to create actual images)

## Files
- **Script**: `s5_generate_universe/scripts/generate_universe.py`
- **Inputs**: Revised concept, brand config
- **Outputs**: `outputs/{batch}/{concept}/{concept}_universe_characters.json`

