# Step 10: Merge Video Clips into Final Video

## Overview
Merges all individual video clips from Step 9 into a single final video using FFmpeg. Combines scenes in sequential order to create the complete video narrative.

## Purpose
- **Video Assembly**: Combines all scene clips into one cohesive video
- **Sequential Ordering**: Ensures scenes are merged in correct narrative sequence
- **Efficient Processing**: Uses FFmpeg stream copy (no re-encoding) for fast merging
- **Output Organization**: Saves final video to dedicated outputs directory

## What It Does

### Input
- **Video clips** (from Step 9) - Individual MP4 files for each scene
- **Scene prompts JSON** (from Step 7) - Defines scene order
- **Model suffix** - Identifies which video model was used (e.g., "veo_3.1_fast", "sora2")

### Output
- **Final merged video**: Single MP4 file with all scenes combined
- **Output directory**: `s10_merge_clips/outputs/{batch}/{concept}/`

### Directory Structure
```
s10_merge_clips/outputs/{batch}/{concept}/
└── {concept}_final_{model_suffix}.mp4

Example:
s10_merge_clips/outputs/olin_1120_0012/olin_achievement_inspirational_advanced_claude_sonnet_4.5/
└── olin_achievement_inspirational_advanced_claude_sonnet_4.5_final_veo_3.1_fast.mp4
```

## Key Features

### 1. FFmpeg Stream Copy
- **No Re-encoding**: Uses `-c copy` to copy video/audio streams directly
- **Fast Processing**: Typically completes in 1-5 seconds
- **Quality Preservation**: No quality loss from re-encoding
- **Efficient**: Minimal CPU usage

### 2. Automatic Scene Ordering
- Reads scene numbers from `scene_prompts.json`
- Merges clips in sequential order (Scene 1, 2, 3, 4, 5...)
- Handles missing scenes gracefully (warns but continues)

### 3. Model Suffix Detection
- Automatically detects video model from file names
- Supports: `veo_3.1_fast`, `veo_3_fast`, `sora2`, `veo3`, etc.
- Falls back to generic naming if suffix not found

### 4. Output Directory Organization
- **Separate from clips**: Final video saved in dedicated `s10_merge_clips/outputs/` directory
- **Consistent structure**: Follows same `{batch}/{concept}/` pattern as other steps
- **Easy to find**: Final video clearly separated from individual clips

## Usage

### Standalone
```bash
python s10_merge_clips/scripts/merge_video_clips_ffmpeg.py \
  <scene_prompts.json> \
  [video_dir] \
  [output_filename] \
  [model_suffix]
```

**Example:**
```bash
python s10_merge_clips/scripts/merge_video_clips_ffmpeg.py \
  "s7_generate_scene_prompts/outputs/olin_1120_0012/olin_achievement_inspirational_advanced_claude_sonnet_4.5/olin_achievement_inspirational_advanced_claude_sonnet_4.5_scene_prompts.json" \
  "s9_generate_video_clips/outputs/olin_1120_0012/olin_achievement_inspirational_advanced_claude_sonnet_4.5" \
  "s10_merge_clips/outputs/olin_1120_0012/olin_achievement_inspirational_advanced_claude_sonnet_4.5/olin_achievement_inspirational_advanced_claude_sonnet_4.5_final_veo_3.1_fast.mp4" \
  "veo_3.1_fast"
```

**Parameters:**
- `scene_prompts.json`: Required - defines scene order
- `video_dir`: Optional - directory containing video clips (auto-detected if not provided)
- `output_filename`: Optional - output file path (auto-generated if not provided)
- `model_suffix`: Optional - model identifier (default: "veo3")

### Via Pipeline
Set in `pipeline_config.yaml`:
```yaml
pipeline_steps:
  run_step_10: true

output:
  merge_outputs_dir: s10_merge_clips/outputs
```

## Configuration

### Output Directory
```yaml
output:
  merge_outputs_dir: s10_merge_clips/outputs
  # Directory for final merged video
  # Step 10 output
```

**Output Path:**
```
s10_merge_clips/outputs/{batch_folder}/{concept_name}/{concept_name}_final_{model_suffix}.mp4
```

### Pipeline Step Control
```yaml
pipeline_steps:
  run_step_10: true  # Set to false to skip merging
```

## Technical Details

### FFmpeg Command
```bash
ffmpeg \
  -f concat \
  -safe 0 \
  -i concat_list.txt \
  -c copy \
  -y \
  output_video.mp4
```

**Parameters:**
- `-f concat`: Use concat demuxer
- `-safe 0`: Allow absolute paths in concat file
- `-i concat_list.txt`: Input file list
- `-c copy`: Copy streams without re-encoding
- `-y`: Overwrite output file if exists

### Concat File Format
The script creates a temporary `concat_list.txt` file:
```
file '/absolute/path/to/scene_1.mp4'
file '/absolute/path/to/scene_2.mp4'
file '/absolute/path/to/scene_3.mp4'
...
```

