#!/usr/bin/env python3
"""
Scene Prompts Generator
Generates detailed video/audio prompts for each scene.
"""

import os
import sys
import json
import time
import re
from pathlib import Path

# Add path for imports
BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR / "s1_generate_concepts" / "scripts"))

# Load environment variables
try:
    from dotenv import load_dotenv
    env_path = BASE_DIR / ".env"
    load_dotenv(env_path)
except ImportError:
    pass

from execute_llm import call_openai, call_anthropic


def call_anthropic_with_caching(prompt, model, api_key, thinking=None, max_tokens=None, temperature=None):
    """
    Call Anthropic API with prompt caching for repeated schema/instructions.
    Caches the schema and instructions to reduce costs and latency on repeated calls.
    """
    try:
        from anthropic import Anthropic
    except ImportError:
        raise ImportError("Anthropic package not installed. Run: pip install anthropic")
    
    client = Anthropic(api_key=api_key)
    
    # Split prompt into cacheable (schema/instructions) and dynamic (content) parts
    # Cache everything up to the OUTPUT FORMAT section
    if "**OUTPUT FORMAT (JSON):**" in prompt:
        parts = prompt.split("**OUTPUT FORMAT (JSON):**")
        cacheable_part = parts[0] + "**OUTPUT FORMAT (JSON):**"
        dynamic_part = parts[1] if len(parts) > 1 else ""
    else:
        # Fallback: cache most of the prompt
        cacheable_part = prompt[:int(len(prompt) * 0.7)]
        dynamic_part = prompt[int(len(prompt) * 0.7):]
    
    # Build system messages with cache control
    system = [
        {
            "type": "text",
            "text": cacheable_part.strip(),
            "cache_control": {"type": "ephemeral"}  # Cache this part
        }
    ]
    
    # Build request parameters
    params = {
        "model": model,
        "system": system,
        "messages": [
            {"role": "user", "content": dynamic_part.strip() if dynamic_part else "Generate the scene prompts now."}
        ]
    }
    
    # Add thinking parameter
    if thinking is not None and thinking > 0:
        if isinstance(thinking, dict):
            params["thinking"] = thinking
            budget_tokens = thinking.get("budget_tokens", 10000)
        elif isinstance(thinking, int):
            budget_tokens = thinking
            params["thinking"] = {"type": "enabled", "budget_tokens": budget_tokens}
        
        if max_tokens is None:
            params["max_tokens"] = budget_tokens + 10000  # Large buffer for scene prompts
        else:
            params["max_tokens"] = max_tokens
        
        params["temperature"] = temperature if temperature is not None else 1
    else:
        params["max_tokens"] = max_tokens if max_tokens else 10000
        params["temperature"] = temperature if temperature is not None else 0.5
    
    response = client.messages.create(**params)
    
    # Extract content from response (handle ThinkingBlocks)
    if not response.content or len(response.content) == 0:
        raise ValueError("Empty response from Anthropic API")
    
    content_parts = []
    for block in response.content:
        # Skip thinking blocks - we only want the actual text response
        if hasattr(block, 'type') and block.type == 'thinking':
            continue
        
        if hasattr(block, 'text'):
            content_parts.append(block.text)
        elif hasattr(block, 'content'):
            content_parts.append(block.content)
        else:
            content_parts.append(str(block))
    
    if not content_parts:
        raise ValueError("No text content found in Anthropic API response (only thinking blocks)")
    
    content = '\n'.join(content_parts)
    
    # Print cache usage stats
    usage = getattr(response, 'usage', None)
    if usage:
        cache_read = getattr(usage, 'cache_read_input_tokens', 0)
        cache_create = getattr(usage, 'cache_creation_input_tokens', 0)
        if cache_read > 0:
            print(f"  → Cache hit: {cache_read} tokens read from cache (saved cost!)")
        if cache_create > 0:
            print(f"  → Cache created: {cache_create} tokens cached for future use")
    
    return content


def get_api_key(provider):
    """Get API key from environment."""
    if provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
    elif provider == "anthropic":
        api_key = os.getenv("ANTHROPIC_API_KEY")
    else:
        raise ValueError(f"Unknown provider: {provider}")
    
    if not api_key:
        raise ValueError(f"{provider.upper()}_API_KEY not found in environment")
    
    return api_key

