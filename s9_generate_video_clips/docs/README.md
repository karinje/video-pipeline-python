# Step 9: Generate Video Clips

## Overview
Generates individual video clips for each scene using OpenAI Sora 2, Google Veo 3 Fast, or Google Veo 3.1 Fast via Replicate. Takes first frame images, scene prompts, and audio descriptions to create 4-8 second video clips with synchronized audio.

## Purpose
- **Video Generation**: Creates high-quality video clips from first frame images
- **Audio Integration**: Generates synchronized background music and dialogue
- **Model Flexibility**: Supports multiple video generation models (Sora-2, Veo 3 Fast, Veo 3.1 Fast)
- **Parallel Processing**: Generates multiple clips simultaneously for speed
- **Visual Continuity**: Uses first frame images to ensure scene consistency

## What It Does

### Input
- **Scene prompts JSON** (from Step 7) - Contains video prompts, audio descriptions
- **First frame images** (from Step 8) - Starting frame for each scene
- **Video model** (from config) - Sora-2, Veo 3 Fast, or Veo 3.1 Fast
- **Aspect ratio and duration** (from config)

### Output
- **Video clips**: One MP4 per scene (4-8 seconds each)
- **Debug directory**: Prompts and API input data for each scene

### Directory Structure
```
s9_generate_video_clips/outputs/{batch}/{concept}/
├── {concept}_p1_veo_3.1_fast.mp4
├── {concept}_p2_veo_3.1_fast.mp4
├── {concept}_p3_veo_3.1_fast.mp4
├── {concept}_p4_veo_3.1_fast.mp4
├── {concept}_p5_veo_3.1_fast.mp4
└── debug/
    ├── scene_1/
    │   └── veo3_p1_prompt.txt
    ├── scene_2/
    │   └── veo3_p2_prompt.txt
    └── ...
```

## Key Features

### 1. Multiple Video Models
Supports three video generation models:

**OpenAI Sora-2:**
- Model: `openai/sora-2`
- Durations: 4, 8, or 12 seconds
- Aspect ratios: `landscape` (16:9) or `portrait` (9:16)
- Parameters: `prompt`, `seconds`, `aspect_ratio`, `input_reference`

**Google Veo 3 Fast:**
- Model: `google/veo-3-fast`
- Durations: 4, 6, or 8 seconds
- Resolution: 720p
- Aspect ratio: 16:9
- Audio: Generated automatically
- Parameters: `image`, `prompt`, `duration`, `resolution`, `aspect_ratio`, `generate_audio`

**Google Veo 3.1 Fast:**
- Model: `google/veo-3.1-fast` (recommended)
- Durations: 4, 6, or 8 seconds
- Resolution: 720p
- Aspect ratio: 16:9
- Audio: Generated automatically
- Parameters: `image`, `prompt`, `duration`, `resolution`, `aspect_ratio`, `generate_audio`
- Faster and more cost-effective than Veo 3 Fast

### 2. Parallel Execution
- Generates multiple clips simultaneously (3 workers default)
- Significantly faster than sequential generation
- Typical time: 2-3 minutes for 5 scenes (vs 8-10 minutes sequential)
- Automatic rate limiting to avoid API throttling

### 3. Prompt Combination
Combines multiple prompt components:
- **Video prompt**: Main visual description
- **Audio background**: Music and sound effects description
- **Audio dialogue**: Character dialogue with voice characteristics

**Example:**
```
Video Prompt: A young watchmaker works at a wooden bench...
Background Music: Upbeat, inspiring orchestral music...
Dialogue: Narrator (warm, encouraging voice): "Every master was once a beginner..."
```

### 4. First Frame Integration
- Uploads first frame image to Replicate
- Uses as starting frame for video generation
- Ensures visual continuity with reference images
- Maintains character/prop consistency across scenes

### 5. Debug Output
Saves complete information for each scene:
- **Prompt breakdown**: Video, audio background, dialogue
- **API input data**: Exact parameters sent to Replicate
- **Image URI**: Uploaded first frame image URL
- **Model settings**: Duration, resolution, aspect ratio

## Usage

