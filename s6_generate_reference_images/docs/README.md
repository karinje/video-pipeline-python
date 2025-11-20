# Step 6: Generate Reference Images

## Overview
Generates hyper-realistic reference images for all characters, props, and locations defined in the universe JSON (from Step 5). Uses Replicate's nano-banana model to create photorealistic images that ensure visual consistency across video scenes.

## Purpose
- **Visual Consistency**: Create reference images for elements appearing in multiple scenes
- **Character Continuity**: Ensure characters look the same across different scenes
- **Prop/Location Tracking**: Generate images for recurring objects and settings
- **Multi-Version Support**: Handle transformations (e.g., young → old, abandoned → restored)

## What It Does

### Input
- **Universe/Characters JSON** (from Step 5)
- **Image generation model** (nano-banana via Replicate)
- **Max workers** (parallel processing)

### Output
- **Reference Images**: JPG files for each element/version
- **Summary JSON**: Metadata about generated images
- **Debug Info**: Prompts and reference images used

### Directory Structure
```
s6_generate_reference_images/outputs/{batch}/{concept}/
├── characters/
│   └── {character_name}/
│       ├── {character}_{version}_scenes_{X_Y}.jpg
│       └── ...
├── props/
│   └── {prop_name}/
│       ├── {prop}_{version}_scene_{X}.jpg
│       └── ...
├── locations/
│   └── {location_name}/
│       └── {location}.jpg
├── debug/
│   └── {element}_{version}_prompt.txt
└── image_generation_summary.json
```

## Key Features

### 1. Multi-Scene Filtering
- **Only processes elements appearing in 2+ scenes**
- Skips single-scene elements (video model generates those fresh)
- Reduces unnecessary image generation

### 2. Sequential Version Generation
- **Original version** generated first (no reference image)
- **Transformed versions** use original as reference
- Ensures visual continuity across transformations

### 3. Parallel Processing
- **Multiple elements** processed in parallel (max 5 workers)
- **Versions within element** processed sequentially
- Optimizes speed while maintaining consistency

### 4. Reference Image Handling
- **File Upload**: Replicate SDK auto-uploads local files
- **URL Support**: Can use URLs as reference images
- **Fallback**: Uses file paths when URLs unavailable

## Usage

### Standalone
```bash
python s6_generate_reference_images/scripts/generate_universe_images.py \
  <universe_characters.json>
```

**Example:**
```bash
python s6_generate_reference_images/scripts/generate_universe_images.py \
  "s5_generate_universe/outputs/olin_1120_0012/olin_achievement_inspirational_advanced_claude_sonnet_4.5/olin_achievement_inspirational_advanced_claude_sonnet_4.5_universe_characters.json"
```

### Via Pipeline
Set in `pipeline_config.yaml`:
```yaml
pipeline_steps:
  run_step_6: true

image_generation:
  image_parallel_workers: 5  # Parallel workers
  
models:
  image_model: google/nano-banana
```

## Configuration

### Image Generation Settings
```yaml
image_generation:
  max_reference_images: 5  # Max refs for first frames (Step 7)
  image_parallel_workers: 5  # Parallel processing
```

### Output Directory
```yaml
output:
  universe_images_dir: s6_generate_reference_images/outputs
```

**Output Path:**
```
s6_generate_reference_images/outputs/{batch}/{concept}/
```

## Image Generation Process

### 1. Characters (Multi-Version)
```
Character: "Young Watchmaker"
├── Version 1: "Struggling Apprentice" (Scenes 1, 3)
│   └── Generate with prompt only (no reference)
└── Version 2: "Master Craftsman" (Scenes 4, 5)
    └── Generate with Version 1 as reference image
```

### 2. Props (Multi-Version)
```
Prop: "Gold Olin Watch"
├── Version 1: "Benchmark Watch" (Scene 3)
│   └── Generate with prompt only
└── Version 2: "Engraved Gift Watch" (Scene 5)
    └── Generate with Version 1 as reference
```

### 3. Locations (Single Version)
```
Location: "Watchmaker's Workshop"
└── Generate with prompt only (no reference)
```

## nano-banana Parameters

### Input Parameters
```python
{
    "prompt": "Hyper-realistic photorealistic...",
    "aspect_ratio": "16:9",  # or "match_input_image" for versions
    "output_format": "jpg",
    "image_input": [file_path]  # For transformed versions only
}
```

### Model Details
- **Model**: `google/nano-banana`
- **Provider**: Replicate
- **Output**: High-quality JPG images
- **Speed**: ~3-5 seconds per image

## Summary JSON

