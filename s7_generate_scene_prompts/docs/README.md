# Step 7: Generate Scene Prompts

## Overview
Generates detailed video and audio prompts for each scene in the ad concept. Creates comprehensive prompts for video generation models (Veo 3 Fast, Sora 2) including camera angles, lighting, actions, dialogue, and first frame image specifications.

## Purpose
- **Video Generation Ready**: Creates prompts optimized for AI video models
- **Audio Integration**: Includes background music and dialogue specifications
- **First Frame Matching**: Generates image prompts that match video style exactly
- **Element Tracking**: Maps characters/props/locations to reference images
- **Self-Contained Scenes**: Each scene prompt is complete and independent

## What It Does

### Input
- **Revised script** (from Step 4)
- **Universe/characters JSON** (from Step 5)
- **Brand config file** (brand context)
- **Image generation summary** (from Step 6 - for element name mapping)
- **Video settings** (duration, resolution, aspect ratio)
- **LLM model** (for generation)

### Output
- **`{concept_name}_scene_prompts.json`**: Structured JSON containing:
  - Scene-by-scene video prompts
  - Audio background descriptions
  - Dialogue with speaker names
  - First frame image prompts
  - Elements used (characters/props/locations)

### Key Features
1. **Flexible Duration Calculation**: Supports multiple input modes
2. **Model-Specific Validation**: Rounds durations to valid values (Veo: 4/6/8s, Sora: 4/8/12s)
3. **Self-Contained Prompts**: Each scene includes complete style/aesthetic info
4. **First Frame Continuity**: Image prompts match video style exactly
5. **Element Name Mapping**: Uses exact names from reference images

## JSON Structure

```json
{
  "scenes": [
    {
      "scene_number": 1,
      "duration_seconds": 8,
      "video_prompt": "Style: Modern documentary style...\n\nScene Description: Young watchmaker...\n\nCinematography:\nCamera shot: Wide shot, eye level\nCamera motion: Slow push-in\nLighting: Soft window light...\nMood: Contemplative and determined\n\nActions:\n- Takes four steps forward\n- Pauses at window\n- Turns head to camera",
      "audio_background": "Ambient piano with subtle string accompaniment, contemplative mood, 60 BPM, minimalist composition",
      "audio_dialogue": "Narrator (warm, reflective voice): Every master begins with a single attempt.",
      "first_frame_image_prompt": "Hyper-realistic photorealistic professional portrait photography. Modern documentary style, shot on digital cinema camera with natural grain, warm cinematic color grade. Wide shot at eye level showing young watchmaker at wooden workbench...",
      "elements_used": {
        "characters": ["Young Watchmaker (Protagonist) - Struggling Apprentice"],
        "locations": ["Watchmaker's Workshop"],
        "props": []
      }
    }
  ]
}
```

## Usage

### Standalone
```bash
python s7_generate_scene_prompts/scripts/generate_scene_prompts.py \
  <revised_concept_file> \
  --duration 32 \
  --model "anthropic/claude-sonnet-4-5-20250929" \
  --resolution "720p"
```

**Example:**
```bash
python s7_generate_scene_prompts/scripts/generate_scene_prompts.py \
  "s4_revise_concept/outputs/olin_1120_0012/olin_achievement_inspirational_advanced_claude_sonnet_4.5/olin_achievement_inspirational_advanced_claude_sonnet_4.5_revised.txt" \
  --duration 32 \
  --model "anthropic/claude-sonnet-4-5-20250929" \
  --resolution "720p"
```

**Note:** The script auto-detects paths based on the input file structure:
- Batch folder: Extracted from parent directory
- Concept name: Extracted from filename
- Brand name: First part of concept name
- Universe JSON: Auto-located in `s5_generate_universe/outputs/`
- Config file: Auto-located in `s1_generate_concepts/inputs/configs/`
- Image summary: Auto-located in `s6_generate_reference_images/outputs/`

### Via Pipeline
Set in `pipeline_config.yaml`:
```yaml
pipeline_steps:
  run_step_7: true

video_settings:
  clip_duration: 8  # Duration per clip
  num_clips: 4      # Number of clips
  resolution: 720p
  aspect_ratio: "16:9"

models:
  llm_model: anthropic/claude-sonnet-4-5-20250929
  llm_thinking: 0  # 0=fast, 10000=max thinking
  scene_prompts_temperature: 0.5
  video_model: openai/sora-2  # Determines valid durations
```

## Configuration

### Duration Calculation (Flexible)
The system supports multiple input modes:

**Mode 1: clip_duration + num_clips**
```yaml
clip_duration: 8
num_clips: 4
# Result: 4 clips × 8s = 32s total
```

**Mode 2: total_duration + num_clips**
```yaml
total_duration: 32
num_clips: 4
# Result: 4 clips × 8s (calculated)
```

**Mode 3: total_duration + clip_duration**
```yaml
total_duration: 32
clip_duration: 8
# Result: 4 clips (calculated)
```