### Video File Detection
The script looks for video files in this order:
1. `{concept}_p{scene_num}_{model_suffix}.mp4` (e.g., `concept_p1_veo_3.1_fast.mp4`)
2. `{concept}_p{scene_num}.mp4` (fallback without suffix)

## Performance

**Typical Execution:**
- **Time**: 1-5 seconds for 5 scenes
- **CPU**: Minimal (stream copy, no encoding)
- **Output**: Single MP4 file (combined size of all clips)
- **Quality**: No quality loss (direct stream copy)

**Example Run:**
```
Found 5 scenes to merge
  ✓ Scene 1: concept_p1_veo_3.1_fast.mp4
  ✓ Scene 2: concept_p2_veo_3.1_fast.mp4
  ✓ Scene 3: concept_p3_veo_3.1_fast.mp4
  ✓ Scene 4: concept_p4_veo_3.1_fast.mp4
  ✗ Scene 5: Video file not found

⚠ Warning: Missing scenes: [5]

Merging 4 clips using ffmpeg...
Output: s10_merge_clips/outputs/.../concept_final_veo_3.1_fast.mp4

✓ Final video saved: .../concept_final_veo_3.1_fast.mp4
  Duration: 32.0 seconds
```

## Integration with Other Steps

### From Step 7 (Scene Prompts)
- Uses `scene_prompts.json` to determine scene order
- Reads `scene_number` for each scene
- Ensures clips are merged in correct sequence

### From Step 9 (Video Clips)
- Reads individual video clips from `s9_generate_video_clips/outputs/`
- Uses model suffix to identify correct video files
- Handles missing clips gracefully

### Output Location
- Final video saved to `s10_merge_clips/outputs/` (separate from clips)
- Maintains same directory structure: `{batch}/{concept}/`
- Easy to locate final output

## Error Handling

### Common Issues

**1. Missing Video Clips**
```
✗ Scene 3: Video file not found
⚠ Warning: Missing scenes: [3]
```
**Cause:** Video clip not generated in Step 9
**Solution:** 
- Check Step 9 completed successfully
- Verify video files exist in `s9_generate_video_clips/outputs/`
- Re-run Step 9 if needed

**2. FFmpeg Not Found**
```
ERROR: ffmpeg not found. Please install ffmpeg.
```
**Cause:** FFmpeg not installed or not in PATH
**Solution:**
```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt-get install ffmpeg

# Windows
# Download from https://ffmpeg.org/download.html
```

**3. Invalid Video Files**
```
✗ FFmpeg error: Invalid data found when processing input
```
**Cause:** Corrupted video file or incompatible format
**Solution:**
- Verify video files are valid MP4
- Check if files were fully downloaded
- Re-generate problematic clips in Step 9

**4. Path Issues**
```
✗ FFmpeg error: No such file or directory
```
**Cause:** Absolute paths in concat file are incorrect
**Solution:** Script handles this automatically by using absolute paths and escaping special characters

**5. Permission Errors**
```
✗ FFmpeg error: Permission denied
```
**Cause:** Cannot write to output directory
**Solution:**
- Check write permissions on output directory
- Ensure output directory exists
- Verify disk space available

## Best Practices

1. **Verify All Clips Exist** before running merge
2. **Check Video Quality** of individual clips before merging
3. **Use Stream Copy** (default) for fastest processing
4. **Keep Output Separate** from individual clips for organization
5. **Review Scene Order** in scene_prompts.json if needed
6. **Test with Few Clips** first if troubleshooting

## Troubleshooting

### Final Video Missing Scenes
1. Check Step 9 completed for all scenes
2. Verify video files exist in `s9_generate_video_clips/outputs/`
3. Check model suffix matches file names
4. Review merge script output for warnings

### Slow Merging (>10 seconds)
1. Check if re-encoding is happening (should use `-c copy`)
2. Verify FFmpeg version supports stream copy
3. Check disk I/O performance
4. Ensure sufficient disk space

### Video Playback Issues
1. Verify all input clips play correctly individually
2. Check video codec compatibility
3. Try re-encoding with `-c:v libx264` if needed
4. Verify audio codec compatibility

### Wrong Scene Order
1. Check `scene_prompts.json` has correct scene numbers
2. Verify scene numbers match video file names
3. Review merge script output for scene order
4. Check if scenes are sorted correctly

## Files
- **Script**: `s10_merge_clips/scripts/merge_video_clips_ffmpeg.py`
- **Inputs**: 
  - Video clips from `s9_generate_video_clips/outputs/`
  - Scene prompts JSON from Step 7
- **Outputs**: 
  - `outputs/{batch}/{concept}/{concept}_final_{model_suffix}.mp4`

## Dependencies
- **FFmpeg**: Required for video merging
  - Install: `brew install ffmpeg` (macOS) or `sudo apt-get install ffmpeg` (Linux)
  - Verify: `ffmpeg -version`

## Notes
- Merging is very fast (1-5 seconds) due to stream copy
- No quality loss from merging (direct stream copy)
- Missing scenes are skipped with warning
- Final video duration = sum of all individual clip durations
- Output directory is separate from individual clips for better organization
- Script automatically handles path escaping for special characters

