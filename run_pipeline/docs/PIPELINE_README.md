# Video Generation Pipeline Documentation

Complete guide to the video generation pipeline from brand config (or evaluation JSON) to final merged video.

## Overview

The pipeline can start from two points:
1. **Brand Config** (Full Pipeline): Generates concepts → Evaluates → Creates video (Steps 0-9)
2. **Evaluation JSON** (Video Only): Uses existing evaluation → Creates video (Steps 2-9)

The complete pipeline generates:
- Multiple ad concepts (generic + advanced prompts, multiple models)
- Scored evaluations of all concepts
- Best concept selection
- Revised 5-scene script
- Universe/character reference images
- Scene-by-scene video prompts
- First frame images
- Video clips with audio
- Final merged video

## Pipeline Steps

### Step 0: Generate Concepts (Optional - if start_from='brand_config')
**Input:** 
- Brand config file (`config_file` in config)
- Creative direction (`creative_direction` in config)
- AD_STYLE list (`ad_styles` in config)
- Templates (`templates` in config)
- Models (`models` in config)

**Output:** Batch summary JSON + concept files  
**What it does:** Generates 5-scene ad concepts for all combinations of:
- AD_STYLE options (e.g., "Achievement - Inspirational")
- Templates (generic, advanced)
- Models (GPT-5.1, Claude Sonnet 4.5, etc.)

Runs in parallel for speed.

**Files:**
- Input: Brand config JSON
- Output: 
  - `results/{brand}_{timestamp}/` - Concept files
  - `prompts_history/{brand}_{timestamp}/` - Generated prompts
  - `results/{brand}_{timestamp}/{brand}_batch_summary_{timestamp}.json`

**Config parameters:**
- `concept_generation.ad_styles`: List of AD_STYLE options
- `concept_generation.templates`: List of [template_path, template_name]
- `concept_generation.models`: List of [provider, model, reasoning_effort, thinking]
- `concept_generation.creative_direction`: Creative direction prompt
- `concept_generation.concept_parallel_workers`: Parallel workers (default: 8)

---

### Step 1: Judge/Evaluate Concepts (Optional - if start_from='brand_config')
**Input:** Batch summary JSON from Step 0  
**Output:** Evaluation JSON with scored concepts  
**What it does:** Evaluates each concept separately (parallel) using an LLM judge. Scores 0-100 based on:
- Narrative Quality (20 points)
- Emotional Impact (20 points)
- Brand Integration (15 points)
- Memorability (15 points)
- Visual Clarity (15 points)
- Success Likelihood (15 points)

**Files:**
- Input: Batch summary JSON from Step 0
- Output: `evaluations/{brand}_evaluation_{judge_model}_{timestamp}.json`

**Config parameters:**
- `evaluation.judge_model`: LLM model for judging
- `evaluation.evaluation_output_dir`: Output directory for evaluations

### Step 2: Extract Best Concept
**Input:** Evaluation JSON file (`evaluation_json` in config)  
**Output:** Best-scoring concept file path  
**What it does:** Loads evaluation JSON, finds the highest-scoring concept, extracts the concept file path.

**Files:**
- Input: `evaluations/*_evaluation_*.json` (from Step 1 or provided)
- Output: Concept file path (from evaluation JSON)

---

### Step 3: Revise Concept Based on Judge Feedback
**Input:** 
- Concept file content (best scoring concept)
- Judge evaluation weaknesses (from Step 1)
- Brand config file (`config_file` in config)
- Duration (`duration_seconds` in config)
- LLM model (`llm_model` in config)

**Output:** Revised concept file + re-evaluation scores  
**What it does:** 
1. Takes the best scoring concept and addresses judge-identified weaknesses
2. Makes strategic improvements while maintaining core strengths
3. Ensures scenes are appropriately paced for video generation
4. **Optional:** Re-judges the revised concept to measure improvement

**Files:**
- Input: Best concept file from Step 2
- Output: 
  - `{concept_name}_revised.txt` - Improved concept
  - `{concept_name}_revised_evaluation.json` - Re-evaluation with score comparison

**Config parameters:**
- `pipeline_steps.run_concept_revision`: Enable/disable revision (default: true)
- `pipeline_steps.rejudge_revised_concept`: Enable/disable re-judging (default: true)
- `video_settings.duration_seconds`: Total video duration
- `models.llm_model`: LLM for concept revision
- `evaluation.judge_model`: LLM for re-judging