**Mode 4: Legacy (total_duration only)**
```yaml
total_duration: 30
scenes_count: 5
# Result: 5 clips × 6s (calculated)
```

### Valid Durations (Model-Specific)
**Sora-2:** 4, 8, or 12 seconds
**Veo 3 Fast:** 4, 6, or 8 seconds

The system automatically rounds to the nearest valid duration:
```
Input: 6.4s → Rounded to: 6s (Veo 3 Fast)
Input: 10s → Rounded to: 8s (Veo 3 Fast)
```

### LLM Settings
```yaml
models:
  llm_model: anthropic/claude-sonnet-4-5-20250929
  llm_thinking: 0  # 0=disabled (fast), 10000=max (slow but better)
  scene_prompts_temperature: 0.5  # 0.0-1.0 (lower=faster)
```

**Thinking Budget:**
- `0`: Disabled - Fast mode (10-30 seconds)
- `500-1000`: Light thinking (30-60 seconds)
- `10000`: Max thinking (7-12 minutes) - Best quality

**Temperature:**
- `0.3-0.5`: Faster, more deterministic
- `0.7-1.0`: Slower, more creative variation

### Output Directory
```yaml
output:
  # Step 7 outputs go to separate directory
  # (Not in base_output_dir - has its own structure)
```

**Output Path:**
```
s7_generate_scene_prompts/outputs/{batch_folder}/{concept_name}/
  └── {concept_name}_scene_prompts.json
```

## Prompt Structure

### Video Prompt Format
Each video prompt follows this structure:

```
Style: [Overall aesthetic, film format, color grade - INCLUDED IN EVERY SCENE]

Scene Description: [WHO is in frame, WHERE they are, WHAT they're doing]

Cinematography:
Camera shot: [Specific framing - wide/medium/close-up, angle]
Camera motion: [Slow push-in/static/dolly/handheld]
Lighting: [Quality and source - soft window light, golden hour, etc.]
Mood: [Emotional tone - contemplative, triumphant, tense]

Actions:
- [First specific beat with timing]
- [Second specific beat with timing]
- [Third specific beat with timing]
```

### Montage Scenes (Multiple Shots)
For scenes with multiple shots, each is clearly separated:

```
Style: [Overall aesthetic]

SHOT 1 (0-2 seconds - Shot Name):
Scene: [WHO, WHERE, WHAT]
Cinematography: [Framing]
Lighting: [Lighting]
Action: [What happens]

SHOT 2 (2-4 seconds - Shot Name):
Scene: [WHO, WHERE, WHAT]
Cinematography: [Framing]
Lighting: [Lighting]
Action: [What happens]
```

### First Frame Image Prompt
**CRITICAL:** Must match video_prompt style EXACTLY for visual continuity.

**Requirements:**
1. Copy ENTIRE "Style:" line from video_prompt verbatim
2. Copy EXACT "Camera shot:" description
3. Copy EXACT "Lighting:" description
4. Copy EXACT "Mood:" description
5. Include EXACT camera type/film style
6. Include EXACT color grade
7. Include all characters/locations from elements_used
8. Add hyper-realistic, photorealistic keywords

**Why:** The first frame image is generated FIRST (nano-banana), then used as the first frame reference for video generation. If styles don't match, the video looks inconsistent.

### Audio Dialogue Format
```
"Speaker Name: [dialogue text]"
```

**Examples:**
- `"Young Watchmaker: I'll master this craft, no matter how long it takes."`
- `"Narrator (warm, nostalgic voice): Every master begins with a single attempt."`
- `"Mentor (gruff but kind voice): You've earned this crown."`
- `null` (for scenes with no dialogue)

### Elements Used Format
```json
{
  "characters": ["Name - Version Name"],
  "locations": ["Name - Version Name"],
  "props": ["Name"]
}
```

**Example:**
```json
{
  "characters": ["Young Watchmaker (Protagonist) - Struggling Apprentice"],
  "locations": ["Watchmaker's Workshop"],
  "props": ["Gold Olin Watch - Benchmark Watch"]
}
```

## Advanced Features (2025)

### 1. Anthropic Prompt Caching
- **Caches** schema and instructions (6000+ tokens)
- **Cost Savings:** 90% reduction on cache hits
- **Speed:** Up to 85% faster with cache
- **Automatic:** Enabled for Claude models

### 2. OpenAI Structured Outputs (GPT-4o/5+)
- **Guarantees** valid JSON matching schema
- **Zero Errors:** No parsing failures
- **Automatic:** Enabled for GPT-4o and later

### 3. ThinkingBlock Handling (Claude)
- **Filters** internal reasoning blocks
- **Extracts** only text content
- **Handles** extended thinking mode

### 4. Robust JSON Parsing
- **Auto-fixes:** Trailing commas, comments, extra text
- **Fallbacks:** Multiple parsing strategies
- **Debug:** Saves failed responses to `outputs/debug/`