### Standalone
```bash
python s9_generate_video_clips/scripts/generate_sora2_clip.py \
  <scene_prompts.json> \
  <scene_number> \
  <first_frame_image_path> \
  [output_path]
```

**Example:**
```bash
python s9_generate_video_clips/scripts/generate_sora2_clip.py \
  "s7_generate_scene_prompts/outputs/olin_1120_0012/olin_achievement_inspirational_advanced_claude_sonnet_4.5/olin_achievement_inspirational_advanced_claude_sonnet_4.5_scene_prompts.json" \
  1 \
  "s8_generate_first_frames/outputs/olin_1120_0012/olin_achievement_inspirational_advanced_claude_sonnet_4.5/olin_achievement_inspirational_advanced_claude_sonnet_4.5_p1_first_frame.jpg"
```

**Parameters:**
- `scene_prompts.json`: Required - scene prompts from Step 7
- `scene_number`: Required - scene number (1-5)
- `first_frame_image_path`: Required - first frame image from Step 8
- `output_path`: Optional - auto-generated if not provided

### Via Pipeline
Set in `pipeline_config.yaml`:
```yaml
pipeline_steps:
  run_step_9: true

video_settings:
  video_model: google/veo-3.1-fast  # or "openai/sora-2" or "google/veo-3-fast"
  aspect_ratio: "16:9"
  duration_seconds: 8

output:
  video_outputs_dir: s9_generate_video_clips/outputs
```

## Configuration

### Video Model Selection
```yaml
video_settings:
  video_model: google/veo-3.1-fast
  # Options:
  #   - "openai/sora-2" (4, 8, or 12 seconds)
  #   - "google/veo-3-fast" (4, 6, or 8 seconds)
  #   - "google/veo-3.1-fast" (4, 6, or 8 seconds) - Recommended
```

**Model Comparison:**
| Model | Speed | Cost | Quality | Audio | Recommended |
|-------|-------|------|---------|-------|-------------|
| Sora-2 | Medium | High | Excellent | No | For highest quality |
| Veo 3 Fast | Fast | Medium | Good | Yes | Balanced option |
| Veo 3.1 Fast | Fastest | Low | Good | Yes | **Best for speed/cost** |

### Duration Settings
```yaml
video_settings:
  duration_seconds: 8  # Will be adjusted to valid duration for model
```

**Valid Durations:**
- **Sora-2**: 4, 8, or 12 seconds
- **Veo 3/3.1 Fast**: 4, 6, or 8 seconds

The script automatically adjusts to the nearest valid duration if your setting doesn't match.

### Aspect Ratio
```yaml
video_settings:
  aspect_ratio: "16:9"  # Standard widescreen
  # Options: "16:9", "9:16", "1:1"
```

**Sora-2 Mapping:**
- `16:9` → `landscape`
- `9:16` → `portrait`
- Other → defaults to `landscape`

**Veo 3/3.1 Fast:**
- Supports `16:9`, `9:16`, `1:1` directly

### Parallel Workers
```yaml
# In pipeline code (hardcoded, can be adjusted)
max_workers: 3  # Concurrent video generations
```

**Recommendation:**
- **3 workers**: Good balance (default)
- **2 workers**: More conservative (if hitting rate limits)
- **4-5 workers**: Faster but may hit API limits

### Output Directory
```yaml
output:
  video_outputs_dir: s9_generate_video_clips/outputs
```

**Output Path:**
```
s9_generate_video_clips/outputs/{batch_folder}/{concept_name}/
```

## Model-Specific Details

### OpenAI Sora-2
```python
input_data = {
    "prompt": combined_prompt,
    "seconds": 8,  # 4, 8, or 12
    "aspect_ratio": "landscape",  # or "portrait"
    "input_reference": image_uri
}
```

**Characteristics:**
- Highest quality output
- No audio generation
- Longer generation time
- Higher cost per clip

### Google Veo 3 Fast
```python
input_data = {
    "image": image_uri,
    "prompt": combined_prompt,
    "duration": 8,  # 4, 6, or 8
    "resolution": "720p",
    "aspect_ratio": "16:9",
    "generate_audio": True
}
```