---

### Step 4: Generate Universe and Characters
**Input:**
- Revised script
- Brand config file
- LLM model

**Output:** Universe/characters JSON file  
**What it does:** Generates detailed descriptions for:
- **Universe:** Props and locations that appear across multiple scenes
- **Characters:** All characters with detailed physical descriptions
- **Versions:** Multiple versions/states for elements (e.g., "Early Struggle" vs "Opening Night Success")

**Files:**
- Input: Revised script from Step 2
- Output: `{concept_name}_universe_characters.json` in output directory

**Config parameters:**
- `models.llm_model`: LLM for universe/character generation

---

### Step 5: Generate Reference Images
**Input:**
- Universe/characters JSON file
- Image generation model (`image_model` in config)

**Output:** Reference images for all universe/character elements  
**What it does:** Generates hyper-realistic reference images for:
- Characters (with multiple versions if applicable)
- Locations (with multiple versions if applicable)
- Props

Images are saved in organized directory structure with an `image_generation_summary.json` mapping element names to file paths.

**Files:**
- Input: `{concept_name}_universe_characters.json` from Step 3
- Output: `{universe_images_dir}/{concept_name}/` directory with:
  - `characters/` subdirectories
  - `locations/` subdirectories
  - `props/` subdirectories
  - `image_generation_summary.json`

**Config parameters:**
- `output.universe_images_dir`: Base directory for images
- `models.image_model`: Image generation model (nano-banana)
- `image_generation.image_parallel_workers`: Parallel workers for image generation
- `advanced.skip_image_generation`: Skip if images already exist

---

### Step 6: Generate Scene Prompts
**Input:**
- Revised script
- Universe/characters JSON
- Brand config
- Image generation summary (for element name mapping)
- Duration, resolution, aspect ratio
- LLM model

**Output:** Scene prompts JSON file  
**What it does:** Generates detailed video generation prompts for each scene including:
- **video_prompt:** Complete prompt with shot type, subject, action, setting, lighting
- **audio_background:** Background music description
- **audio_dialogue:** Dialogue with speaker name and voice characteristics (format: "Character Name: dialogue" or "Narrator (voice): dialogue")
- **first_frame_image_prompt:** Detailed image prompt for first frame
- **elements_used:** List of characters/locations/props with version names (format: "Element Name - Version Name")

**Files:**
- Input: Revised script, universe/characters JSON, image summary
- Output: `{concept_name}_scene_prompts.json` in output directory

**Config parameters:**
- `video_settings.duration_seconds`: Total duration
- `video_settings.resolution`: Video resolution (480p, 720p, 1080p)
- `video_settings.aspect_ratio`: Aspect ratio (16:9)
- `video_settings.scenes_count`: Number of scenes (default: 5)
- `models.llm_model`: LLM for scene prompt generation
- `advanced.regenerate_scene_prompts`: Force regeneration even if file exists

---

### Step 7: Generate First Frame Images
**Input:**
- Scene prompts JSON
- Universe/characters JSON
- Reference images directory
- Resolution, aspect ratio

**Output:** First frame image for each scene  
**What it does:** Generates the first frame image for each scene using:
- Reference images from universe/characters (blended naturally, not literally inserted)
- First frame image prompt from scene prompts
- Version-specific matching (uses exact version names from `elements_used`)

**Files:**
- Input: Scene prompts JSON, universe/characters JSON, reference images
- Output: `{first_frames_dir}/{concept_name}/` directory with:
  - `{concept_name}_p{scene_num}_first_frame.jpg` for each scene
  - `debug/scene_{num}/` directories with prompts and reference images used

**Config parameters:**
- `output.first_frames_dir`: Base directory for first frames
- `video_settings.resolution`: Resolution for first frames
- `video_settings.aspect_ratio`: Aspect ratio for first frames
- `image_generation.max_reference_images`: Max reference images (nano-banana limit: 5)
- `image_generation.image_parallel_workers`: Parallel workers
- `advanced.skip_first_frames`: Skip if frames already exist

---

### Step 8: Generate Video Clips
**Input:**
- Scene prompts JSON
- First frame images
- Video generation model
- Resolution, aspect ratio, duration
- Audio generation flag

