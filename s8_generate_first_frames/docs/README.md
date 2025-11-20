# Step 8: Generate First Frame Images

## Overview
Generates the first frame image for each scene using nano-banana image generation. These images serve as the starting frame reference for video generation in Step 9, ensuring visual consistency with the universe/character reference images.

## Purpose
- **Video Continuity**: Creates first frames that match the video style exactly
- **Reference Integration**: Blends character/prop/location reference images naturally
- **Visual Consistency**: Ensures scenes maintain consistent look across the video
- **Version Matching**: Uses correct character/prop versions for each scene
- **Parallel Generation**: Processes all scenes simultaneously for speed

## What It Does

### Input
- **Scene prompts JSON** (from Step 7)
- **Universe/characters JSON** (from Step 5)
- **Reference images directory** (from Step 6)
- **Resolution and aspect ratio** (from config)

### Output
- **First frame images**: One JPG per scene
- **Summary JSON**: Metadata about generated images
- **Debug directory**: Prompts and reference images used

### Directory Structure
```
s8_generate_first_frames/outputs/{batch}/{concept}/
├── {concept}_p1_first_frame.jpg
├── {concept}_p2_first_frame.jpg
├── {concept}_p3_first_frame.jpg
├── {concept}_p4_first_frame.jpg
├── {concept}_p5_first_frame.jpg
├── first_frames_summary.json
└── debug/
    ├── scene_1/
    │   ├── first_frame_p1_prompt.txt
    │   ├── first_frame_p1_reference_1.jpg
    │   └── first_frame_p1_reference_2.jpg
    ├── scene_2/
    └── ...
```

## Key Features

### 1. Reference Image Selection
**Smart Filtering:**
- Only uses elements appearing in **2+ scenes** (multi-scene elements)
- Skips single-scene elements (video model generates those fresh)
- Prioritizes: Characters > Props > Locations
- Limits to 5 reference images (nano-banana maximum)

**Version Matching:**
- Parses version names from `elements_used` (e.g., "Character - Version Name")
- Matches exact version to scene number
- Uses correct transformation state (early vs later appearance)

**Example:**
```
Scene 1: Uses "Young Watchmaker - Struggling Apprentice"
Scene 5: Uses "Young Watchmaker - Master Craftsman"
```

### 2. Image Name Mapping
Uses `image_generation_summary.json` from Step 6 to map element names to actual file paths:
- Handles name variations (with/without parentheses)
- Matches base names (ignores descriptors)
- Resolves ambiguous names

### 3. Parallel Processing
- Generates all scenes simultaneously (5 workers default)
- Significantly faster than sequential generation
- Typical time: 10-20 seconds for 5 scenes

### 4. Debug Output
Saves complete information for each scene:
- **Prompt used**: Exact text sent to nano-banana
- **Reference images**: Copies of all reference images used
- **Element mapping**: Which elements were included

## Usage

### Standalone
```bash
python s8_generate_first_frames/scripts/generate_first_frames.py \
  <scene_prompts.json> \
  [universe_characters.json] \
  [universe_images_dir] \
  [output_dir] \
  [resolution] \
  [max_workers]
```

**Example:**
```bash
python s8_generate_first_frames/scripts/generate_first_frames.py \
  "s7_generate_scene_prompts/outputs/olin_1120_0012/olin_achievement_inspirational_advanced_claude_sonnet_4.5/olin_achievement_inspirational_advanced_claude_sonnet_4.5_scene_prompts.json" \
  "s5_generate_universe/outputs/olin_1120_0012/olin_achievement_inspirational_advanced_claude_sonnet_4.5/olin_achievement_inspirational_advanced_claude_sonnet_4.5_universe_characters.json" \
  "s6_generate_reference_images/outputs/olin_1120_0012/olin_achievement_inspirational_advanced_claude_sonnet_4.5" \
  "s8_generate_first_frames/outputs/olin_1120_0012/olin_achievement_inspirational_advanced_claude_sonnet_4.5" \
  "720p" \
  5
```

**Parameters:**
- `scene_prompts.json`: Required - scene prompts from Step 7
- `universe_characters.json`: Optional - auto-detected if not provided
- `universe_images_dir`: Optional - auto-detected if not provided
- `output_dir`: Optional - auto-detected if not provided
- `resolution`: Optional - default "480p"
- `max_workers`: Optional - default 5

### Via Pipeline
Set in `pipeline_config.yaml`:
```yaml
pipeline_steps:
  run_step_8: true

video_settings:
  resolution: 720p
  aspect_ratio: "16:9"

image_generation:
  image_parallel_workers: 5
  max_reference_images: 5

output:
  first_frames_dir: s8_generate_first_frames/outputs
```