See [PIPELINE_README.md](../../run_pipeline/docs/PIPELINE_README.md#advanced-features-2025) for detailed implementation.

## Performance

**Typical Execution:**
- **Time (Fast Mode):** 10-30 seconds (thinking=0)
- **Time (Thinking Mode):** 1-5 minutes (thinking=10000)
- **Cost:** ~$0.05-0.15 per run (with caching: ~$0.005-0.015 on cache hits)
- **Output:** 20-30KB JSON file
- **Scenes:** 4-5 scenes with complete prompts

### Example Run (Fast Mode)
```
Cache created: 6632 tokens
LLM API call: 107.9 seconds (1.8 minutes)
Scenes generated: 5
Total duration: 30 seconds (5 × 6s clips)
```

## Prompt Engineering Best Practices

### 1. Self-Contained Scenes
Each scene must include ALL necessary information:
- ✅ Include style/aesthetic in EVERY scene
- ✅ Clearly state WHO, WHERE, WHAT
- ✅ Specify lighting quality and source
- ❌ Don't assume context from previous scenes

### 2. Specific, Not Vague
- ✅ "Wet asphalt, neon reflections, steam rising from grates"
- ❌ "Beautiful street scene"

### 3. Clear Motion
- ✅ "Slow push-in over 4 seconds, ending on close-up"
- ❌ "Camera moves in"

### 4. Montage Clarity
- ✅ Clearly separate each shot with timing
- ✅ Distinguish shots so they don't blend
- ❌ Vague transitions between moments

## Error Handling

### Common Issues

**1. JSON Parsing Errors**
- **Cause:** Malformed JSON from LLM
- **Solution:** Automatic fixes applied (trailing commas, comments)
- **Debug:** Check `s7_generate_scene_prompts/outputs/debug/failed_response.txt`

**2. Duration Mismatch**
- **Cause:** Requested duration doesn't match valid values
- **Solution:** Automatic rounding to nearest valid duration
- **Warning:** Shows adjustment message

**3. Missing Config File**
- **Cause:** Brand config not found (e.g., `olin.json` vs `luxury_watch.json`)
- **Solution:** Create symlink or copy config with correct name
- **Example:** `cp luxury_watch.json olin.json`

**4. Element Name Mismatches**
- **Cause:** LLM uses different names than reference images
- **Solution:** Image summary provides name mappings
- **Prevention:** Prompt includes EXACT allowed names

## Integration with Other Steps

### From Step 4 (Revised Script)
- Uses revised concept as base narrative
- Extracts scene structure and content

### From Step 5 (Universe)
- Uses character/prop/location descriptions
- Includes version information for transformations

### From Step 6 (Reference Images)
- Maps element names to actual image files
- Ensures prompts use exact names from images

### To Step 8 (First Frames)
- First frame image prompts used to generate images
- Elements_used maps to reference images
- Version names ensure correct image selection

### To Step 9 (Video Clips)
- Video prompts used for video generation
- Audio prompts used for audio generation
- Duration settings control clip length

## Best Practices

1. **Use Fast Mode (thinking=0)** for speed unless quality issues occur
2. **Enable Caching** for cost savings on repeated runs
3. **Check Duration Settings** match your video model (Veo vs Sora)
4. **Review First Frame Prompts** ensure they match video style
5. **Verify Element Names** match reference images exactly
6. **Use Temperature 0.5** for balanced speed and quality

## Troubleshooting

### Slow Generation (>5 minutes)
1. Disable thinking: `llm_thinking: 0`
2. Lower temperature: `scene_prompts_temperature: 0.3`
3. Use GPT-4o instead of Claude (faster for JSON)

### Quality Issues
1. Enable thinking: `llm_thinking: 10000`
2. Increase temperature: `scene_prompts_temperature: 0.7`
3. Check prompt includes all necessary context

### JSON Parsing Failures
1. Check debug files in `outputs/debug/`
2. Verify LLM model supports JSON output
3. Try GPT-4o with structured outputs (zero errors)
4. Increase max_tokens if response truncated

## Files
- **Script**: `s7_generate_scene_prompts/scripts/generate_scene_prompts.py`
- **Inputs**: 
  - Revised script (from Step 4)
  - Universe/characters JSON (from Step 5)
  - Brand config file
  - Image generation summary (from Step 6)
- **Outputs**: 
  - `outputs/{batch}/{concept}/{concept}_scene_prompts.json`
  - `outputs/debug/failed_response.txt` (if errors occur)

## Next Step
→ **Step 8**: Generate First Frame Images (uses scene prompts + reference images)

## Environment Variables
```bash
# Required
OPENAI_API_KEY=sk-...  # If using GPT models
ANTHROPIC_API_KEY=sk-...  # If using Claude models

# Optional (for .env file)
# None - all config in pipeline_config.yaml
```