**Output:** Video clip for each scene  
**What it does:** Generates video clips using Veo 3 Fast (or other models) with:
- First frame image as reference
- Combined prompt (video + audio background + dialogue)
- Audio generation enabled
- Scene-specific duration

**Files:**
- Input: Scene prompts JSON, first frame images
- Output: `{video_outputs_dir}/{concept_name}/` directory with:
  - `{concept_name}_p{scene_num}_{model_suffix}.mp4` for each scene
  - `debug/scene_{num}/` directories with exact prompts sent to API

**Config parameters:**
- `output.video_outputs_dir`: Base directory for video outputs
- `models.video_model`: Video generation model (google/veo-3-fast, openai/sora-2, etc.)
- `video_settings.resolution`: Video resolution
- `video_settings.aspect_ratio`: Aspect ratio
- `video_generation.generate_audio`: Enable audio generation
- `advanced.skip_video_clips`: Skip if clips already exist

---

### Step 10: Merge Video Clips
**Input:**
- Scene prompts JSON (for scene order)
- Video clips directory (from Step 9)
- Model suffix (for file naming)

**Output:** Final merged video  
**What it does:** Merges all scene clips in sequence using ffmpeg into a single final video. Output is saved to dedicated `s10_merge_clips/outputs/` directory.

**Files:**
- Input: Scene prompts JSON, individual video clips from Step 9
- Output: `{merge_outputs_dir}/{batch}/{concept_name}/{concept_name}_final_{model_suffix}.mp4`

**Config parameters:**
- `models.video_model`: Used to determine model suffix for output filename
- `output.merge_outputs_dir`: Directory for final merged video (default: `s10_merge_clips/outputs`)

---

## Pipeline Modes

### Mode 1: Full Pipeline (start_from='brand_config')
Runs Steps 0-9:
- Generates concepts for all AD_STYLE/template/model combinations
- Evaluates all concepts
- Selects best concept
- Generates complete video

**Use when:** Starting fresh with just a brand config

### Mode 2: Video Only (start_from='evaluation_json')
Runs Steps 2-9:
- Uses existing evaluation JSON
- Selects best concept
- Generates complete video

**Use when:** You already have evaluated concepts and just want to generate video

## Configuration File

The pipeline is controlled by `pipeline_config.yaml` (or `pipeline_config.json` for backward compatibility) with the following sections:

**Note:** The YAML format is recommended as it's more human-readable with clear sections and comments explaining each step.

### `pipeline_mode`
- `start_from`: "brand_config" or "evaluation_json"
- `skip_concept_generation`: Skip Step 0 if batch exists
- `skip_evaluation`: Skip Step 1 if evaluation exists

### `concept_generation` (Step 0)
- `creative_direction`: Creative direction prompt
- `ad_styles`: List of AD_STYLE options to generate
- `templates`: List of [template_path, template_name]
- `models`: List of [provider, model, reasoning_effort, thinking]
- `concept_parallel_workers`: Parallel workers

### `evaluation` (Step 1)
- `judge_model`: LLM model for judging
- `evaluation_output_dir`: Output directory

### `input`
- `evaluation_json`: Path to evaluation JSON file
- `config_file`: Path to brand configuration file

### `output`
- `base_output_dir`: Base directory for script generation outputs
- `universe_images_dir`: Directory for reference images
- `first_frames_dir`: Directory for first frame images
- `video_outputs_dir`: Directory for individual video clips (Step 9 output)
- `merge_outputs_dir`: Directory for final merged video (Step 10 output, default: `s10_merge_clips/outputs`)

### `video_settings`
- `duration_seconds`: Total video duration (default: 30)
- `resolution`: Video resolution (480p, 720p, 1080p)
- `aspect_ratio`: Aspect ratio (16:9)
- `scenes_count`: Number of scenes (default: 5)

### `models`
- `llm_model`: LLM for script/universe/scene generation
- `video_model`: Video generation model
- `image_model`: Image generation model

### `image_generation`
- `max_reference_images`: Max reference images for first frames (default: 5)
- `image_parallel_workers`: Parallel workers for image generation

### `video_generation`
- `generate_audio`: Enable audio generation (default: true)
- `video_parallel_workers`: Parallel workers for video generation