## Configuration

### Resolution Settings
```yaml
video_settings:
  resolution: 720p  # Options: 480p, 720p, 1080p
  aspect_ratio: "16:9"  # Standard widescreen
```

**Resolution Mapping:**
- `480p`: 854×480 (16:9)
- `720p`: 1280×720 (16:9)
- `1080p`: 1920×1080 (16:9)

### Image Generation Settings
```yaml
image_generation:
  max_reference_images: 5  # nano-banana limit
  image_parallel_workers: 5  # Parallel scenes
```

### Output Directory
```yaml
output:
  first_frames_dir: s8_generate_first_frames/outputs
```

**Output Path:**
```
s8_generate_first_frames/outputs/{batch_folder}/{concept_name}/
```

## Reference Image Selection Logic

### Priority Order
1. **Characters** (highest priority)
2. **Props** (medium priority)
3. **Locations** (lowest priority)

### Multi-Scene Filtering
```python
# Only include if element appears in 2+ scenes
scenes_used = element.get("scenes_used", [])
if len(scenes_used) >= 2:
    include_in_references()
else:
    skip_element()  # Video model generates fresh
```

**Example:**
```
✓ Young Watchmaker: Scenes [1, 3, 5] → Include (3 scenes)
✓ Workshop: Scenes [1, 3, 5] → Include (3 scenes)
✗ Senior Craftsmen: Scene [2] → Skip (1 scene)
✗ Competition Judges: Scene [4] → Skip (1 scene)
✗ Mentor: Scene [5] → Skip (1 scene)
```

### Version Matching
```python
# Parse element name and version
"Young Watchmaker (Protagonist) - Struggling Apprentice"
→ base_name: "Young Watchmaker (Protagonist)"
→ version_name: "Struggling Apprentice"

# Match to correct scene
if scene_num in version.scenes_used:
    use_this_version()
```

### Maximum References
```python
# Limit to 5 images (nano-banana maximum)
references = []
references.extend(character_images[:remaining_slots])
references.extend(prop_images[:remaining_slots])
references.extend(location_images[:remaining_slots])
references = references[:5]  # Hard limit
```

## Summary JSON Structure

```json
{
  "scene_prompts_file": "path/to/scene_prompts.json",
  "universe_file": "path/to/universe_characters.json",
  "universe_images_dir": "path/to/reference/images",
  "output_dir": "path/to/output",
  "resolution": "720p",
  "aspect_ratio": "16:9",
  "generated_at": "2025-11-20 01:03:00",
  "scenes": [
    {
      "scene_number": 1,
      "first_frame_path": "olin_..._p1_first_frame.jpg",
      "reference_images_used": [
        "characters/young_watchmaker.../struggling_apprentice.jpg",
        "locations/watchmakers_workshop/watchmakers_workshop.jpg"
      ],
      "elements_used": {
        "characters": ["Young Watchmaker (Protagonist) - Struggling Apprentice"],
        "locations": ["Watchmaker's Workshop"],
        "props": []
      }
    }
  ]
}
```

## Debug Output

### Debug Directory Structure
```
debug/
├── scene_1/
│   ├── first_frame_p1_prompt.txt
│   ├── first_frame_p1_reference_1.jpg
│   └── first_frame_p1_reference_2.jpg
├── scene_2/
│   ├── first_frame_p2_prompt.txt
│   └── first_frame_p2_reference_1.jpg
└── ...
```

### Prompt File Contents
```
PROMPT:
Hyper-realistic photorealistic professional portrait photography...
[Complete first_frame_image_prompt from scene prompts]

REFERENCE IMAGES:
  1. characters/young_watchmaker_protagonist/struggling_apprentice.jpg
  2. locations/watchmakers_workshop/watchmakers_workshop.jpg

ELEMENTS USED:
Characters:
  - Young Watchmaker (Protagonist) - Struggling Apprentice (scenes: [1, 3])
Locations:
  - Watchmaker's Workshop (scenes: [1, 3, 5])
Props:
  (none)
```

## Performance

**Typical Execution:**
- **Time**: 10-20 seconds for 5 scenes (parallel)
- **Cost**: ~$0.01-0.03 per image (~$0.05-0.15 total)
- **Output**: 5 JPG files + 1 summary JSON + debug files
- **Quality**: High-resolution, photorealistic images

### Example Run
```
Parallel workers: 5
Scenes: 5
Time: 14.9 seconds
Files generated: 21 total
  - 5 first frame images
  - 1 summary JSON
  - 15 debug files (3 per scene average)
```