def repair_json(json_text):
    """Attempt to repair common JSON issues."""
    # Fix unescaped newlines in strings (replace \n with \\n inside string values)
    # This is a simple approach - find string values and escape newlines
    lines = json_text.split('\n')
    repaired_lines = []
    in_string = False
    escape_next = False
    
    for i, line in enumerate(lines):
        if escape_next:
            escape_next = False
            repaired_lines.append(line)
            continue
            
        # Simple state tracking for strings
        # Count unescaped quotes to determine if we're in a string
        quote_count = 0
        for char in line:
            if char == '"' and (not repaired_lines or repaired_lines[-1][-1] != '\\'):
                quote_count += 1
        
        # If odd number of quotes, we're entering/exiting a string
        if quote_count % 2 == 1:
            in_string = not in_string
        
        repaired_lines.append(line)
    
    repaired = '\n'.join(repaired_lines)
    
    # Try to fix truncated strings by finding the last incomplete string and closing it
    # Look for patterns like: "text... (end of file or next key)
    if not repaired.strip().endswith('}') and not repaired.strip().endswith(']'):
        # Try to close the last incomplete string
        # Find the last unclosed quote
        last_quote_pos = repaired.rfind('"')
        if last_quote_pos > 0:
            # Check if there's a closing quote after it
            after_quote = repaired[last_quote_pos+1:].strip()
            if after_quote and not after_quote.startswith(',') and not after_quote.startswith('}') and not after_quote.startswith(']'):
                # Likely truncated - try to close it
                # Find where the string should end (before next key or closing brace)
                next_key = re.search(r'\s*"[^"]*":', after_quote)
                if next_key:
                    # Insert closing quote before next key
                    insert_pos = last_quote_pos + 1 + next_key.start()
                    repaired = repaired[:insert_pos] + '"' + repaired[insert_pos:]
                else:
                    # Just close it at the end
                    repaired = repaired.rstrip() + '"\n'
    
    return repaired

def load_visual_effects_library():
    """Load visual effects from markdown file."""
    effects_path = BASE_DIR / "s7_generate_scene_prompts" / "inputs" / "visual_effects.md"
    if effects_path.exists():
        with open(effects_path, 'r', encoding='utf-8') as f:
            return f.read()
    return None