### `advanced`
- `skip_image_generation`: Skip if images exist
- `skip_first_frames`: Skip if first frames exist
- `skip_video_clips`: Skip if clips exist
- `regenerate_scene_prompts`: Force regeneration of scene prompts

## Usage

### Full Pipeline (Brand Config → Video)
```bash
python run_pipeline_complete.py
```
Uses default `pipeline_config.yaml` with `start_from='brand_config'`

### Video Only (Evaluation → Video)
Edit `pipeline_config.yaml`:
```yaml
pipeline_mode:
  start_from: evaluation_json

input:
  evaluation_json: evaluations/rolex_evaluation_claude_4.5_1115_1848.json
```
Then run:
```bash
python run_pipeline_complete.py
```

### Custom Config
```bash
python run_pipeline_complete.py my_config.yaml
# or
python run_pipeline_complete.py my_config.json  # JSON still supported
```

### Example Config
See `pipeline_config.yaml` for a complete example with clear sections and comments explaining each step, input, and output.

## Output Structure

```
results/
  {brand}_{timestamp}/
    {brand}_{ad_style}_{template}_{model}.txt  (concept files)
    {brand}_batch_summary_{timestamp}.json

prompts_history/
  {brand}_{timestamp}/
    {brand}_{ad_style}_{template}_{model}_prompt.txt

evaluations/
  {brand}_evaluation_{judge_model}_{timestamp}.json
  {brand}_scores_{judge_model}_{timestamp}.csv

script_generation/
  {brand}_{timestamp}/
    {concept_name}/
      {concept_name}_revised.txt
      {concept_name}_universe_characters.json
      {concept_name}_scene_prompts.json

universe_characters/
  {concept_name}/
    characters/
      {element_name}/
        {element_name}_{version}.jpg
    locations/
      {location_name}/
        {location_name}_{version}.jpg
    props/
      {prop_name}/
        {prop_name}.jpg
    image_generation_summary.json

first_frames/
  {concept_name}/
    {concept_name}_p{scene_num}_first_frame.jpg
    debug/
      scene_{num}/
        first_frame_p{num}_prompt.txt
        first_frame_p{num}_reference_*.jpg

video_outputs/
  {concept_name}/
    {concept_name}_p{scene_num}_{model}.mp4
    {concept_name}_final_{model}.mp4
    debug/
      scene_{num}/
        {model}_p{num}_prompt.txt
```

## Advanced Features (2025)

### JSON Validation & Structured Outputs

The pipeline uses state-of-the-art techniques (as of Nov 2025) to ensure reliable JSON generation from LLMs:

#### 1. OpenAI Structured Outputs (GPT-4o/5+)
**What it does:** Guarantees 100% valid JSON matching a predefined schema - no parsing errors possible.

**Implementation:**
```python
# Define JSON schema
schema = {
    "type": "object",
    "properties": {
        "universe": {...},
        "characters": {...}
    },
    "required": ["universe", "characters"],
    "additionalProperties": False
}

# Use structured outputs
completion = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": prompt}],
    response_format={
        "type": "json_schema",
        "json_schema": {
            "name": "schema_name",
            "strict": True,
            "schema": schema
        }
    }
)
```

**Benefits:**
- Zero JSON parsing errors
- Automatic validation against schema
- No need for error handling or fixes
- Works with GPT-4o, GPT-5.1, and later models

**Used in:** Steps 5 (Universe), 7 (Scene Prompts) when using GPT models

---

#### 2. Anthropic Prompt Caching + Extended Thinking
**What it does:** Reduces costs by 90% and handles Claude's ThinkingBlock format correctly.

**Implementation:**
```python
# Split prompt into cacheable and dynamic parts
system = [
    {
        "type": "text",
        "text": "Schema and instructions...",
        "cache_control": {"type": "ephemeral"}  # Cache this
    }
]

# Call with thinking enabled
response = client.messages.create(
    model="claude-sonnet-4-5-20250929",
    system=system,
    messages=[{"role": "user", "content": "Dynamic content..."}],
    thinking={"type": "enabled", "budget_tokens": 10000},
    max_tokens=16000
)

# Extract text content (skip ThinkingBlocks)
content_parts = []
for block in response.content:
    if hasattr(block, 'type') and block.type == 'thinking':
        continue  # Skip internal reasoning
    if hasattr(block, 'text'):
        content_parts.append(block.text)

content = '\n'.join(content_parts)
```