## Integration with Other Steps

### From Step 5 (Universe)
- Uses character/prop/location definitions
- Respects `scenes_used` for multi-scene filtering
- Handles `has_multiple_versions` for transformations

### From Step 6 (Reference Images)
- Uses generated reference images
- Reads `image_generation_summary.json` for name mapping
- Copies reference images to debug directory

### From Step 7 (Scene Prompts)
- Uses `first_frame_image_prompt` for each scene
- Reads `elements_used` for reference image selection
- Matches version names to correct images

### To Step 9 (Video Clips)
- First frame images used as video starting frame
- Ensures video continuity with reference images
- Maintains visual consistency across scenes

## Error Handling

### Common Issues

**1. Missing Reference Images**
```
DEBUG: No image found for Senior Craftsmen Group (character, scene 2)
```
**Cause:** Element only appears in 1 scene (correctly skipped)
**Solution:** Normal behavior - video model generates single-scene elements

**2. Image Generation Failure**
```
ERROR: Failed to generate first frame for scene 3: ...
```
**Cause:** Replicate API error or invalid prompt
**Solution:** Check debug prompt file, verify reference images exist, retry

**3. Version Mismatch**
```
WARNING: No matching version found for element X in scene Y
```
**Cause:** Version name in scene prompts doesn't match universe JSON
**Solution:** Check `elements_used` format matches universe version names

**4. Too Many Reference Images**
```
WARNING: 7 reference images found, limiting to 5 (nano-banana max)
```
**Cause:** More than 5 multi-scene elements
**Solution:** Normal behavior - prioritizes characters > props > locations

## Best Practices

1. **Use 720p Resolution** for balance of quality and speed
2. **Keep Max Workers at 5** for optimal parallel processing
3. **Check Debug Files** if images don't match expectations
4. **Verify Reference Images** exist before running
5. **Review Element Names** ensure they match across steps

## Troubleshooting

### Images Don't Match Video Style
1. Check `first_frame_image_prompt` in scene prompts (Step 7)
2. Verify prompt includes style, camera, lighting, mood
3. Ensure prompt matches video_prompt exactly
4. Review debug prompt file for what was actually sent

### Wrong Character Version Used
1. Check `elements_used` in scene prompts
2. Verify version name format: "Name - Version Name"
3. Check universe JSON has matching version name
4. Review image summary for correct file paths

### Missing Reference Images
1. Verify Step 6 completed successfully
2. Check `image_generation_summary.json` exists
3. Ensure reference images are in correct directory
4. Confirm element appears in 2+ scenes

### Slow Generation (>30 seconds)
1. Check Replicate API status
2. Verify parallel workers setting (should be 5)
3. Reduce number of reference images if possible
4. Check network connection

## Files
- **Script**: `s8_generate_first_frames/scripts/generate_first_frames.py`
- **Inputs**: 
  - Scene prompts JSON (from Step 7)
  - Universe/characters JSON (from Step 5)
  - Reference images directory (from Step 6)
- **Outputs**: 
  - `outputs/{batch}/{concept}/{concept}_p{N}_first_frame.jpg` (one per scene)
  - `outputs/{batch}/{concept}/first_frames_summary.json`
  - `outputs/{batch}/{concept}/debug/scene_{N}/` (prompts + references)

## Next Step
→ **Step 9**: Generate Video Clips (uses first frames as video starting frames)

## Environment Variables
```bash
# Required
REPLICATE_API_TOKEN=r8_...  # or REPLICATE_API_KEY

# Optional (for .env file)
# None - all config in pipeline_config.yaml
```

## Technical Details

### nano-banana Parameters
```python
{
    "prompt": "Hyper-realistic photorealistic...",
    "image_input": [ref1.jpg, ref2.jpg, ...],  # Up to 5
    "aspect_ratio": "16:9",  # or "match_input_image"
    "output_format": "jpg"
}
```

### Image Processing
- **Model**: `google/nano-banana` via Replicate
- **Output**: High-quality JPG images
- **Speed**: ~3-5 seconds per image
- **Parallel**: All scenes processed simultaneously

### Reference Image Blending
- nano-banana blends reference images naturally
- Not literal insertion - uses as style/appearance guide
- Maintains consistency while allowing variation
- Works best with 2-3 references per scene

## Notes
- First frame images are critical for video continuity
- Reference images ensure character/prop consistency
- Multi-scene filtering prevents redundant generation
- Version matching ensures correct transformation state
- Debug output helps troubleshoot any issues
- Parallel processing makes generation fast (10-20s total)