**Characteristics:**
- Good quality with audio
- Faster than Sora-2
- Lower cost
- 720p resolution

### Google Veo 3.1 Fast (Recommended)
```python
input_data = {
    "image": image_uri,
    "prompt": combined_prompt,
    "duration": 8,  # 4, 6, or 8
    "resolution": "720p",
    "aspect_ratio": "16:9",
    "generate_audio": True
}
```

**Characteristics:**
- Fastest generation
- Lowest cost
- Good quality with audio
- 720p resolution
- Best for parallel processing

## Debug Output

### Debug Directory Structure
```
debug/
├── scene_1/
│   └── veo3_p1_prompt.txt
├── scene_2/
│   └── veo3_p2_prompt.txt
└── ...
```

### Prompt File Contents
```
================================================================================
VEO 3.1 FAST PROMPT (EXACT SENT TO API)
================================================================================

Model: google/veo-3.1-fast
Scene Number: 1
First Frame Image: /path/to/p1_first_frame.jpg
Duration: 8 seconds
Aspect Ratio: 16:9
Resolution: 720p
Generate Audio: True

COMBINED PROMPT:
--------------------------------------------------------------------------------
A young watchmaker works at a wooden bench...

Background Music: Upbeat, inspiring orchestral music...

Narrator (warm, encouraging voice): "Every master was once a beginner..."
--------------------------------------------------------------------------------

BREAKDOWN:
Video Prompt: A young watchmaker works at a wooden bench...
Audio Background: Upbeat, inspiring orchestral music...
Audio Dialogue: Narrator (warm, encouraging voice): "Every master was once a beginner..."

First Frame Image URI: https://api.replicate.com/v1/files/...

================================================================================
FULL API INPUT DATA:
================================================================================
image: https://api.replicate.com/v1/files/...
prompt: [full combined prompt]
duration: 8
resolution: 720p
aspect_ratio: 16:9
generate_audio: True
```

## Performance

**Typical Execution (Veo 3.1 Fast, Parallel):**
- **Time**: 2-3 minutes for 5 scenes (parallel)
- **Cost**: ~$0.10-0.20 per clip (~$0.50-1.00 total)
- **Output**: 5 MP4 files (2-4MB each) + debug files
- **Quality**: 720p, 8 seconds, with audio

**Sequential vs Parallel:**
- **Sequential**: 8-10 minutes (1.5-2 min per clip)
- **Parallel (3 workers)**: 2-3 minutes (4-5x faster)

### Example Run
```
Parallel workers: 3
Scenes: 5
Model: Veo 3.1 Fast
Time: 113.6 seconds (1.9 minutes)
Files generated: 9 total
  - 4 video clips (Scene 5 failed - content filter)
  - 5 debug prompt files
Success rate: 4/5 (80%)
```

## Integration with Other Steps

### From Step 7 (Scene Prompts)
- Uses `video_prompt` for visual description
- Uses `audio_background` for music/sound effects
- Uses `audio_dialogue` for character dialogue
- Reads `duration_seconds` for clip length
- Reads `scene_number` for output naming

### From Step 8 (First Frames)
- Uses first frame images as video starting frame
- Uploads images to Replicate for API
- Maintains visual consistency with reference images

### To Step 10 (Merge Clips)
- Generated clips used as input for final video
- Clips merged in scene order
- Final video includes all scenes sequentially

## Error Handling

### Common Issues

**1. Content Filter (E005)**
```
✗ Scene 5 failed: The input or output was flagged as sensitive. Please try again with different inputs. (E005)
```
**Cause:** Google's content filter flagged the prompt/image
**Solution:** 
- Review prompt in debug file
- Adjust sensitive content in scene prompts
- Try different first frame image
- May need to regenerate scene prompts (Step 7)

**2. Missing First Frame**
```
✗ Scene 1: First frame not found, skipping
```
**Cause:** First frame image doesn't exist
**Solution:** 
- Verify Step 8 completed successfully
- Check first frame path is correct
- Ensure file exists in expected location

**3. API Rate Limit**
```
✗ Failed: Rate limit exceeded
```
**Cause:** Too many concurrent requests
**Solution:**
- Reduce `max_workers` from 3 to 2
- Add delay between requests
- Check Replicate account limits