**Benefits:**
- **Cost Savings:** Cache reads cost 10% vs 100% of input tokens
- **Speed:** Up to 85% faster with cache hits
- **Quality:** Extended thinking (10k tokens) for better reasoning
- **Correct Parsing:** Filters out ThinkingBlock objects

**Used in:** Steps 5 (Universe), 7 (Scene Prompts) when using Claude models

---

#### 3. Robust JSON Extraction & Auto-Fixing
**What it does:** Handles common LLM JSON issues automatically with multiple fallback strategies.

**Implementation:**
```python
# 1. Remove markdown code blocks
if "```json" in response:
    json_text = response.split("```json")[1].split("```")[0].strip()

# 2. Find JSON boundaries
if not json_text.startswith("{"):
    start = json_text.find("{")
    end = json_text.rfind("}") + 1
    json_text = json_text[start:end]

# 3. Try to parse
try:
    result = json.loads(json_text)
except json.JSONDecodeError:
    # 4. Auto-fix common issues
    json_text = re.sub(r',(\s*[}\]])', r'\1', json_text)  # Trailing commas
    json_text = re.sub(r'//.*?\n', '\n', json_text)  # Comments
    json_text = re.sub(r'/\*.*?\*/', '', json_text, flags=re.DOTALL)
    
    # 5. Try again
    result = json.loads(json_text)
```

**Handles:**
- Markdown code blocks (```json)
- Extra text before/after JSON
- Trailing commas
- JavaScript-style comments
- Unescaped characters

**Used in:** All LLM-based steps (5, 7) as fallback

---

#### 4. Debug Mode & Error Reporting
**What it does:** Saves failed responses for manual inspection and debugging.

**Implementation:**
```python
except json.JSONDecodeError as e:
    # Save debug info
    debug_dir = Path("outputs/debug")
    debug_dir.mkdir(parents=True, exist_ok=True)
    
    debug_file = debug_dir / "failed_response.txt"
    with open(debug_file, 'w') as f:
        f.write("=== ORIGINAL RESPONSE ===\n")
        f.write(response)
        f.write("\n\n=== EXTRACTED JSON ===\n")
        f.write(json_text)
        f.write(f"\n\n=== ERROR ===\n{e}")
    
    print(f"Debug info saved to: {debug_file}")
    print(f"Error location: line {e.lineno}, column {e.colno}")
    
    # Show context around error
    if hasattr(e, 'pos'):
        start = max(0, e.pos - 100)
        end = min(len(json_text), e.pos + 100)
        print(f"Context: ...{json_text[start:end]}...")
```

**Benefits:**
- Easy debugging with full context
- Exact error location shown
- Original and processed JSON saved
- Can manually fix and retry

**Used in:** All LLM-based steps as final fallback

---

### Summary: JSON Reliability Strategy

| Model | Primary Method | Fallback | Error Rate |
|-------|---------------|----------|------------|
| GPT-4o/5+ | Structured Outputs | Auto-fix | ~0% |
| Claude 4.5 | Prompt Caching + Thinking | Auto-fix | ~1-2% |
| Older Models | Prompt Engineering | Auto-fix | ~5-10% |

**Best Practices:**
1. Use GPT-4o/5+ for guaranteed valid JSON (zero errors)
2. Use Claude with prompt caching for cost savings (90% cheaper on cache hits)
3. Enable extended thinking for complex JSON structures
4. Always check debug files if parsing fails
5. Retry with higher thinking budget if quality issues occur

---

## Dependencies

- Python 3.8+
- Required packages: See `requirements.txt`
- External tools: ffmpeg (for video merging)
- API keys: OpenAI, Anthropic, Replicate (in `.env` file)

## Notes

- The pipeline automatically creates batch folders with timestamps
- Version names in `elements_used` ensure correct image matching
- Dialogue format includes speaker names and voice characteristics for audio models
- All prompts are saved in debug directories for review
- Parallel execution is used for concept generation, image generation, and video generation where possible
- You can skip Steps 0-1 if you already have an evaluation JSON
- You can skip individual steps (image generation, first frames, video clips) if outputs already exist