def generate_scene_prompts(revised_script, universe_chars, config, duration=30, model="anthropic/claude-sonnet-4-5-20250929", resolution="480p", image_summary_path=None, thinking=None, temperature=None, clip_duration=None, num_clips=None, video_model="google/veo-3-fast", enable_visual_effects=True):
    """Generate detailed video generation prompts for each scene.
    
    Args:
        revised_script: The revised script text
        universe_chars: Universe/characters JSON
        config: Brand config
        duration: Total duration (legacy, used if clip_duration/num_clips not provided)
        model: LLM model
        resolution: Video resolution
        image_summary_path: Path to image generation summary
        thinking: Thinking budget for Claude
        temperature: Temperature for LLM
        clip_duration: Duration per clip in seconds (optional)
        num_clips: Number of clips to generate (optional)
        video_model: Video model to determine valid durations
        enable_visual_effects: Whether to include visual effects in prompts (default: True)
    """
    
    step_start_time = time.time()
    print("  [Step 1/6] Calculating scene duration and count...")
    
    # Determine valid durations based on video model
    is_sora2 = video_model == "openai/sora-2"
    if is_sora2:
        valid_durations = [4, 8, 12]
        model_name = "Sora-2"
    else:
        valid_durations = [4, 6, 8]
        model_name = "Veo 3 Fast"
    
    # Calculate clip_duration and num_clips based on provided inputs
    if clip_duration is not None and num_clips is not None:
        # Both provided: use directly, calculate total
        scene_duration_raw = clip_duration
        num_scenes = num_clips
        total_duration = clip_duration * num_clips
        print(f"  → Using provided: clip_duration={clip_duration}s, num_clips={num_clips}")
    elif clip_duration is not None:
        # Only clip_duration: calculate num_clips from total_duration
        if duration:
            num_scenes = max(1, int(round(duration / clip_duration)))
            total_duration = duration
        else:
            raise ValueError("Must provide either num_clips or total_duration when clip_duration is specified")
        scene_duration_raw = clip_duration
        print(f"  → Using provided clip_duration={clip_duration}s, calculated num_clips={num_scenes} from total_duration={duration}s")
    elif num_clips is not None:
        # Only num_clips: calculate clip_duration from total_duration
        if duration:
            scene_duration_raw = duration / num_clips
            total_duration = duration
        else:
            raise ValueError("Must provide either clip_duration or total_duration when num_clips is specified")
        num_scenes = num_clips
        print(f"  → Using provided num_clips={num_clips}, calculating clip_duration from total_duration={duration}s")
    else:
        # Neither provided: use legacy behavior (duration / scenes_count)
        scenes_count = config.get("scenes_count", 5) if isinstance(config, dict) else 5
        scene_duration_raw = duration / scenes_count
        num_scenes = scenes_count
        total_duration = duration
        print(f"  → Using legacy mode: total_duration={duration}s, scenes_count={scenes_count}")
    
    # Round clip_duration to nearest valid value
    scene_duration = min(valid_durations, key=lambda x: abs(x - scene_duration_raw))
    
    if scene_duration != scene_duration_raw:
        print(f"  ⚠ Clip duration adjusted from {scene_duration_raw:.1f}s to {scene_duration}s ({model_name} requirement)")
    
    # Recalculate total_duration based on rounded clip_duration
    actual_total_duration = scene_duration * num_scenes
    
    print(f"  ✓ Clip duration: {scene_duration} seconds per clip")
    print(f"  ✓ Number of clips: {num_scenes}")
    print(f"  ✓ Total duration: {actual_total_duration} seconds")
    
    print("  [Step 2/6] Determining aspect ratio...")
    # Determine aspect ratio from resolution
    aspect_ratio = "16:9"  # Default for 480p/1080p
    print(f"  ✓ Aspect ratio: {aspect_ratio}")
    
    print("  [Step 3/6] Loading image generation summary (if available)...")
    # Load image_generation_summary.json if available to get actual element names used for images
    image_element_names = {}
    if image_summary_path and os.path.exists(image_summary_path):
        try:
            with open(image_summary_path, 'r', encoding='utf-8') as f:
                image_summary = json.load(f)
                for elem in image_summary.get("elements", []):
                    # Map by type and try to match to universe element
                    elem_type = elem.get("element_type", "")
                    summary_name = elem.get("element_name", "")
                    # Try to find matching universe element
                    if elem_type == "character":
                        for char in universe_chars.get("characters", []):
                            char_name = char.get("name", "")
                            # If names are similar (handle plural/singular), use image summary name
                            if (char_name == summary_name or 
                                char_name.lower().replace(" ", "") == summary_name.lower().replace(" ", "") or
                                char_name.split("(")[0].strip().lower() in summary_name.lower() or
                                summary_name.split("(")[0].strip().lower() in char_name.lower()):
                                image_element_names[char_name] = summary_name
                    elif elem_type == "location":
                        for loc in universe_chars.get("universe", {}).get("locations", []):
                            loc_name = loc.get("name", "")
                            if (loc_name == summary_name or 
                                loc_name.lower().replace(" ", "") == summary_name.lower().replace(" ", "") or
                                loc_name.split("(")[0].strip().lower() in summary_name.lower() or
                                summary_name.split("(")[0].strip().lower() in loc_name.lower()):
                                image_element_names[loc_name] = summary_name
                    elif elem_type == "prop":
                        for prop in universe_chars.get("universe", {}).get("props", []):
                            prop_name = prop.get("name", "")
                            if (prop_name == summary_name or 
                                prop_name.lower().replace(" ", "") == summary_name.lower().replace(" ", "") or
                                prop_name.split("(")[0].strip().lower() in summary_name.lower() or
                                summary_name.split("(")[0].strip().lower() in prop_name.lower()):
                                image_element_names[prop_name] = summary_name
            print(f"  ✓ Loaded {len(image_element_names)} element name mappings from image summary")
        except Exception as e:
            print(f"  ⚠ Could not load image_generation_summary.json: {e}")
    else:
        print(f"  → No image summary provided, using universe names directly")
    
    print("  [Step 4/6] Building allowed element names list...")
    # Build allowed names list - use image summary names if available, otherwise universe names
    def get_display_name(original_name):
        return image_element_names.get(original_name, original_name)
    
    allowed_char_names = [get_display_name(char.get('name')) for char in universe_chars.get('characters', [])]
    allowed_loc_names = [get_display_name(loc.get('name')) for loc in universe_chars.get('universe', {}).get('locations', [])]
    allowed_prop_names = [get_display_name(prop.get('name')) for prop in universe_chars.get('universe', {}).get('props', [])]
    print(f"  ✓ Allowed names: {len(allowed_char_names)} characters, {len(allowed_loc_names)} locations, {len(allowed_prop_names)} props")
    
    # Load visual effects library only if enabled
    visual_effects_library = None
    if enable_visual_effects:
        print("  [Step 5/6] Loading visual effects library...")
        visual_effects_library = load_visual_effects_library()
        if visual_effects_library:
            print(f"  ✓ Loaded visual effects library")
        else:
            print(f"  ⚠ Visual effects library not found")
    else:
        print("  [Step 5/6] Visual effects disabled (enable_visual_effects=false)")
    
    print("  [Step 6/7] Building LLM prompt...")
    
    # Build visual effects section conditionally
    if enable_visual_effects:
        visual_effects_section = f"""

**VISUAL EFFECTS LIBRARY:**
{visual_effects_library if visual_effects_library else "Visual effects library not available"}

**VISUAL EFFECTS USAGE INSTRUCTIONS:**
1. Select 1-3 visual effects per scene that enhance the eyewear storytelling
2. Effects should complement, not overshadow the frames
3. Use effects that highlight the product benefits (e.g., "Luminous Gaze" for lens quality, "3D Rotation" for design showcase)
4. Include the exact effect name and description in your scene
5. Time the effects appropriately within the scene duration"""
        visual_effects_instruction = """

6. **visual_effects**: Include 1-3 visual effects from the library.
   - Use EXACT effect names from the visual effects library
   - Include full description from library
   - Specify timing within the scene (e.g., "at 2-3 seconds")
   - Effects should enhance the eyewear storytelling"""
        visual_effects_example = """,
      "visual_effects": [
        {{
          "name": "Effect Name from Library",
          "description": "Full description from visual effects library",
          "timing": "When in the scene (e.g., '2-3 seconds', 'throughout', 'at climax')"
        }}
      ]"""
    else:
        visual_effects_section = ""
        visual_effects_instruction = ""
        visual_effects_example = ""
    
    # Pipeline assumes eyewear/sunglasses products only
    prompt = f"""You are a professional video director creating prompts for AI video generation (Veo 3 Fast, Sora 2) specializing in eyewear/sunglasses advertising.

**CRITICAL CONTEXT**: Each scene will be generated INDEPENDENTLY by the video AI model. Each prompt must be COMPLETELY SELF-CONTAINED with all necessary information.

**BRAND CONTEXT:**
- Brand: {config.get('BRAND_NAME', '')}
- Product: {config.get('PRODUCT_DESCRIPTION', '')}
- Tagline: {config.get('TAGLINE', '')}
- Creative Direction: {config.get('CREATIVE_DIRECTION', '')}

**EYEWEAR AD REQUIREMENTS:**
- Frames must be clearly visible and identifiable in EVERY scene
- Include at least one "hero shot" of the glasses per scene
- Show frames from multiple angles across the video
- Include moments where light interacts with lenses (reflections, glare reduction)
- Frame Style: {config.get('FRAME_STYLE', '')}
- Lens Type: {config.get('LENS_TYPE', '')}
- Lens Features: {config.get('LENS_FEATURES', '')}
- Style Persona: {config.get('STYLE_PERSONA', '')}
- Wearing Occasion: {config.get('WEARING_OCCASION', '')}
- Frame Material: {config.get('FRAME_MATERIAL', '')}
**{num_scenes}-SCENE CONCEPT:**
{revised_script}

**UNIVERSE & CHARACTERS:**
{json.dumps(universe_chars, indent=2)}

**CRITICAL: EXACT ELEMENT NAMES TO USE**
You MUST use the EXACT names from the universe_characters.json above. Do NOT create new names or variations.

**ALLOWED CHARACTER NAMES** (use EXACTLY as shown - these are the names that have reference images):
{chr(10).join([f"- {name}" for name in allowed_char_names])}

**ALLOWED LOCATION NAMES** (use EXACTLY as shown - these are the names that have reference images):
{chr(10).join([f"- {name}" for name in allowed_loc_names])}

**ALLOWED PROP NAMES** (use EXACTLY as shown - these are the names that have reference images):
{chr(10).join([f"- {name}" for name in allowed_prop_names])}

**VIDEO SPECIFICATIONS:**
- Resolution: {resolution}
- Aspect Ratio: {aspect_ratio}
- Scene Duration: {scene_duration} seconds (EXACT - all scenes must be this duration)

**SORA 2 PROMPTING BEST PRACTICES:**
1. **Each scene prompt must be self-contained** - include style/aesthetic in EVERY scene (not just the first one)
2. **Be specific, not vague** - "wet asphalt, neon reflections" beats "beautiful street"
3. **Clear who, where, what** - Explicitly state who is in the frame, where they are, what they're doing
4. **For montage/multi-shot scenes**: Clearly distinguish each shot/moment so they don't blend together
5. **Dialogue**: Always specify WHO is speaking (character name or narrator with voice description)
6. **Keep motion simple**: One clear camera move, one clear subject action per shot
7. **Lighting**: Describe quality and source, not just "well lit"
{visual_effects_section}
**INSTRUCTIONS:**
For EACH of the {num_scenes} scenes, create:

**CRITICAL: ALL scenes must be EXACTLY {scene_duration} seconds. Do NOT vary the duration.**

**CRITICAL WORKFLOW REMINDER:**
- The first_frame_image_prompt generates an image FIRST (using nano-banana)
- That image becomes the FIRST FRAME reference for video generation (Veo 3 Fast/Sora 2)
- **Therefore, first_frame_image_prompt MUST copy ALL stylistic elements from video_prompt** - they must be visually identical in style, lighting, camera, color grade, mood, etc.
- If the image style doesn't match the video style, the final video will look inconsistent and unprofessional

1. **video_prompt**: Complete, self-contained prompt following this structure:

   **Style:** [Overall aesthetic, era, film format - e.g., "Modern documentary style, shot on digital cinema camera with natural grain, warm cinematic color grade" - INCLUDE IN EVERY SCENE]
   
   **Scene Description:** [Prose description clearly stating WHO is in the scene, WHERE they are, WHAT they're doing. Be specific with details - colors, textures, objects, expressions]
   
   **Cinematography:**
   Camera shot: [Specific framing - e.g., "wide shot, eye level" or "medium close-up, slight angle from behind"]
   Camera motion: [e.g., "slow push-in" or "handheld, steady" or "static"]
   Lighting: [Quality and source - e.g., "soft window light with warm lamp fill, cool rim from hallway"]
   Mood: [e.g., "contemplative and determined" or "triumphant yet intimate"]
   
   **Actions:** [Break action into specific beats, e.g., "- Takes four steps forward", "- Pauses at window", "- Turns head to camera"]
   
   For MONTAGE scenes with multiple shots: Clearly separate each shot and describe the transition. Example:
   SHOT 1 (0-2 sec): [Who, where, what, how - be specific]
   SHOT 2 (2-4 sec): [Who, where, what, how - be specific]
   SHOT 3 (4-6 sec): [Who, where, what, how - be specific]
   
   Keep the video_prompt detailed but focused on what the model needs to generate THIS specific scene

2. **audio_background**: Detailed background music prompt for ElevenLabs/Suno (genre, mood, tempo, instruments, energy level)

3. **audio_dialogue**: Format as "Speaker: [dialogue]" where Speaker is:
   - EXACT character name from universe_characters.json OR
   - "Narrator (voice description)" with tone/emotion/style
   Example: "Character Name: [their dialogue here]"
   Example: "Narrator (warm, nostalgic voice): [voiceover text here]"

4. **first_frame_image_prompt**: Complete image gen prompt matching {resolution} {aspect_ratio}. 
   
   **CRITICAL WORKFLOW UNDERSTANDING:**
   - The first_frame_image_prompt will be used FIRST to generate a reference image using image generation models (nano-banana)
   - That generated image will then be used as the FIRST FRAME reference for the video generation model (Veo 3 Fast, Sora 2)
   - The video model will use this first frame image to maintain visual consistency throughout the video
   - **THEREFORE: The first_frame_image_prompt MUST match the video_prompt style EXACTLY** - they are part of the SAME visual sequence
   
   **CRITICAL FOR VIDEO CONTINUITY**: The generated first frame image MUST be stylistically identical to what the video_prompt describes. If they don't match, the video will look inconsistent and jarring.
   
   **MANDATORY REQUIREMENTS - COPY EXACTLY FROM YOUR VIDEO_PROMPT:**
   
   When creating first_frame_image_prompt, you MUST:
   1. **Copy the ENTIRE "Style:" line** from your video_prompt verbatim (e.g., "Modern documentary style, shot on digital cinema camera with natural grain, warm cinematic color grade with rich amber tones, authentic mountaineering documentary aesthetic")
   2. **Copy the EXACT "Camera shot:" description** from your video_prompt's Cinematography section (e.g., "Wide establishing shot at eye level showing full mountain backdrop")
   3. **Copy the EXACT "Lighting:" description** from your video_prompt's Cinematography section (e.g., "Golden hour sunrise from right side casting warm amber light across mountain face and protagonist, creating long dramatic shadows, soft natural glow")
   4. **Copy the EXACT "Mood:" description** from your video_prompt's Cinematography section (e.g., "Determined yet uncertain, contemplative and resolute, beginning of a journey")
   5. **Include the EXACT camera type/film style** from your video_prompt (e.g., "shot on digital cinema camera with natural grain")
   6. **Include the EXACT color grade** from your video_prompt (e.g., "warm cinematic color grade with rich amber tones")
   7. Include all characters/locations from elements_used clearly visible
   8. Add hyper-realistic, photorealistic style keywords for image generation
   
   **WORKFLOW REMINDER:** Image is generated FIRST, then used as first frame for video. They MUST be stylistically identical or the video will look wrong.
   
   **The first frame image should look like a still frame FROM the exact video you described in video_prompt - same style, same lighting, same camera, same mood, same everything.**

5. **elements_used**: Characters/props/locations from universe_characters that appear in MULTIPLE scenes.
   - Use EXACT names from ALLOWED lists
   - Include version name if has_multiple_versions: "Name - Version Name"
   - Only include if scenes_used has 2+ scene numbers
{visual_effects_instruction}
**EXAMPLE OUTPUT STRUCTURE:**

Single shot scene example:
```
Style: [Overall aesthetic, film format, color grade - INCLUDE IN EVERY SCENE]

Scene Description: [WHO is in the frame, WHERE they are, WHAT they're doing. Specific details: colors, textures, expressions, objects]

Cinematography:
Camera shot: [Specific framing - wide/medium/close-up, angle]
Camera motion: [Slow push-in/static/dolly/handheld]
Lighting: [Quality and source - soft window light, harsh overhead, golden hour, etc.]
Mood: [Emotional tone - contemplative, triumphant, tense, etc.]

Actions:
- [First specific beat with timing]
- [Second specific beat with timing]
- [Third specific beat with timing]
```

MONTAGE scene example (clearly separate each shot):
```
Style: [Overall aesthetic - INCLUDE color grading transitions if applicable]

SHOT 1 (0-2 seconds - [Shot Name]):
Scene: [WHO, WHERE, WHAT - be specific]
Cinematography: [Framing for this shot]
Lighting: [Lighting for this shot]
Action: [What happens in this shot]

SHOT 2 (2-4 seconds - [Shot Name]):
Scene: [WHO, WHERE, WHAT - be specific]
Cinematography: [Framing for this shot]
Lighting: [Lighting for this shot]
Action: [What happens in this shot]

SHOT 3 (4-6 seconds - [Shot Name]):
Scene: [WHO, WHERE, WHAT - be specific]
Cinematography: [Framing for this shot]
Lighting: [Lighting for this shot]
Action: [What happens in this shot]
```

**OUTPUT FORMAT (JSON):**
```json
{{
  "scenes": [
    {{
      "scene_number": 1,
      "duration_seconds": {scene_duration},
      "video_prompt": "[Complete self-contained prompt following structure above]",
      "audio_background": "[Music prompt with genre, mood, tempo, instruments]",
      "audio_dialogue": "Speaker Name: [text]" or "Narrator (voice): [text]" or null,
      "first_frame_image_prompt": "[Hyper-realistic image prompt matching video_prompt style EXACTLY - same camera, lighting, mood, color grade, film style - ready for video generation continuity]",
      "elements_used": {{
        "characters": ["Exact Name - Version Name"],
        "locations": ["Exact Name - Version Name"],
        "props": ["Exact Name"]
      }}{visual_effects_example}
    }}
  ]
}}
```"""
    print(f"  ✓ Prompt built ({len(prompt)} chars)")
    
    print("  [Step 7/7] Calling LLM to generate scene prompts...")
    provider, model_name = model.split("/", 1) if "/" in model else ("anthropic", model)
    api_key = get_api_key(provider)
    
    # Define JSON schema for structured output (OpenAI)
    scene_properties = {
        "scene_number": {"type": "integer"},
        "duration_seconds": {"type": "integer"},
        "video_prompt": {"type": "string"},
        "audio_background": {"type": "string"},
        "audio_dialogue": {"type": ["string", "null"]},
        "first_frame_image_prompt": {"type": "string"},
        "elements_used": {
            "type": "object",
            "properties": {
                "characters": {"type": "array", "items": {"type": "string"}},
                "locations": {"type": "array", "items": {"type": "string"}},
                "props": {"type": "array", "items": {"type": "string"}}
            }
        }
    }
    
    # Add visual_effects to schema only if enabled
    if enable_visual_effects:
        scene_properties["visual_effects"] = {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "timing": {"type": "string"}
                },
                "required": ["name", "description", "timing"]
            }
        }
    
    scene_schema = {
        "type": "object",
        "properties": {
            "scenes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": scene_properties,
                    "required": ["scene_number", "duration_seconds", "video_prompt", "audio_background", "first_frame_image_prompt", "elements_used"]
                }
            }
        },
        "required": ["scenes"],
        "additionalProperties": False
    }
    
    print(f"  → Calling {provider}/{model_name}...")
    if thinking and thinking > 0:
        print(f"  → Extended thinking enabled (thinking={thinking}) - may take 1-5 minutes...")
    else:
        print(f"  → Thinking disabled (fast mode) - should take 10-30 seconds...")
    print(f"  → Waiting for LLM response...")
    
    # Measure pure LLM API call time
    llm_start_time = time.time()
    if provider == "openai":
        # Use structured outputs for guaranteed valid JSON (GPT-4o and later)
        if "gpt-4o" in model_name or "gpt-5" in model_name:
            print(f"  → Using OpenAI Structured Outputs for guaranteed valid JSON...")
            from openai import OpenAI
            client = OpenAI(api_key=api_key)
            
            completion = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "scene_prompts_schema",
                        "strict": True,
                        "schema": scene_schema
                    }
                }
            )
            response = completion.choices[0].message.content
        else:
            # Fallback for older models
            response = call_openai(prompt, model_name, api_key, reasoning_effort="high" if thinking else None)
    else:
        # Claude: Use prompt caching + ThinkingBlock handling
        print(f"  → Using Anthropic Prompt Caching to reduce costs and latency...")
        thinking_value = thinking if thinking and thinking > 0 else None
        response = call_anthropic_with_caching(
            prompt, model_name, api_key, 
            thinking=thinking_value, 
            max_tokens=10000, 
            temperature=temperature
        )
    llm_end_time = time.time()
    llm_duration = llm_end_time - llm_start_time
    
    print(f"  ✓ LLM response received ({len(response)} chars)")
    print(f"  ⏱️  Pure LLM API call time: {llm_duration:.1f} seconds ({llm_duration/60:.1f} minutes)")
    print(f"  → Parsing JSON from response...")
    
    # Extract JSON from response (handles markdown code blocks)
    json_text = response.strip()
    
    # Remove markdown code blocks if present
    if "```json" in json_text:
        json_text = json_text.split("```json")[1].split("```")[0].strip()
    elif "```" in json_text:
        json_text = json_text.split("```")[1].split("```")[0].strip()
    
    # Find JSON object boundaries if there's extra text
    if not json_text.startswith("{"):
        start = json_text.find("{")
        end = json_text.rfind("}") + 1
        if start != -1 and end > start:
            json_text = json_text[start:end]
    
    print(f"  → Loading JSON...")
    try:
        result = json.loads(json_text)
    except json.JSONDecodeError as e:
        print(f"  ⚠ JSON parsing failed: {e}")
        print(f"  → Attempting to fix common JSON issues...")
        
        # Fix common LLM JSON issues:
        # 1. Remove trailing commas before closing brackets/braces
        json_text = re.sub(r',(\s*[}\]])', r'\1', json_text)
        # 2. Remove comments (// or /* */)
        json_text = re.sub(r'//.*?\n', '\n', json_text)
        json_text = re.sub(r'/\*.*?\*/', '', json_text, flags=re.DOTALL)
        
        try:
            result = json.loads(json_text)
            print(f"  ✓ JSON fixed and parsed successfully!")
        except json.JSONDecodeError as e2:
            print(f"  ✗ Still failed after automatic fixes: {e2}")
            print(f"  → Saving debug info...")
            
            # Save to debug directory
            debug_dir = Path(__file__).parent.parent / "outputs" / "debug"
            debug_dir.mkdir(parents=True, exist_ok=True)
            
            # Save raw response
            raw_file = debug_dir / "failed_response.txt"
            with open(raw_file, 'w', encoding='utf-8') as f:
                f.write("=== ORIGINAL RESPONSE ===\n")
                f.write(response)
                f.write("\n\n=== EXTRACTED JSON TEXT ===\n")
                f.write(json_text)
                f.write(f"\n\n=== ERROR ===\n{e2}")
            
            print(f"  → Debug info saved to: {raw_file}")
            print(f"  → Error location: line {e2.lineno}, column {e2.colno}")
            
            # Show context around error
            if hasattr(e2, 'pos') and e2.pos:
                start = max(0, e2.pos - 100)
                end = min(len(json_text), e2.pos + 100)
                print(f"  → Context: ...{json_text[start:end]}...")
            
            raise Exception(f"Failed to parse JSON after fixes. See {raw_file} for details.") from e2
    
    print(f"  ✓ JSON parsed successfully - {len(result.get('scenes', []))} scenes generated")
    
    step_end_time = time.time()
    total_duration = step_end_time - step_start_time
    print(f"  ⏱️  Total Step 7 time: {total_duration:.1f} seconds ({total_duration/60:.1f} minutes)")
    
    return result


