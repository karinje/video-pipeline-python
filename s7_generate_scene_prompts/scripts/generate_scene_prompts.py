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
    
    # NO CACHING - Direct simple call (caching causes 20min delays)
    params = {
        "model": model,
        "messages": [
            {"role": "user", "content": prompt}
        ]
    }
    
    print(f"    [DEBUG] Building API request (thinking={thinking})...")
    
    # Add thinking parameter
    if thinking is not None and thinking > 0:
        if isinstance(thinking, dict):
            params["thinking"] = thinking
            budget_tokens = thinking.get("budget_tokens", 10000)
        elif isinstance(thinking, int):
            budget_tokens = thinking
            params["thinking"] = {"type": "enabled", "budget_tokens": budget_tokens}
        
        if max_tokens is None:
            # Total max_tokens = thinking + response
            # With thinking=5000, we want 12k response, so 17k total
            params["max_tokens"] = 17000  # Total: thinking (5000) + response (12000)
        else:
            params["max_tokens"] = max_tokens
        
        params["temperature"] = temperature if temperature is not None else 1
    else:
        # Scene prompts JSON with new timestamp format needs more tokens
        params["max_tokens"] = max_tokens if max_tokens else 17000
        params["temperature"] = temperature if temperature is not None else 0.5
    
    print(f"    [DEBUG] Sending request to Anthropic API...", flush=True)
    print(f"    [DEBUG] Model: {model}, Max tokens: {params.get('max_tokens')}, Thinking: {thinking}", flush=True)
    
    # Use streaming if thinking budget is high (required for long operations)
    use_streaming = thinking and thinking >= 5000
    
    api_start = time.time()
    try:
        if use_streaming:
            print(f"    [DEBUG] Using streaming mode (thinking={thinking} requires it)...", flush=True)
            full_response = ""
            chunk_count = 0
            with client.messages.stream(**params) as stream:
                for text in stream.text_stream:
                    full_response += text
                    chunk_count += 1
                    if chunk_count % 50 == 0:  # Progress indicator
                        print(f"    [DEBUG] Received {chunk_count} chunks, {len(full_response)} chars so far...", flush=True)
                # Get the final message to ensure we have everything
                final_message = stream.get_final_message()
            
            api_end = time.time()
            print(f"    [DEBUG] ✓ API response received in {api_end - api_start:.1f} seconds", flush=True)
            print(f"    [DEBUG] Total chunks received: {chunk_count}, Total chars: {len(full_response)}", flush=True)
            
            # Use final message text if available (more reliable)
            if hasattr(final_message, 'content') and final_message.content:
                final_text = ""
                for block in final_message.content:
                    if hasattr(block, 'text'):
                        final_text += block.text
                if final_text and len(final_text) > len(full_response):
                    print(f"    [DEBUG] Using final_message.content ({len(final_text)} chars) instead of streamed ({len(full_response)} chars)", flush=True)
                    full_response = final_text
            
            # Create a mock response object with text property
            class MockResponse:
                def __init__(self, text):
                    self.text = text
                    self.content = [type('obj', (object,), {'type': 'text', 'text': text})]
            response = MockResponse(full_response)
        else:
            response = client.messages.create(**params)
        api_end = time.time()
        print(f"    [DEBUG] ✓ API response received in {api_end - api_start:.1f} seconds", flush=True)
        
        # Save raw response text for debugging (skip pickle for streaming responses)
        if not use_streaming:
            import pickle
            from pathlib import Path
            debug_dir = Path(__file__).parent.parent / "outputs" / "debug"
            debug_dir.mkdir(parents=True, exist_ok=True)
            response_file = debug_dir / f"anthropic_response_{int(time.time())}.pkl"
            try:
                with open(response_file, 'wb') as f:
                    pickle.dump(response, f)
                print(f"    [DEBUG] Response saved to: {response_file}", flush=True)
            except Exception as e:
                print(f"    [DEBUG] Could not save response (streaming mode): {e}", flush=True)
        
    except Exception as e:
        api_end = time.time()
        print(f"    [DEBUG] ✗ API call failed after {api_end - api_start:.1f} seconds: {e}", flush=True)
        raise
    
    # Extract content from response - use .text property which handles thinking blocks automatically
    print(f"    [DEBUG] Extracting content using .text property...", flush=True)
    
    try:
        # Anthropic SDK's .text property automatically filters out thinking blocks
        content = response.text
        print(f"    [DEBUG] Content extracted: {len(content)} chars", flush=True)
        return content
    except AttributeError:
        # Fallback to manual extraction if .text doesn't exist
        print(f"    [DEBUG] .text not available, using manual extraction...", flush=True)
        content_parts = []
        for block in response.content:
            if hasattr(block, 'type') and block.type == 'thinking':
                continue
            if hasattr(block, 'text'):
                content_parts.append(block.text)
        
        if not content_parts:
            raise ValueError("No text content found in response")
        
        content = '\n'.join(content_parts)
        print(f"    [DEBUG] Content extracted: {len(content)} chars", flush=True)
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
    
    print(f"[{time.strftime('%H:%M:%S')}] [Step 2/7] Determining aspect ratio...")
    # Determine aspect ratio from resolution
    aspect_ratio = "16:9"  # Default for 480p/1080p
    print(f"  ✓ Aspect ratio: {aspect_ratio}")
    
    print(f"[{time.strftime('%H:%M:%S')}] [Step 3/7] Loading image generation summary (if available)...")
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
    
    print(f"[{time.strftime('%H:%M:%S')}] [Step 4/7] Building allowed element names list...")
    # Build allowed names list - use image summary names if available, otherwise universe names
    def get_display_name(original_name):
        return image_element_names.get(original_name, original_name)
    
    allowed_char_names = [get_display_name(char.get('name')) for char in universe_chars.get('characters', [])]
    allowed_loc_names = [get_display_name(loc.get('name')) for loc in universe_chars.get('universe', {}).get('locations', [])]
    allowed_prop_names = [get_display_name(prop.get('name')) for prop in universe_chars.get('universe', {}).get('props', [])]
    print(f"  ✓ Allowed names: {len(allowed_char_names)} characters, {len(allowed_loc_names)} locations, {len(allowed_prop_names)} props")
    
    # Build reference images documentation with type labels and canonical states
    reference_images_list = []
    for char in universe_chars.get('characters', []):
        char_name = get_display_name(char.get('name'))
        canonical_state = char.get('canonical_state', 'Character in neutral state')
        reference_images_list.append(f"- {char_name} [CHARACTER REFERENCE] (canonical state: {canonical_state})")
    
    for loc in universe_chars.get('universe', {}).get('locations', []):
        loc_name = get_display_name(loc.get('name'))
        canonical_state = loc.get('canonical_state', 'Location in neutral state')
        reference_images_list.append(f"- {loc_name} [LOCATION REFERENCE] (canonical state: {canonical_state})")
    
    for prop in universe_chars.get('universe', {}).get('props', []):
        prop_name = get_display_name(prop.get('name'))
        canonical_state = prop.get('canonical_state', 'Prop in neutral state')
        reference_images_list.append(f"- {prop_name} [PRODUCT REFERENCE] (canonical state: {canonical_state})")
    
    reference_images_documentation = "\n".join(reference_images_list)
    
    # Load visual effects library only if enabled
    visual_effects_library = None
    if enable_visual_effects:
        print(f"[{time.strftime('%H:%M:%S')}] [Step 5/7] Loading visual effects library...")
        visual_effects_library = load_visual_effects_library()
        if visual_effects_library:
            print(f"  ✓ Loaded visual effects library")
        else:
            print(f"  ⚠ Visual effects library not found")
    else:
        print(f"[{time.strftime('%H:%M:%S')}] [Step 5/7] Visual effects disabled (enable_visual_effects=false)")
    
    print(f"[{time.strftime('%H:%M:%S')}] [Step 6/7] Building LLM prompt...")
    
    # Build visual effects section conditionally
    if enable_visual_effects:
        visual_effects_section = f"""

**VISUAL EFFECTS LIBRARY:**
{visual_effects_library if visual_effects_library else "Visual effects library not available"}

**VISUAL EFFECTS USAGE INSTRUCTIONS:**
1. AT MOST 1 visual effect per scene - can be ZERO if nothing fits naturally
2. Only include an effect when it NATURALLY ENHANCES the scene - do NOT force an effect just to have one
3. Effect should complement, not overshadow the frames
4. Use effects that highlight product benefits (e.g., "Luminous Gaze" for lens quality, "3D Rotation" for design showcase)
5. Include exact effect name and description from the library
6. Time the effect appropriately within the scene duration
7. If NO effect fits naturally, set visual_effect to null - this is COMPLETELY ACCEPTABLE"""
    else:
        visual_effects_section = ""
    
    # Pipeline assumes eyewear/sunglasses products only
    prompt = f"""You are a professional video director creating prompts for AI video generation (Veo 3 Fast, Sora 2) specializing in eyewear/sunglasses advertising.

**CRITICAL CONTEXT**: Each scene will be generated INDEPENDENTLY by the video AI model. Each prompt must be COMPLETELY SELF-CONTAINED with all necessary information.

════════════════════════════════════════════════════════════════════════════════
🚨 MOST CRITICAL REQUIREMENTS - READ FIRST 🚨
════════════════════════════════════════════════════════════════════════════════

**REQUIREMENT 1: SCENE TRANSITION CONTINUITY (CRITICAL FOR FINAL AD)**

All {num_scenes} scenes will be STITCHED TOGETHER into one coherent advertisement. Therefore:

**VIDEO TRANSITIONS:**
1. **Each scene MUST transition smoothly into the next scene** - NO abrupt endings or jarring cuts
2. **Scene endings must set up the next scene** - Consider what happens next when planning the final 2 seconds of each scene
3. **Scene beginnings must flow from previous scene** - Consider what came before when planning the first 2 seconds (except Scene 1)
4. **Visual/narrative bridges required** - Use motion, composition, or thematic elements that carry across the cut
5. **Timing must support flow** - Actions should feel continuous across scenes, not like separate isolated clips

**AUDIO TRANSITIONS (EQUALLY CRITICAL):**
1. **Music MUST NOT hard-stop at scene end** - Use "continues into next scene", "fades preparing for transition", "sustains as scene ends"
2. **SFX should bridge scenes where logical** - If same location (e.g., rain, traffic), continue the sound across the cut
3. **Ambience should evolve naturally** - Don't reset ambience abruptly; transition it (e.g., "rain continues but softens", "traffic fades as we move indoors")
4. **Audio hierarchy throughout**: Dialogue > SFX > Ambience > Music (duck music/ambience when dialogue present)
5. **Think: "How does THIS scene's audio flow INTO the NEXT scene's audio?"**

**Example of GOOD transition planning:**
- Scene 1 ends (6-8s): Hero discovers sunglasses, begins to raise them toward face. Music: piano melody completes phrase but sustains, setting up continuation. SFX: case opening sound begins. Ambience: rain continues.
- Scene 2 begins (0-2s): Continuation of raising motion, now placing them on face. Music: piano sustained note from previous scene now shifts to new melody. SFX: case opening sound completes, frames slide onto face. Ambience: rain continues from previous scene.

**Example of BAD transition (DO NOT DO THIS):**
- Scene 1 ends: Hero freezes mid-action. Music: abrupt stop at 8 seconds. SFX: silence. Ambience: cuts off.
- Scene 2 begins: Entirely new action. Music: suddenly starts from scratch. SFX: unrelated sounds. Ambience: completely different soundscape with no connection.

**REQUIREMENT 2: FIRST FRAME FACE VISIBILITY (CRITICAL FOR CHARACTER CONSISTENCY)**

The first_frame_image_prompt generates an image that Veo uses as the REFERENCE for the ENTIRE video clip.

**CRITICAL RULE: If a character/person appears in the scene, their COMPLETE FACE must be FULLY VISIBLE and PROPERLY FRAMED in the first frame image.**

Why this matters:
- Veo uses the first frame to understand what the character looks like
- If you hide/crop the face in the first frame (e.g., extreme close-up of just eyes, back of head, side profile with face obscured), Veo will GENERATE A DIFFERENT FACE when the camera moves or character turns
- This breaks character consistency and ruins the video

**MANDATORY FACE FRAMING for first_frame_image_prompt when character is present:**
- ✅ CORRECT: "Medium shot showing Hero's full face clearly visible" (face occupies 20-40% of frame height)
- ✅ CORRECT: "Medium close-up with Hero centered, face fully recognizable" (face occupies 30-50% of frame)
- ❌ WRONG: "Wide shot" (face too small, unrecognizable, distant)
- ❌ WRONG: "Extreme close-up of Hero's eyes through lens" (face cropped, only partial features visible)
- ❌ WRONG: "Over-shoulder shot, Hero's face partially obscured" (face not fully visible)
- ❌ WRONG: "Hero from behind, back of head" (face not visible at all)

**FIRST FRAME SHOT REQUIREMENTS:**
- Use Medium Shot or Medium Close-Up for character scenes (NOT Wide, NOT Extreme Close-Up)
- Face should occupy 20-40% of frame height for clear visibility and recognition
- Full face visible: eyes, nose, mouth, chin, forehead all clearly recognizable
- If your timestamp blocks include camera moves (push-in, pull-out), the first frame MUST show the character's face BEFORE those moves happen

**REQUIREMENT 3: SUNGLASSES STATE CONSISTENCY (CRITICAL FOR EYEWEAR ADS)**

**SUNGLASSES STATE RULES - MUST FOLLOW IN EVERY TIMESTAMP:**

1. **Character can wear ONLY ONE pair of sunglasses at a time** - NEVER wear multiple pairs stacked or layered
2. **To switch frames, MUST explicitly show removal and wearing sequence:**
   - First: Remove current pair (state: "NOT wearing any sunglasses")
   - Then: Put on new pair (state: "NOW WEARING [new model]")
3. **Every visual description MUST explicitly state sunglasses status:**
   - "NOT wearing any sunglasses" (when bare face)
   - "WEARING [specific SunVue model]" (when wearing)
   - "Removing [model] with [hand]" (during removal)
   - "Putting on [model]" (during wearing)
4. **Once removed, old frames stay removed** - they don't magically reappear unless explicitly shown being put back on
5. **Switching action must be clear and complete:**
   - ❌ WRONG: "Hero now wearing wayfarers" (what happened to the aviators she was wearing?)
   - ✅ CORRECT: "Hero removes aviators with left hand (NOT wearing any). Takes wayfarers with right hand. Slides wayfarers onto face (NOW WEARING wayfarers only)."

**EXPLICIT STATE TRACKING REQUIRED:**
In each timestamp's visual description, you MUST include the current sunglasses state:
- Before wearing any: "NOT wearing any sunglasses - face fully visible"
- While wearing: "WEARING SunVue Aviator Sunglasses on face"
- During switch: "Removing aviators (NOT wearing any), putting on wayfarers (NOW WEARING wayfarers)"

════════════════════════════════════════════════════════════════════════════════

**VEO 3 WORKFLOW (Google Recommended)**: 
- First frame is generated separately using an image model (Imagen/nano-banana) from first_frame_image_prompt
- That generated image becomes the starting frame for Veo's image-to-video generation
- Timestamp blocks tell Veo how to ANIMATE that first frame with synchronized video and audio
- Therefore: first_frame_image_prompt and the first timestamp block (00:00-00:02) must be PERFECTLY aligned in style/lighting/camera/mood

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

**REFERENCE IMAGES AVAILABLE (with canonical states):**
These reference images will be attached to first_frame_image_prompt generation. Each shows the element in its BASE/NEUTRAL/CANONICAL state:

{reference_images_documentation}

When creating first_frame_image_prompt, you will include these with proper [TYPE REFERENCE] labels and instruct whether to use AS-IS or MODIFY based on the scene requirements.

**VIDEO SPECIFICATIONS:**
- Resolution: {resolution}
- Aspect Ratio: {aspect_ratio}
- Scene Duration: {scene_duration} seconds (EXACT - all scenes must be this duration)

**VEO 3 PROMPTING BEST PRACTICES (Google's Official Guidelines):**
1. **Each scene prompt must be self-contained** - include style/aesthetic in EVERY scene (not just the first one)
2. **Be specific, not vague** - "wet asphalt, neon reflections" beats "beautiful street"
3. **Clear who, where, what** - Explicitly state who is in the frame, where they are, what they're doing
4. **For montage/multi-shot scenes**: Clearly distinguish each shot/moment so they don't blend together
5. **Dialogue**: Always specify WHO is speaking (character name or narrator with voice description)
6. **Keep motion simple**: One clear camera move, one clear subject action per shot
7. **CRITICAL: Always specify depth composition** - Foreground/Midground/Background enables Veo to create parallax and realistic camera moves
8. **CRITICAL: Always specify lens type and depth of field** - Controls focus falloff, bokeh, and lens character (e.g., "50mm f/2.8 shallow depth")
9. **CRITICAL: Always specify directional lighting** - Give source and direction for key/fill/rim/practical lights (e.g., "key light: overhead left 45°"), not just mood
10. **Include atmospheric particles** - Haze, mist, dust motes, breath vapor add cinematic depth and subtle motion cues
11. **Specify material surfaces** - Glossy/matte/reflective properties help Veo render realistic materials and reflections
12. **Add small environmental motion** - Distant traffic, drifting steam, swaying elements make the world feel alive
{visual_effects_section}
**INSTRUCTIONS:**
For EACH of the {num_scenes} scenes, create:

**CRITICAL REQUIREMENTS:**
1. **YOU MUST GENERATE ALL {num_scenes} SCENES** - The "scenes" array MUST contain exactly {num_scenes} complete scene objects (scene_number 1 through {num_scenes}). Do NOT stop after generating only 1 or 2 scenes.
2. **EVERY scene must be EXACTLY {scene_duration} seconds** - Set "duration_seconds": {scene_duration} for all {num_scenes} scenes. Do NOT vary the duration.

**CRITICAL WORKFLOW REMINDER:**
- The first_frame_image_prompt generates an image FIRST (using nano-banana)
- That image becomes the FIRST FRAME reference for video generation (Veo 3 Fast/Sora 2)
- Veo will generate video + audio from timestamp-based prompts following Google's recommended format
- Each timestamp block (e.g., "00:00-00:02") contains visual, cinematography, and audio (dialogue, sfx, ambience, music)
- Audio follows strict hierarchy: Dialogue > SFX > Ambience > Music (music ducks under dialogue)

1. **video_summary**: One-sentence overview of what happens in this scene (for UI display to user)

2. **audio_summary**: One-sentence description of the audio journey in this scene (for UI display to user)

3. **visual_effect** (singular): Select the SINGLE MOST SUITABLE visual effect for this scene from the library. Include name, description, and timing. If no effect is appropriate, set to null.

4. **Timestamp blocks** (00:00-00:02, 00:02-00:04, etc.): For a {scene_duration}-second scene, create {scene_duration//2} timestamp blocks of 2 seconds each.

   Each timestamp block MUST contain these fields:
   
   **visual**: Complete prose description of what is happening visually in this 2-second segment. CRITICAL: Each timestamp must be SELF-CONTAINED with all essential visual information.
   
   Include:
   - WHO: Character(s) in frame with key appearance details that ensure consistency (e.g., "Hero/Main Commuter, 28-year-old woman with shoulder-length dark hair, grey wool coat")
   - WHERE: Location/setting for this segment (e.g., "under concrete bus stop shelter", "at rain-slicked urban intersection") - restate even if established earlier for Veo's clarity
   - WHAT ACTION: Specific physical action being performed (e.g., "checking phone with squinting tired eyes", "sliding aviators onto face")
   - **SUNGLASSES STATE (MANDATORY - MUST BE EXPLICIT IN EVERY TIMESTAMP)**: State which sunglasses are currently worn:
     * "NOT wearing any sunglasses - face fully visible" (when bare face)
     * "WEARING SunVue [Model] Sunglasses on face" (when wearing specific pair)
     * When switching: "Removes [old model] with [hand] (NOT wearing any). Takes [new model] with [hand]. Slides [new model] onto face (NOW WEARING [new model] only)."
     * NEVER: "wearing multiple pairs", "aviators appear again" (once removed, stay removed unless explicitly put back on)
   - WHAT OBJECTS/PRODUCTS: All visible props and products, especially eyewear (CRITICAL: state if sunglasses are worn/held/visible/prominent - e.g., "wearing gold SunVue aviators on face, frames catching light", "SunVue case held in right hand, logo visible")
   - HOW: Character expressions, emotions, body language that drive the narrative (e.g., "weary expression with hunched shoulders", "confident smile forming, posture straightening")
   - Material surfaces if pivotal to visual quality (glossy puddles, matte concrete, polished metal frames)
   - Atmospheric particles if essential to cinematic depth (light mist, breath vapor in cold air, dust motes in light)
   - Small environmental motion if it enhances realism (distant car passing, steam drifting, rain droplets on lens)
   
   **cinematography**: Complete cinematography description for this segment. Include ALL of:
   - Camera shot: [Specific framing - e.g., "Medium shot at eye level, centered"]
   - Lens & Depth: [CRITICAL - lens type (e.g., "50mm standard", "85mm portrait"), aperture/depth of field (e.g., "f/2.8 shallow depth with creamy bokeh")]
   - Camera motion: [e.g., "slow dolly-in at 2cm/sec, easing" or "static locked-off" or "handheld subtle drift"]
   - Composition: [CRITICAL - depth layers: "Foreground: [elements], Midground: [subject], Background: [distant elements]"]
   - Lighting: [CRITICAL - directional sources: "Key light: [source + direction], Fill light: [source], Rim light: [source + direction], Practical lights: [sources]"]
   - Style: [Overall aesthetic for this timestamp - e.g., "Modern documentary, desaturated grey-blue grade, natural film grain"]
   - Mood: [Emotional tone - e.g., "weary and mundane"]
   
   **dialogue**: Dialogue spoken in this 2-second segment. Format as "Character Name: [dialogue text]" or "Narrator (voice description): [voiceover text]" or null if no dialogue.
   
   **sfx**: Sound effects for this 2-second segment. List 1-3 key sound effects, most important first. Be specific (e.g., "phone screen tap, distant car horn" not just "city sounds"). Consider what creates the sound and its character.
   
   **ambience**: Background ambient sound for this 2-second segment. Describe the sonic environment (e.g., "light rain pattering on concrete shelter, distant traffic hum, puddle ripples"). Should evolve naturally across timestamps, not reset abruptly.
   
   **music**: Background music description for this 2-second segment. Include:
   - Instrumentation (e.g., "minimal melancholic piano")
   - Tempo if relevant (e.g., "60 BPM")
   - Dynamics/volume (e.g., "very muted, sparse" or "building tension")
   - How it evolves (e.g., "adds second note for tension" or "sustains preparing for next scene")
   - Note: Music should duck (lower volume) when dialogue is present
   - Note: Music should transition smoothly between scenes, not hard-stop
   
   **CRITICAL AUDIO HIERARCHY:** In each timestamp, audio priority is: Dialogue > SFX > Ambience > Music. When dialogue is present, music and ambience should duck in volume.

5. **first_frame_image_prompt**: Complete image gen prompt matching {resolution} {aspect_ratio}. 
   
   **CRITICAL WORKFLOW UNDERSTANDING:**
   - The first_frame_image_prompt will be used FIRST to generate a reference image using image generation models (nano-banana)
   - Reference images from universe/characters will be attached (showing elements in their CANONICAL state)
   - That generated image will then be used as the FIRST FRAME reference for video generation (Veo 3 Fast/Sora 2)
   - The video model will use this first frame image to maintain visual consistency throughout the video
   - **THEREFORE: The first_frame_image_prompt MUST match the FIRST TIMESTAMP BLOCK (00:00-00:02) style EXACTLY** - same visual, cinematography, style, lighting, composition
   
   **CRITICAL FOR VIDEO CONTINUITY**: The generated first frame image MUST be stylistically identical to the first timestamp block. If they don't match, the video will look inconsistent and jarring.
   
   **REFERENCE IMAGES HANDLING - CRITICAL:**
   
   **IMPORTANT: Reference image files will be physically attached to the image generation API call.**
   
   These are actual image files (not descriptions) showing elements in their CANONICAL state (from universe_characters JSON below).
   The image generation model (nano-banana-pro) will receive these image files as input and must use them as the BASE/STARTING POINT.
   
   In your first_frame_image_prompt, you MUST include a "REFERENCE IMAGES ATTACHED:" section that:
   1. Explicitly states that reference image files are being provided as input
   2. For each element, clearly describe what the reference image shows (copy the canonical_state from universe_characters)
   3. Explicitly instruct how to use the reference image:
      - "USE THIS REFERENCE IMAGE AS-IS" (if no changes needed)
      - "USE THIS REFERENCE IMAGE AS BASE AND MODIFY IT TO: [specific transformation]" (if changes needed)
   
   **Format:**
   ```
   [Style, camera, lens, composition, lighting, mood from first timestamp block (00:00-00:02)]
   
   REFERENCE IMAGES CONTEXT:
   You are receiving reference images showing the CANONICAL APPEARANCE of characters, locations, and props from this advertisement universe. These images show how each element looks in its BASE/NEUTRAL state. Your task is to use these as the visual foundation and transform them according to the instructions below to match this specific scene's requirements.
   
   REFERENCE IMAGES ATTACHED (each element has one reference image file):
   - Element Name [CHARACTER/LOCATION/PRODUCT REFERENCE] (reference image shows: [canonical_state from universe_characters - their BASE appearance]) - USE THIS REFERENCE IMAGE AS-IS / USE THIS REFERENCE IMAGE AS BASE AND MODIFY IT TO: [specific transformation for this scene]
   
   [Hyper-realistic photorealistic composition matching first timestamp visual description]
   ```
   
   **Example - Scene 1 (before transformation):**
   ```
   Modern documentary, wide shot, natural lighting, muted color grade.
   
   REFERENCE IMAGES CONTEXT:
   You are receiving reference images showing the CANONICAL APPEARANCE of characters, locations, and props from this advertisement universe. These images show how each element looks in its BASE/NEUTRAL state. Your task is to use these as the visual foundation and transform them according to the instructions below to match this specific scene's requirements.
   
   REFERENCE IMAGES ATTACHED (each element has one reference image file):
   - Main Character [CHARACTER REFERENCE] (reference image shows: 28-year-old professional woman, shoulder-length dark brown hair, olive skin, hazel eyes, neutral expression, casual attire - this is her BASE appearance) - USE THIS REFERENCE IMAGE AS BASE AND MODIFY IT TO: weary fatigued expression, squinting eyes, shoulders hunched, grey wool coat damp from rain, NOT wearing sunglasses, holding black leather sunglasses case in right hand
   - Urban City Streets [LOCATION REFERENCE] (reference image shows: grey wet urban street, concrete bus stop shelter, neutral colors, normal atmosphere) - USE THIS REFERENCE IMAGE AS BASE AND MODIFY IT TO: washed-out, desaturated, lifeless, frozen mannequin-like commuters in background
   - SunVue Aviators [PRODUCT REFERENCE] (reference image shows: classic aviator frame in polished gold metal with amber lenses, on neutral background) - Character HOLDING in CLOSED case, NOT visible in frame, NOT wearing
   
   Hyper-realistic photorealistic street photography, character walking through dull city, squinting, clutching sunglasses case, looking tired, documentary style
   ```
   
   **Example - Scene 3 (after transformation):**
   ```
   Modern documentary, medium shot, golden hour, vibrant color grade.
   
   REFERENCE IMAGES CONTEXT:
   You are receiving reference images showing the CANONICAL APPEARANCE of characters, locations, and props from this advertisement universe. These images show how each element looks in its BASE/NEUTRAL state. Your task is to use these as the visual foundation and transform them according to the instructions below to match this specific scene's requirements.
   
   REFERENCE IMAGES ATTACHED (each element has one reference image file):
   - Main Character [CHARACTER REFERENCE] (reference image shows: 28-year-old professional woman, shoulder-length dark brown hair, olive skin, hazel eyes, neutral expression - this is her BASE appearance) - USE THIS REFERENCE IMAGE AS BASE AND MODIFY IT TO: WEARING gold aviators on face, confident posture, relaxed smile, shoulders back, vibrant energy
   - Urban City Streets [LOCATION REFERENCE] (reference image shows: grey wet urban street, neutral colors, normal atmosphere) - USE THIS REFERENCE IMAGE AS BASE AND MODIFY IT TO: saturated vibrant colors, energetic atmosphere, warm golden hour lighting, neon signs glowing
   - SunVue Aviators [PRODUCT REFERENCE] (reference image shows: classic aviator frame in polished gold metal with amber lenses) - Character WEARING on face prominently, frames catching golden light, lenses showing reflections
   
   Hyper-realistic photorealistic street photography, character striding confidently, aviators prominent and catching light, city bursting with color and life, cinematic style
   ```
   
   **MANDATORY REQUIREMENTS - COPY EXACTLY FROM YOUR FIRST TIMESTAMP BLOCK (00:00-00:02):**
   
   When creating first_frame_image_prompt, you MUST:
   1. **Copy the ENTIRE "Style:" from the first timestamp's cinematography** verbatim
   2. **Copy the EXACT "Camera shot:" from the first timestamp's cinematography** - BUT ensure it follows FACE FRAMING requirements below
   3. **Copy the EXACT "Lens & Depth:" from the first timestamp's cinematography**
   4. **Copy the EXACT "Composition:" (Foreground/Midground/Background) from the first timestamp's cinematography**
   5. **Copy the EXACT "Lighting:" (with all directional sources) from the first timestamp's cinematography**
   6. **Copy the EXACT "Mood:" from the first timestamp's cinematography**
   7. **Use the visual description from the first timestamp** as the basis for composition
   8. **Verify FACE FRAMING if character is present:**
      - Use Medium Shot or Medium Close-Up (NOT Wide, NOT Extreme Close-Up)
      - Face should occupy 20-40% of frame height for clear recognition
      - Full face visible: eyes, nose, mouth, chin, forehead all clearly recognizable
   9. **Add REFERENCE IMAGES section** describing what's attached and how to use/modify each element
   10. Include all characters/locations from elements_used clearly visible
   11. Add hyper-realistic, photorealistic style keywords for image generation
   
   **WORKFLOW REMINDER:** Image is generated FIRST, then used as first frame for video. They MUST be stylistically identical or the video will look wrong.
   
   **The first frame image should look like a still frame FROM the first timestamp block (00:00-00:02) - same style, same lighting, same camera, same mood, same composition, same everything.**

6. **elements_used**: List of element names (characters/props/locations) from universe_characters that appear in this scene.
   - Use EXACT names from ALLOWED lists
   - Only include elements that appear in MULTIPLE scenes (2+)
   - These will have their canonical reference images attached to first frame generation
**EXAMPLE OUTPUT STRUCTURE:**

Example 8-second scene with timestamp blocks:
```
video_summary: "Hero discovers and opens SunVue sunglasses case at rainy bus stop, transforming from weary to hopeful"

audio_summary: "Melancholic piano builds from sparse notes to hopeful melody, with rain ambience and discovery sound effects"

visual_effect: {{
  "name": "Freezing",
  "description": "Time freezes as glasses go on—breath becomes visible, motion stops. Perfect for showing the moment everything changes",
  "timing": "6-8 seconds as she discovers the case"
}}

00:00-00:02:
  visual: "Hero/Main Commuter (28-year-old professional woman with shoulder-length dark brown hair, olive skin, grey wool coat damp from rain) stands under concrete bus stop shelter on dreary rainy morning at Urban Street with Bus Stop. She's hunched against drizzle, checking phone with squinting tired eyes, shoulders slumped in weary posture. NOT wearing sunglasses - face fully visible. Worn leather messenger bag visible on shoulder. Cracked sidewalk puddles with glossy surface reflecting overcast sky. Light rain visible as fine droplets in air."
  cinematography: "Camera shot: Medium shot at eye level, subject center-frame. Lens & Depth: 50mm standard lens, f/2.8 shallow depth of field with soft bokeh. Camera motion: Subtle handheld drift forward at 1cm/sec. Composition: Foreground: rain puddles on concrete. Midground: Hero centered under shelter. Background: blurred wet street with dim storefronts. Lighting: Key light: flat overcast daylight from above, even illumination. Fill light: soft bounce from wet pavement. Practical lights: distant streetlamp glow. Style: Modern documentary photography, desaturated grey-blue grade, natural film grain. Mood: Weary and mundane, quietly desperate"
  dialogue: null
  sfx: "phone screen tap, distant car horn"
  ambience: "light rain pattering on concrete shelter, distant traffic hum, puddle ripples"
  music: "minimal melancholic piano notes, 60 BPM, very muted, sparse, single note pattern"

00:02-00:04:
  visual: "Hero/Main Commuter at Urban Street with Bus Stop digs through worn leather messenger bag with frustrated movements, searching urgently. Hands visible rummaging through bag interior, items shifting. Still NOT wearing sunglasses. Expression shows mounting frustration - furrowed brow, slight frown. Grey wool coat sleeve visible as arm reaches into bag. Messenger bag matte leather texture, worn edges. Rain continues falling in background, puddles visible on ground."
  cinematography: "Camera shot: Medium close-up on hands and bag. Lens & Depth: 50mm f/2.8 shallow depth, bag in focus. Camera motion: Handheld subtle shake matching frustration. Composition: Foreground: bag flap edge. Midground: hands searching bag interior. Background: soft grey shelter wall. Lighting: Same flat overcast, bag interior slightly darker. Style: Continues documentary aesthetic. Mood: Mounting frustration and urgency"
  dialogue: "Hero/Main Commuter: [soft sigh of frustration]"
  sfx: "bag zipper sound, leather rustling, items clinking inside bag"
  ambience: "rain continues steady, bus engine approaching in far distance"
  music: "piano adds second note creating tension, dynamics lift slightly, duck under dialogue"

00:04-00:06:
  visual: "Hero/Main Commuter at bus stop discovers sleek SunVue Sunglasses Case (matte black leather with embossed logo) in messenger bag, pauses in surprise. Hand holds case against bag interior, fingers touching embossed SunVue logo with curiosity. Expression shifts from frustration to surprise - eyes widen slightly, eyebrows raise. Still NOT wearing sunglasses. Case surface catching slight overhead light with subtle sheen. Bag interior fabric texture visible in matte grey tones."
  cinematography: "Camera shot: Insert close-up of case in hand against bag. Lens & Depth: 85mm portrait lens f/2.8 for intimacy. Camera motion: Push-in slowly to case at 1cm/sec. Composition: Foreground: bag fabric texture. Midground: case prominent in hand. Background: soft grey blur. Lighting: Key light: slight highlight catching case surface from above. Style: Documentary with hint of warmth emerging. Mood: Surprise shifting to curiosity"
  dialogue: "Hero/Main Commuter: [curious 'hmm?']"
  sfx: "subtle leather case texture sound as fingers trace logo, discovery moment silence"
  ambience: "rain softens slightly, bus engine fades"
  music: "piano adds hopeful third note, tempo unchanged, dynamics lift creating optimism, duck under dialogue"

00:06-00:08:
  visual: "Hero/Main Commuter at Urban Street with Bus Stop holds SunVue case up examining it with growing curiosity, bringing it closer to eye level. Hint of smile forming on face - corners of mouth lifting, eyes showing interest. Hand beginning to open case clasp (motion transitions toward next scene). Still NOT wearing sunglasses - full face visible showing emotion shift from weary to hopeful. Case prominent in frame, logo clearly visible. Grey wool coat shoulder visible, rain-dampened. Background shows wet street and shelter softening with emerging warmth in light."
  cinematography: "Camera shot: Medium shot returning to Hero's face with case. Lens & Depth: 50mm f/2.8 keeping face sharp. Camera motion: Slight drift up following case movement. Composition: Foreground: case edge entering frame. Midground: Hero's face showing emotion shift. Background: shelter and street softening. Lighting: Slight warmth beginning to emerge in highlights. Style: Documentary with emerging hope. Mood: Curiosity and emerging confidence"
  dialogue: null
  sfx: "case being raised through air, subtle fabric rustle from coat movement, case clasp beginning to click (sets up next scene)"
  ambience: "rain ambient continues steady, distant footsteps of approaching commuter"
  music: "piano melody completes hopeful phrase but sustains final note, preparing smooth transition to next scene, no hard stop"
```

**OUTPUT FORMAT (JSON):**
```json
{{
  "scenes": [
    {{
      "scene_number": 1,
      "duration_seconds": {scene_duration},
      "video_summary": "One-sentence overview of what happens in this scene",
      "audio_summary": "One-sentence description of the audio journey",
      "visual_effect": {{
        "name": "Effect Name from Library",
        "description": "Full description from library",
        "timing": "When it occurs (e.g., '6-8 seconds')"
      }} or null,
      "00:00-00:02": {{
        "visual": "Complete self-contained visual description: WHO (character with key appearance), WHERE (location/setting), WHAT ACTION (specific action), WHAT OBJECTS/PRODUCTS (especially eyewear - worn/held/visible?), HOW (expressions/emotions/body language), plus material surfaces, atmospheric particles, environmental motion as needed",
        "cinematography": "Complete cinematography: Camera shot, Lens & Depth, Camera motion, Composition (Foreground/Midground/Background), Lighting (Key/Fill/Rim/Practical with directions), Style, Mood",
        "dialogue": "Character Name: [dialogue]" or "Narrator (voice): [text]" or null,
        "sfx": "sound effect 1, sound effect 2, sound effect 3",
        "ambience": "ambient sound description for this segment",
        "music": "music description with instrumentation, tempo, dynamics, evolution"
      }},
      "00:02-00:04": {{
        "visual": "...",
        "cinematography": "...",
        "dialogue": "..." or null,
        "sfx": "...",
        "ambience": "...",
        "music": "..."
      }},
      "00:04-00:06": {{
        "visual": "...",
        "cinematography": "...",
        "dialogue": "..." or null,
        "sfx": "...",
        "ambience": "...",
        "music": "..."
      }},
      "00:06-00:08": {{
        "visual": "...",
        "cinematography": "...",
        "dialogue": "..." or null,
        "sfx": "...",
        "ambience": "...",
        "music": "..."
      }},
      "first_frame_image_prompt": "[Copy style/camera/lens/composition/lighting/mood from 00:00-00:02 cinematography]\n\nREFERENCE IMAGES ATTACHED (image files provided as input - use each as base and modify as instructed):\n- Element Name 1 (reference image shows: canonical state) - USE THIS REFERENCE IMAGE AS-IS / AS BASE AND MODIFY TO: [...]\n- Element Name 2 (reference image shows: canonical state) - USE THIS REFERENCE IMAGE AS-IS / AS BASE AND MODIFY TO: [...]\n\n[Hyper-realistic photorealistic composition matching first timestamp visual]",
      "elements_used": ["Element Name 1", "Element Name 2"]
    }}
  ]
}}
```

**CRITICAL NOTES:**
- For an 8-second scene, you will have 4 timestamp blocks: 00:00-00:02, 00:02-00:04, 00:04-00:06, 00:06-00:08
- For a 6-second scene: 3 blocks (00:00-00:02, 00:02-00:04, 00:04-00:06)
- For a 4-second scene: 2 blocks (00:00-00:02, 00:02-00:04)
- Each timestamp must have ALL six fields: visual, cinematography, dialogue, sfx, ambience, music
- visual_effect is SINGULAR - pick the ONE most suitable effect, or null if none fit
- Audio must transition smoothly between scenes - last timestamp should set up next scene's audio
"""
    print(f"  ✓ Prompt built ({len(prompt)} chars)")
    
    print(f"[{time.strftime('%H:%M:%S')}] [Step 7/7] Calling LLM to generate scene prompts...")
    provider, model_name = model.split("/", 1) if "/" in model else ("anthropic", model)
    api_key = get_api_key(provider)
    
    # Define JSON schema for structured output (OpenAI)
    # Note: Timestamp blocks (00:00-00:02, etc.) are dynamic based on scene_duration,
    # so we use additionalProperties to allow them
    
    timestamp_block_schema = {
        "type": "object",
        "properties": {
            "visual": {"type": "string"},
            "cinematography": {"type": "string"},
            "dialogue": {"type": ["string", "null"]},
            "sfx": {"type": "string"},
            "ambience": {"type": "string"},
            "music": {"type": "string"}
        },
        "required": ["visual", "cinematography", "dialogue", "sfx", "ambience", "music"]
    }
    
    scene_properties = {
        "scene_number": {"type": "integer"},
        "duration_seconds": {"type": "integer"},
        "video_summary": {"type": "string"},
        "audio_summary": {"type": "string"},
        "first_frame_image_prompt": {"type": "string"},
        "elements_used": {
            "type": "array",
            "items": {"type": "string"}
        }
    }
    
    # Add visual_effect to schema (singular, nullable)
    if enable_visual_effects:
        scene_properties["visual_effect"] = {
            "type": ["object", "null"],
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "timing": {"type": "string"}
                },
                "required": ["name", "description", "timing"]
        }
    
    # Scene schema - additionalProperties=True to allow dynamic timestamp keys
    scene_schema = {
        "type": "object",
        "properties": {
            "scenes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": scene_properties,
                    "required": ["scene_number", "duration_seconds", "video_summary", "audio_summary", "first_frame_image_prompt", "elements_used"],
                    "additionalProperties": True  # Allow timestamp blocks like "00:00-00:02"
                }
            }
        },
        "required": ["scenes"]
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
        # Claude: Direct API call (NO CACHING)
        print(f"  → Calling Anthropic API (no caching)...")
        thinking_value = thinking if thinking and thinking > 0 else None
        response = call_anthropic_with_caching(
            prompt, model_name, api_key, 
            thinking=thinking_value, 
            max_tokens=17000,  # Total: thinking (5000) + response (12000)
            temperature=temperature
        )
    llm_end_time = time.time()
    llm_duration = llm_end_time - llm_start_time
    
    print(f"  ✓ LLM response received ({len(response)} chars)", flush=True)
    print(f"  ⏱️  Pure LLM API call time: {llm_duration:.1f} seconds ({llm_duration/60:.1f} minutes)", flush=True)
    
    # ALWAYS save raw response for debugging
    debug_dir = Path(__file__).parent.parent / "outputs" / "debug"
    debug_dir.mkdir(parents=True, exist_ok=True)
    raw_response_file = debug_dir / f"raw_response_{int(time.time())}.txt"
    with open(raw_response_file, 'w', encoding='utf-8') as f:
        f.write(response)
    print(f"  → Raw response saved to: {raw_response_file}", flush=True)
    
    print(f"  → Parsing JSON from response...", flush=True)
    
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
    
    print(f"  → Loading JSON...", flush=True)
    try:
        result = json.loads(json_text)
        print(f"  ✓ JSON loaded successfully", flush=True)
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
    
    print(f"  ✓ JSON parsed successfully - {len(result.get('scenes', []))} scenes generated", flush=True)
    
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
    
    # Extract batch folder from path
    # Path structure can be either:
    #   .../batch_folder/concept_name/concept_name_revised.txt (pipeline structure)
    #   .../batch_folder/concept_name_revised.txt (Step 0 structure)
    # Check if parent's name matches concept_name (pipeline structure)
    if input_path.parent.name == concept_name:
        # Pipeline structure: batch_folder is parent's parent
        batch_folder = input_path.parent.parent.name
        concept_dir = input_path.parent
    else:
        # Step 0 structure: batch_folder is parent
        batch_folder = input_path.parent.name
        concept_dir = input_path.parent
    
    # Extract brand name from concept name (first part before first underscore)
    brand_name = concept_name.split("_")[0] if "_" in concept_name else "unknown"
    
    # Construct all paths automatically (matching pipeline structure exactly)
    args.concept = str(input_path)
    
    # Try both concept_name and concept_name_revised for universe path
    universe_base = concept_name
    universe_revised = f"{concept_name}_revised"
    universe_path_base = BASE_DIR / "s5_generate_universe" / "outputs" / batch_folder / universe_base / f"{universe_base}_universe_characters.json"
    universe_path_revised = BASE_DIR / "s5_generate_universe" / "outputs" / batch_folder / universe_revised / f"{universe_revised}_universe_characters.json"
    if universe_path_revised.exists():
        args.universe = str(universe_path_revised)
    elif universe_path_base.exists():
        args.universe = str(universe_path_base)
    else:
        args.universe = str(universe_path_base)  # Will fail with clear error
    
    # Try brand-specific config first, then fallback to sunglasses.json
    config_brand = BASE_DIR / "s1_generate_concepts" / "inputs" / "configs" / f"{brand_name}.json"
    config_sunglasses = BASE_DIR / "s1_generate_concepts" / "inputs" / "configs" / "sunglasses.json"
    if config_brand.exists():
        args.config = str(config_brand)
    elif config_sunglasses.exists():
        args.config = str(config_sunglasses)
    else:
        args.config = str(config_brand)  # Will fail with clear error
    
    # Try both concept_name and concept_name_revised for image summary
    image_summary_base = BASE_DIR / "s6_generate_reference_images" / "outputs" / batch_folder / universe_base / "image_generation_summary.json"
    image_summary_revised = BASE_DIR / "s6_generate_reference_images" / "outputs" / batch_folder / universe_revised / "image_generation_summary.json"
    if image_summary_revised.exists():
        args.image_summary = str(image_summary_revised)
    elif image_summary_base.exists():
        args.image_summary = str(image_summary_base)
    else:
        args.image_summary = None
    
    # Output uses same folder name as universe (could be concept_name or concept_name_revised)
    output_folder = universe_revised if universe_path_revised.exists() else universe_base
    args.output = str(BASE_DIR / "s7_generate_scene_prompts" / "outputs" / batch_folder / output_folder / f"{output_folder}_scene_prompts.json")
    
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
    
    # Generate (with thinking enabled - saving response for debugging)
    result = generate_scene_prompts(
        concept_content,
        universe_chars,
        config_data,
        duration=args.duration,
        model=args.model,
        resolution=args.resolution,
        image_summary_path=image_summary_path,
        thinking=2500  # ENABLED to debug the hang issue
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