### Structure
```json
{
  "json_file": "path/to/universe_characters.json",
  "json_prefix": "concept_name",
  "generated_at": "2025-11-20 00:36:00",
  "elements": [
    {
      "type": "character",
      "name": "Young Watchmaker",
      "has_multiple_versions": true,
      "versions": [
        {
          "version_name": "Struggling Apprentice",
          "scenes_used": [1, 3],
          "image_path": "characters/.../struggling_apprentice.jpg",
          "prompt": "Hyper-realistic...",
          "reference_images": null
        },
        {
          "version_name": "Master Craftsman",
          "scenes_used": [4, 5],
          "image_path": "characters/.../master_craftsman.jpg",
          "prompt": "Hyper-realistic...",
          "reference_images": ["path/to/struggling_apprentice.jpg"]
        }
      ]
    }
  ]
}
```

## Debug Information

### Debug Directory
```
s6_generate_reference_images/outputs/{batch}/{concept}/debug/
├── {element}_{version}_prompt.txt
├── {element}_{version}_reference_1.jpg
└── ...
```

### Prompt File Contents
```
PROMPT:
Hyper-realistic photorealistic ultra-realistic professional portrait...

REFERENCE IMAGES:
  1. path/to/reference.jpg
      (Local file path)
```

## Performance

**Typical Execution:**
- **Time**: 15-30 seconds (3-8 images, parallel)
- **Cost**: ~$0.01-0.03 per image (Replicate pricing)
- **Output**: 3-8 JPG files + 1 summary JSON
- **Quality**: High-resolution, photorealistic images

### Example Run
```
Processing 3 elements in parallel:
  ✓ Character: Young Watchmaker (2 versions) - 8 seconds
  ✓ Prop: Gold Olin Watch (2 versions) - 7 seconds  
  ✓ Location: Workshop (1 version) - 4 seconds
Total: 17.8 seconds
```

## Error Handling

### Common Issues

**1. Replicate API Token Missing**
```
ERROR: REPLICATE_API_TOKEN or REPLICATE_API_KEY not found
```
**Solution**: Add to `.env` file:
```
REPLICATE_API_TOKEN=your_token_here
```

**2. No URL from Replicate**
```
⚠ No URL from Replicate - will try file object for next version
```
**Cause**: Normal behavior - Replicate returns file object instead of URL
**Solution**: Automatic - file path used for next version

**3. Image Generation Failed**
```
✗ Error processing character Young Watchmaker: ...
```
**Solution**: Check debug files, verify prompt quality, retry

## Best Practices

1. **Use Detailed Prompts**: More detail = better image quality
2. **Sequential Versions**: Always generate original before transformed
3. **Check Debug Files**: Review prompts and references if issues occur
4. **Parallel Processing**: Use 5 workers for optimal speed
5. **Monitor Costs**: Each image costs ~$0.01-0.03 on Replicate

## Integration with Other Steps

### From Step 5
- Reads universe/characters JSON
- Uses `image_generation_prompt` field for each element
- Respects `scenes_used` and `has_multiple_versions`

### To Step 7 (First Frames)
- Reference images used to generate first frames
- Summary JSON provides image paths
- Ensures character/prop consistency in first frames

### To Step 8 (Video Clips)
- First frames (from Step 7) used as video input
- Reference images ensure consistency across clips

## Files
- **Script**: `s6_generate_reference_images/scripts/generate_universe_images.py`
- **Inputs**: Universe/characters JSON (from Step 5)
- **Outputs**: 
  - `outputs/{batch}/{concept}/characters/*.jpg`
  - `outputs/{batch}/{concept}/props/*.jpg`
  - `outputs/{batch}/{concept}/locations/*.jpg`
  - `outputs/{batch}/{concept}/image_generation_summary.json`
  - `outputs/{batch}/{concept}/debug/*` (prompts, references)

## Next Step
→ **Step 7**: Generate Scene Prompts (uses universe JSON and reference images)

## Environment Variables
```bash
# Required
REPLICATE_API_TOKEN=r8_...  # or REPLICATE_API_KEY

# Optional (for .env file)
# None - all config in pipeline_config.yaml
```

## Troubleshooting

### Images Look Wrong
1. Check debug prompts: `outputs/.../debug/{element}_prompt.txt`
2. Verify reference images are correct
3. Improve prompt detail in Step 5
4. Regenerate with better prompts

### Slow Generation
1. Increase `image_parallel_workers` (max 5-10)
2. Check Replicate API status
3. Reduce number of versions if possible

### File Not Found Errors
1. Verify Step 5 completed successfully
2. Check universe JSON path is correct
3. Ensure output directory is writable