**4. Invalid Duration**
```
⚠ Duration adjusted from 7s to 8s (Veo 3.1 Fast requirement)
```
**Cause:** Duration not in valid range for model
**Solution:** Normal behavior - script auto-adjusts to nearest valid duration

**5. Image Upload Failure**
```
✗ Failed: Could not upload image
```
**Cause:** Network issue or invalid image file
**Solution:**
- Check network connection
- Verify image file is valid JPG
- Check Replicate API status
- Retry the generation

## Best Practices

1. **Use Veo 3.1 Fast** for best speed/cost balance
2. **Keep Parallel Workers at 3** for optimal performance
3. **Check Debug Files** if clips don't match expectations
4. **Review Prompts** before generation to avoid content filters
5. **Verify First Frames** exist before running
6. **Monitor API Costs** - video generation is expensive
7. **Test Single Scene** before running full batch

## Troubleshooting

### Clips Don't Match First Frame
1. Check first frame image quality
2. Verify prompt matches visual style
3. Review debug prompt file
4. Ensure first frame was uploaded correctly

### Audio Missing or Poor Quality
1. Verify `generate_audio: True` in API input
2. Check audio descriptions in scene prompts
3. Review debug file for audio prompt inclusion
4. Note: Sora-2 doesn't generate audio

### Slow Generation (>5 minutes)
1. Check Replicate API status
2. Verify parallel workers setting (should be 3)
3. Check network connection
4. Review API rate limits

### Content Filter Errors
1. Review prompt in debug file
2. Check for sensitive content
3. Adjust scene prompts (Step 7)
4. Try different first frame image
5. May need to regenerate with different approach

### Wrong Model Used
1. Check `video_model` in `pipeline_config.yaml`
2. Verify model name is exact: `google/veo-3.1-fast`
3. Check script default parameter
4. Review debug file for actual model used

## Files
- **Script**: `s9_generate_video_clips/scripts/generate_sora2_clip.py`
- **Inputs**: 
  - Scene prompts JSON (from Step 7)
  - First frame images (from Step 8)
- **Outputs**: 
  - `outputs/{batch}/{concept}/{concept}_p{N}_{model_suffix}.mp4` (one per scene)
  - `outputs/{batch}/{concept}/debug/scene_{N}/veo3_p{N}_prompt.txt` (debug files)

## Next Step
→ **Step 10**: Merge Video Clips (combines all clips into final video)

## Environment Variables
```bash
# Required
REPLICATE_API_TOKEN=r8_...  # or REPLICATE_API_KEY

# Optional (for .env file)
# None - all config in pipeline_config.yaml
```

## Technical Details

### Replicate API Integration
```python
# Upload image first
client = replicate.Client(api_token=api_token)
with open(first_frame_path, "rb") as f:
    file_obj = client.files.create(f)
    image_uri = file_obj.urls["get"]

# Generate video
output = replicate.run(
    "google/veo-3.1-fast",
    input={
        "image": image_uri,
        "prompt": combined_prompt,
        "duration": 8,
        "resolution": "720p",
        "aspect_ratio": "16:9",
        "generate_audio": True
    }
)

# Save output
with open(output_path, "wb") as f:
    f.write(output.read())
```

### Output Handling
The script handles different Replicate output types:
- **FileOutput object**: Uses `.read()` method (Veo 3.1 Fast)
- **URL string**: Downloads via `urllib.request`
- **Iterator**: Iterates and writes chunks

### Parallel Execution
```python
with ThreadPoolExecutor(max_workers=3) as executor:
    future_to_task = {
        executor.submit(generate_clip_task, task): task 
        for task in tasks
    }
    
    for future in as_completed(future_to_task):
        result = future.result()
        # Handle result
```

## Notes
- Video generation is the most expensive step in the pipeline
- Parallel execution significantly reduces total time
- Veo 3.1 Fast is recommended for best speed/cost balance
- Content filters may block some scenes - review prompts carefully
- Debug files are essential for troubleshooting
- First frame images are critical for visual continuity
- Audio generation adds to cost but improves final video quality