if __name__ == "__main__":
    """Run directly from command line."""
    import argparse
    import re
    
    parser = argparse.ArgumentParser(description="Generate scene prompts for video generation")
    parser.add_argument("input_file", type=str, help="Path to revised concept file (e.g., .../rolex_achievement_inspirational_advanced_claude_sonnet_4.5_revised.txt)")
    parser.add_argument("--duration", type=int, default=30, help="Total video duration in seconds")
    parser.add_argument("--model", type=str, default="anthropic/claude-sonnet-4-5-20250929", help="LLM model")
    parser.add_argument("--resolution", type=str, default="720p", help="Video resolution")
    
    args = parser.parse_args()
    
    # Parse input file path to extract batch folder and concept name
    input_path = Path(args.input_file).resolve()
    
    # Extract concept name from filename (remove _revised.txt)
    concept_name = input_path.stem.replace("_revised", "")
    
    # Extract batch folder from path (parent's parent)
    # Path structure: .../batch_folder/concept_name/concept_name_revised.txt
    batch_folder = input_path.parent.parent.name
    concept_dir = input_path.parent
    
    # Extract brand name from concept name (first part before first underscore)
    brand_name = concept_name.split("_")[0] if "_" in concept_name else "unknown"
    
    # Construct all paths automatically (matching pipeline structure exactly)
    args.concept = str(input_path)
    args.universe = str(BASE_DIR / "s5_generate_universe" / "outputs" / batch_folder / concept_name / f"{concept_name}_universe_characters.json")
    args.config = str(BASE_DIR / "s1_generate_concepts" / "inputs" / "configs" / f"{brand_name}.json")
    # Pipeline expects: universe_images_dir / "image_generation_summary.json" where universe_images_dir = s6/.../{batch_folder}/{concept_name}
    # But actual file structure has extra level: s6/.../{batch_folder}/{concept_name}/{concept_name}/
    # Try pipeline path first, then actual path
    pipeline_image_summary = BASE_DIR / "s6_generate_reference_images" / "outputs" / batch_folder / concept_name / "image_generation_summary.json"
    actual_image_summary = BASE_DIR / "s6_generate_reference_images" / "outputs" / batch_folder / concept_name / concept_name / "image_generation_summary.json"
    if pipeline_image_summary.exists():
        args.image_summary = str(pipeline_image_summary)
    elif actual_image_summary.exists():
        args.image_summary = str(actual_image_summary)
    else:
        args.image_summary = None
    args.output = str(BASE_DIR / "s7_generate_scene_prompts" / "outputs" / batch_folder / concept_name / f"{concept_name}_scene_prompts.json")
    
    print("=" * 80)
    print("STEP 7: Generate Scene Prompts (Direct Run)")
    print("=" * 80)
    print(f"Input file: {args.input_file}")
    print(f"Extracted batch folder: {batch_folder}")
    print(f"Extracted concept name: {concept_name}")
    print(f"Extracted brand name: {brand_name}")
    print()
    print("Derived paths:")
    print(f"  Concept: {args.concept}")
    print(f"  Universe: {args.universe}")
    print(f"  Config: {args.config}")
    print(f"  Image summary: {args.image_summary}")
    print(f"  Output: {args.output}")
    print()
    
    # Load files
    print("Loading files...")
    with open(args.concept, 'r', encoding='utf-8') as f:
        concept_content = f.read()
    print(f"  ✓ Concept: {len(concept_content)} chars")
    
    with open(args.universe, 'r', encoding='utf-8') as f:
        universe_chars = json.load(f)
    print(f"  ✓ Universe: {len(universe_chars.get('characters', []))} characters")
    
    with open(args.config, 'r', encoding='utf-8') as f:
        config_data = json.load(f)
    print(f"  ✓ Config: {config_data.get('BRAND_NAME', 'N/A')}")
    
    image_summary_path = args.image_summary if Path(args.image_summary).exists() else None
    if image_summary_path:
        print(f"  ✓ Image summary: {image_summary_path}")
    else:
        print(f"  ⚠ Image summary: Not found (optional)")
    
    print()
    print("=" * 80)
    
    # Generate
    result = generate_scene_prompts(
        concept_content,
        universe_chars,
        config_data,
        duration=args.duration,
        model=args.model,
        resolution=args.resolution,
        image_summary_path=image_summary_path
    )
    
    # Save
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2)
    
    # Verify
    total_dur = sum(s.get('duration_seconds', 0) for s in result.get('scenes', []))
    print()
    print("=" * 80)
    print(f"✓ COMPLETE")
    print(f"✓ Total duration: {total_dur} seconds (expected: {args.duration})")
    for scene in result.get('scenes', []):
        print(f"  Scene {scene.get('scene_number')}: {scene.get('duration_seconds')}s")
    print(f"✓ Saved: {output_path}")
    print("=" * 80)

