#!/usr/bin/env python3
"""
Video Script Generator
Extracts best-scoring concept from evaluation, revises it, and generates video production assets.
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import os
from execute_llm import call_openai, call_anthropic

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


def load_evaluation_json(evaluation_path):
    """Load evaluation JSON and find best scoring concept."""
    with open(evaluation_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    best_concept = None
    best_score = -1
    
    for eval_group in data.get("evaluations", []):
        for eval_item in eval_group.get("evaluations", []):
            score = eval_item.get("score", 0)
            if score > best_score:
                best_score = score
                best_concept = eval_item
    
    if not best_concept:
        raise ValueError("No concepts found in evaluation file")
    
    return best_concept, best_score


def load_concept_file(file_path):
    """Load concept file content."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read()


def load_config_file(config_path):
    """Load config JSON file."""
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def revise_script_for_video(concept_content, config, model="anthropic/claude-sonnet-4-5-20250929", duration=30):
    """Revise script to ensure it can be rendered in specified duration (minor edits only)."""
    
    prompt = f"""You are a video production expert. Review this 5-scene ad concept and make MINOR edits ONLY if needed to ensure it can be rendered in {duration} seconds (approximately {duration//5} seconds per scene, ±3 seconds).

**BRAND CONTEXT:**
- Brand: {config.get('BRAND_NAME', 'N/A')}
- Product: {config.get('PRODUCT_DESCRIPTION', 'N/A')}
- Tagline: {config.get('TAGLINE', 'N/A')}

**ORIGINAL CONCEPT:**
{concept_content}

**INSTRUCTIONS:**
1. Keep the core story, characters, and narrative arc EXACTLY the same
2. Only make MINOR edits if scenes are too complex or too long for {duration//5} seconds each
3. Simplify descriptions ONLY if absolutely necessary for timing
4. Maintain all key story beats and brand integration
5. If no changes needed, return the original concept as-is

**OUTPUT FORMAT:**
Return the revised 5-scene concept in the EXACT same format as the input, with only minor timing/clarity adjustments if needed.

If no changes are needed, return the original concept unchanged.

After the 5 scenes, add a section "**STANDOUT ELEMENTS:**" with 1-2 sentences describing what is particularly standout, memorable, or compelling about this concept."""
    
    provider, model_name = model.split("/", 1) if "/" in model else ("anthropic", model)
    api_key = get_api_key(provider)
    
    if provider == "openai":
        revised = call_openai(prompt, model_name, api_key, reasoning_effort="high")
    else:
        revised = call_anthropic(prompt, model_name, api_key, thinking=10000)
    
    return revised


def generate_universe_and_characters(revised_script, config, model="anthropic/claude-sonnet-4-5-20250929"):
    """Generate universe (props, locations) and character descriptions for consistency across scenes."""
    
    prompt = f"""You are a video production designer. Analyze this 5-scene ad concept and create detailed descriptions for:
1. **UNIVERSE**: All props, locations, and environmental elements that appear across multiple scenes
2. **CHARACTERS**: All characters with detailed descriptions for visual consistency

**BRAND CONTEXT:**
- Brand: {config.get('BRAND_NAME', 'N/A')}
- Product: {config.get('PRODUCT_DESCRIPTION', 'N/A')}
- Creative Direction: {config.get('CREATIVE_DIRECTION', 'N/A')}

**5-SCENE CONCEPT:**
{revised_script}

**INSTRUCTIONS:**
1. Identify ONLY props/objects that appear in MULTIPLE scenes (2 or more) - these need consistency tracking
2. Identify ONLY locations that appear in MULTIPLE scenes (2 or more) - these need consistency tracking
3. Identify ALL characters with detailed physical descriptions (age, appearance, clothing, distinctive features) - characters need consistency even if only in one scene
4. **CRITICAL**: If an element has MULTIPLE VERSIONS/STATES (e.g., abandoned location → transformed location, young character → old character, early appearance → later appearance), create separate versions with image generation prompts for EACH
5. For transformed/evolved versions, include a reference to the original version (for image editing workflows)
6. Each description should be vivid and detailed enough to use directly in AI image/video generation prompts
7. DO NOT include props or locations that only appear in a single scene - the video generation model will create those fresh each time
8. Focus on elements that need visual consistency ACROSS multiple scenes

**OUTPUT FORMAT (JSON):**
```json
{{
  "universe": {{
    "locations": [
      {{
        "name": "Location Name",
        "scenes_used": [1, 2, 3],
        "has_multiple_versions": true,
        "versions": [
          {{
            "version_name": "Original/Abandoned/Early",
            "scenes_used": [1],
            "description": "Detailed visual description for this version",
            "image_generation_prompt": "Complete prompt for generating reference image of this version (for nano/banan image generation)",
            "is_original": true
          }},
          {{
            "version_name": "Transformed/Restored/Later",
            "scenes_used": [4, 5],
            "description": "Detailed visual description for this transformed version",
            "image_generation_prompt": "Complete prompt for generating reference image of this version (for nano/banan image generation)",
            "is_original": false,
            "references_original_version": "Original/Abandoned/Early"
          }}
        ]
      }}
    ],
    "props": [
      {{
        "name": "Prop Name",
        "scenes_used": [1, 2, 3],
        "has_multiple_versions": false,
        "description": "Detailed visual description for AI generation",
        "image_generation_prompt": "Complete prompt for generating reference image (for nano/banan image generation)"
      }}
    ]
  }},
  "characters": [
    {{
      "name": "Character Name",
      "scenes_used": [1, 2, 3, 4, 5],
      "has_multiple_versions": true,
      "versions": [
        {{
          "version_name": "Early Appearance",
          "scenes_used": [1, 2, 3],
          "description": "Detailed physical description for early scenes",
          "image_generation_prompt": "Complete prompt for generating reference image of this character version (for nano/banan image generation)",
          "is_original": true
        }},
        {{
          "version_name": "Later Appearance",
          "scenes_used": [4, 5],
          "description": "Detailed physical description for later scenes",
          "image_generation_prompt": "Complete prompt for generating reference image of this character version (for nano/banan image generation)",
          "is_original": false,
          "references_original_version": "Early Appearance"
        }}
      ]
    }}
  ]
}}
```

**IMPORTANT NOTES:**
- If an element has only ONE version/state across all scenes, use the simple format (no "versions" array, just "description" and "image_generation_prompt")
- If an element has MULTIPLE versions, use the "versions" array format
- "image_generation_prompt" should be a complete, detailed prompt ready to feed into image generation models (nano-banana, etc.)
- For transformed versions, "references_original_version" should match the "version_name" of the original version
- **CRITICAL: Image prompts must generate HYPER-REALISTIC, PHOTOREALISTIC images that look like real people/photographs**
- Include these realism keywords in every image_generation_prompt: "hyper-realistic", "photorealistic", "ultra-realistic", "lifelike", "documentary photography style", "real person", "authentic", "natural skin texture", "realistic lighting", "professional portrait photography"
- **CRITICAL FOR GROUPS**: If describing a group with diversity requirements (e.g., "diverse ethnicities", "2 white, 1 Black, 1 Hispanic"), make diversity the FIRST and MOST PROMINENT part of the prompt. Explicitly describe each person's ethnicity, skin tone, and distinctive features. Example: "Group of 4 chefs: Chef 1 - White male with light skin tone and European features, Chef 2 - Black male with dark brown skin and African features, Chef 3 - Hispanic male with medium olive skin and Latin American features, Chef 4 - White male with light skin and European features. Each person clearly distinguishable with distinct ethnic features and skin tones."
- Image prompts should include all visual details: lighting, composition, style, specific features, colors, textures, skin details, hair texture, clothing fabric details, etc.
- Avoid any stylized, artistic, or cartoon-like descriptions - focus on photographic realism"""
    
    provider, model_name = model.split("/", 1) if "/" in model else ("anthropic", model)
    api_key = get_api_key(provider)
    
    if provider == "openai":
        response = call_openai(prompt, model_name, api_key, reasoning_effort="high")
    else:
        response = call_anthropic(prompt, model_name, api_key, thinking=10000)
    
    # Extract JSON from response
    if "```json" in response:
        json_text = response.split("```json")[1].split("```")[0].strip()
    elif "```" in response:
        json_text = response.split("```")[1].split("```")[0].strip()
    else:
        json_text = response.strip()
    
    return json.loads(json_text)


def generate_scene_prompts(revised_script, universe_chars, config, duration=30, model="anthropic/claude-sonnet-4-5-20250929", resolution="480p", image_summary_path=None):
    """Generate detailed video generation prompts for each scene."""
    
    scene_duration = duration // 5
    
    # Determine aspect ratio from resolution
    aspect_ratio = "16:9"  # Default for 480p/1080p
    
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
        except Exception as e:
            print(f"  ⚠ Could not load image_generation_summary.json: {e}")
    
    # Build allowed names list - use image summary names if available, otherwise universe names
    def get_display_name(original_name):
        return image_element_names.get(original_name, original_name)
    
    allowed_char_names = [get_display_name(char.get('name')) for char in universe_chars.get('characters', [])]
    allowed_loc_names = [get_display_name(loc.get('name')) for loc in universe_chars.get('universe', {}).get('locations', [])]
    allowed_prop_names = [get_display_name(prop.get('name')) for prop in universe_chars.get('universe', {}).get('props', [])]
    
    prompt = f"""You are a professional video director creating prompts for AI video generation (Veo 3.1, Sora 2, Seedance-1-pro).

**BRAND CONTEXT:**
- Brand: {config.get('BRAND_NAME', 'N/A')}
- Product: {config.get('PRODUCT_DESCRIPTION', 'N/A')}
- Tagline: {config.get('TAGLINE', 'N/A')}
- Creative Direction: {config.get('CREATIVE_DIRECTION', 'N/A')}

**5-SCENE CONCEPT:**
{revised_script}

**UNIVERSE & CHARACTERS:**
{json.dumps(universe_chars, indent=2)}

**CRITICAL: EXACT ELEMENT NAMES TO USE**
You MUST use the EXACT names from the universe_characters.json above. Do NOT create new names or variations.
**IMPORTANT**: If an element name in universe_characters.json has a plural/singular variation (e.g., "Young Chef Group" vs "Young Chefs Group"), you MUST use the EXACT spelling as shown in universe_characters.json above, including any plural/singular differences. Do NOT add or remove 's' from names.

**ALLOWED CHARACTER NAMES** (use EXACTLY as shown - these are the names that have reference images):
{chr(10).join([f"- {name}" for name in allowed_char_names])}

**ALLOWED LOCATION NAMES** (use EXACTLY as shown - these are the names that have reference images):
{chr(10).join([f"- {name}" for name in allowed_loc_names])}

**ALLOWED PROP NAMES** (use EXACTLY as shown - these are the names that have reference images):
{chr(10).join([f"- {name}" for name in allowed_prop_names])}

**VIDEO SPECIFICATIONS:**
- Resolution: {resolution}
- Aspect Ratio: {aspect_ratio}
- Scene Duration: {scene_duration} seconds (±3 seconds)

**INSTRUCTIONS:**
For EACH of the 5 scenes, create:

1. **video_prompt**: Complete prompt for video generation that MUST include:
   - **Shot Type**: Specific camera shot (close-up, medium shot, wide shot, etc.)
   - **Subject**: Main subject(s) in the frame
   - **Action**: What is happening, character movements, expressions
   - **Setting**: Location and environment details
   - **Lighting**: Lighting conditions, mood, time of day
   - Reference characters/locations by NAME only (e.g., "Master Chef", "Restaurant Location")
   - Reference full descriptions from universe_characters.json
   - Keep concise but complete for the video model

2. **audio_background**: Detailed background music prompt for ElevenLabs/Suno (genre, mood, tempo, instruments, energy level)

3. **audio_dialogue**: Compelling, evocative dialogue that characters say in this scene, OR narrator voiceover. **CRITICAL FORMAT**: 
   - **For character dialogue**: Use format "Character Name: [dialogue text]". Use the EXACT character name from universe_characters.json (e.g., "Main Chef (Protagonist): Ma, one day this place will smell like your kitchen again.")
   - **For narrator/voiceover**: Use format "Narrator (voice characteristics): [dialogue text]". Voice characteristics must include: tone (sad, hopeful, determined, warm, authoritative, gentle, etc.), emotion (emotional, nostalgic, contemplative, etc.), and style (warm, deep, soft, etc.). Example: "Narrator (sad, emotional, warm, contemplative voice): The journey begins with a single promise."
   - Make dialogue authentic, sensory-rich, and poetic when appropriate. Use vivid imagery, specific details, and memorable phrasing. Match the brand's tone and creative direction.
   - **PRIORITIZE dialogue in scenes with multiple characters, key story moments, or when dialogue would enhance the narrative impact.**
   - Only use null if the scene truly requires silence (e.g., contemplative solo moments, pure visual storytelling).
   - Dialogue can be 10-15 words - make every word count. Aim for lines that are quotable, memorable, and emotionally resonant.

4. **first_frame_image_prompt**: Complete, detailed image generation prompt for the first frame. This should be:
   - Hyper-realistic, photorealistic style
   - Include all characters and locations from elements_used
   - Match the resolution ({resolution}) and aspect ratio ({aspect_ratio})
   - Include specific details: camera settings, lighting, composition, character positions, expressions
   - Ready to feed into image generation models (nano-banana, etc.)
   - Must ensure all reference characters/locations are clearly visible and identifiable

5. **elements_used**: List which characters, props, and locations from universe/characters are in this scene.
   **CRITICAL**: 
   - You MUST use the EXACT names from the "ALLOWED" lists above. Copy the names EXACTLY as shown (including parentheses, capitalization, etc.).
   - **ONLY include elements that appear in MULTIPLE scenes** (check the "scenes_used" array in the universe_characters.json above)
   - Do NOT include elements that appear in only ONE scene (they don't need reference images for consistency)
   - For characters: Use EXACT names from "ALLOWED CHARACTER NAMES" above, but only if scenes_used has 2+ scene numbers
   - For locations: Use EXACT names from "ALLOWED LOCATION NAMES" above, but only if scenes_used has 2+ scene numbers
   - For props: Use EXACT names from "ALLOWED PROP NAMES" above, but only if scenes_used has 2+ scene numbers
   - **IF an element has MULTIPLE VERSIONS** (check "has_multiple_versions" and "versions" array in universe_characters.json), you MUST include the version name in the format: "Element Name - Version Name"
   - Example: If a character has versions "Early Version" (scenes 1,2,3) and "Later Version" (scenes 4,5), and this is scene 2, write: "Character Name - Early Version"
   - Example: If a location has versions "Abandoned" (scene 1) and "Restored" (scene 4), and this is scene 4, write: "Location Name - Restored"
   - Example: If an element has NO multiple versions (has_multiple_versions: false), just write the base name: "Prop Name"
   - Do NOT create variations, abbreviations, or simplified names
   - Check the "scenes_used" array for each version to determine which version is used in THIS scene number

**CRITICAL**: 
- The first_frame_image_prompt must generate an image that includes ALL characters and locations from elements_used
- This first frame image will be used as a reference input for video generation (passed to nano-banana with character/location reference images)
- video_prompt must explicitly include: shot type, subject, action, setting, and lighting
- Choose shot types, lighting, and composition that best serve the overall storyline
- In video_prompt and first_frame_image_prompt, you can reference characters by their full name or a shorter descriptive name, but in elements_used you MUST use the EXACT name from the allowed lists

**OUTPUT FORMAT (JSON):**
```json
{{
  "scenes": [
    {{
      "scene_number": 1,
      "duration_seconds": {scene_duration},
      "video_prompt": "Complete prompt with shot type, subject, action, setting, lighting. Reference characters/locations by name only.",
      "audio_background": "Detailed music prompt for ElevenLabs/Suno (genre, mood, tempo, instruments, energy level)",
      "audio_dialogue": "Character Name: [dialogue text] OR Narrator (voice characteristics): [dialogue text] OR null",
      "first_frame_image_prompt": "Complete hyper-realistic image generation prompt for first frame, matching {resolution} {aspect_ratio}, with all characters/locations visible. Must include shot type, all characters visible, setting, lighting, composition. Ready to feed into nano-banana with reference images.",
      "elements_used": {{
        "characters": ["EXACT Character Name from ALLOWED list above, or 'Character Name - Version Name' if multiple versions"],
        "locations": ["EXACT Location Name from ALLOWED list above, or 'Location Name - Version Name' if multiple versions"],
        "props": ["EXACT Prop Name from ALLOWED list above, or 'Prop Name - Version Name' if multiple versions"]
      }}
    }}
  ]
}}
```"""
    
    provider, model_name = model.split("/", 1) if "/" in model else ("anthropic", model)
    api_key = get_api_key(provider)
    
    if provider == "openai":
        response = call_openai(prompt, model_name, api_key, reasoning_effort="high")
    else:
        response = call_anthropic(prompt, model_name, api_key, thinking=10000)
    
    # Extract JSON from response
    if "```json" in response:
        json_text = response.split("```json")[1].split("```")[0].strip()
    elif "```" in response:
        json_text = response.split("```")[1].split("```")[0].strip()
    else:
        json_text = response.strip()
    
    return json.loads(json_text)


def generate_video_script(evaluation_path, output_base_dir="script_generation", 
                          revision_model="anthropic/claude-sonnet-4-5-20250929",
                          duration=30):
    """
    Main function: Extract best concept, revise, and generate video production assets.
    """
    print(f"\n{'='*80}")
    print("VIDEO SCRIPT GENERATOR")
    print(f"{'='*80}\n")
    
    # Step 1: Load evaluation and find best concept
    print("Step 1: Extracting best-scoring concept from evaluation...")
    best_concept, best_score = load_evaluation_json(evaluation_path)
    concept_file = best_concept.get("file")
    brand_name = best_concept.get("model", "").split("-")[0] if "-" in best_concept.get("model", "") else "unknown"
    
    print(f"  ✓ Best score: {best_score}/100")
    print(f"  ✓ Concept file: {concept_file}")
    print(f"  ✓ Model: {best_concept.get('model')} | Template: {best_concept.get('template')}")
    
    # Load concept content
    concept_content = load_concept_file(concept_file)
    
    # Find corresponding config file
    # Extract batch folder from concept file path
    concept_path = Path(concept_file)
    batch_folder = concept_path.parent.name  # e.g., "rolex_1115_1833"
    
    # Find config file in prompts_history/{batch_folder}/configs/
    config_dir = Path("prompts_history") / batch_folder / "configs"
    if not config_dir.exists():
        raise FileNotFoundError(f"Config directory not found: {config_dir}")
    
    # Find config file matching the concept filename prefix
    concept_stem = concept_path.stem  # e.g., "rolex_achievement_inspirational_advanced_claude_sonnet_4.5"
    # Extract prefix before template/model (e.g., "rolex_achievement_inspirational")
    parts = concept_stem.split("_")
    # Find where template name appears (advanced/generic)
    template_idx = None
    for i, part in enumerate(parts):
        if part in ["advanced", "generic"]:
            template_idx = i
            break
    
    if template_idx:
        prefix = "_".join(parts[:template_idx])  # e.g., "rolex_achievement_inspirational"
    else:
        prefix = "_".join(parts[:-2])  # Fallback
    
    config_file = config_dir / f"{prefix}.json"
    
    if not config_file.exists():
        raise FileNotFoundError(f"Config file not found: {config_file}")
    
    print(f"  ✓ Config file: {config_file}")
    config = load_config_file(config_file)
    
    # Create output directory structure
    output_dir = Path(output_base_dir) / batch_folder / concept_path.stem
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"\nOutput directory: {output_dir}\n")
    
    # Step 2: Revise script
    print("Step 2: Revising script for video generation (minor edits only)...")
    revised_script = revise_script_for_video(concept_content, config, revision_model, duration)
    
    revised_file = output_dir / f"{concept_path.stem}_revised.txt"
    with open(revised_file, 'w', encoding='utf-8') as f:
        f.write(revised_script)
    print(f"  ✓ Saved: {revised_file}")
    
    # Step 3: Generate universe and characters
    print("\nStep 3: Generating universe (props, locations) and character descriptions...")
    universe_chars = generate_universe_and_characters(revised_script, config, revision_model)
    
    universe_file = output_dir / f"{concept_path.stem}_universe_characters.json"
    with open(universe_file, 'w', encoding='utf-8') as f:
        json.dump(universe_chars, f, indent=2)
    print(f"  ✓ Saved: {universe_file}")
    
    # Step 4: Generate scene prompts
    print("\nStep 4: Generating detailed video generation prompts for each scene...")
    # Try to find image_generation_summary.json to use actual element names that have images
    image_summary_path = None
    universe_images_dir = Path("universe_characters") / concept_path.stem.replace("_scene_prompts", "").replace("_universe_characters", "")
    potential_summary = universe_images_dir / "image_generation_summary.json"
    if potential_summary.exists():
        image_summary_path = str(potential_summary)
        print(f"  ✓ Found image generation summary - will use actual element names from images")
    scene_prompts = generate_scene_prompts(revised_script, universe_chars, config, duration, revision_model, resolution="480p", image_summary_path=image_summary_path)
    
    scenes_file = output_dir / f"{concept_path.stem}_scene_prompts.json"
    with open(scenes_file, 'w', encoding='utf-8') as f:
        json.dump(scene_prompts, f, indent=2)
    print(f"  ✓ Saved: {scenes_file}")
    
    # Create summary
    summary = {
        "source_evaluation": str(evaluation_path),
        "source_concept": concept_file,
        "source_config": str(config_file),
        "best_score": best_score,
        "model": best_concept.get("model"),
        "template": best_concept.get("template"),
        "duration_seconds": duration,
        "output_files": {
            "revised_script": str(revised_file),
            "universe_characters": str(universe_file),
            "scene_prompts": str(scenes_file)
        },
        "generated_at": datetime.now().isoformat()
    }
    
    summary_file = output_dir / f"{concept_path.stem}_summary.json"
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2)
    print(f"  ✓ Saved: {summary_file}")
    
    print(f"\n{'='*80}")
    print("VIDEO SCRIPT GENERATION COMPLETE")
    print(f"{'='*80}")
    print(f"Output directory: {output_dir}")
    print(f"Files generated:")
    print(f"  - Revised script: {revised_file.name}")
    print(f"  - Universe/Characters: {universe_file.name}")
    print(f"  - Scene prompts: {scenes_file.name}")
    print(f"  - Summary: {summary_file.name}")
    print(f"{'='*80}\n")
    
    return output_dir


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python generate_video_script.py <evaluation_json> [duration] [model]")
        print("\nExample:")
        print("  python generate_video_script.py evaluations/rolex_evaluation_claude_4.5_1115_1848.json")
        print("  python generate_video_script.py evaluations/rolex_evaluation_claude_4.5_1115_1848.json 30")
        print("  python generate_video_script.py evaluations/rolex_evaluation_claude_4.5_1115_1848.json 30 openai/gpt-5.1")
        sys.exit(1)
    
    evaluation_path = sys.argv[1]
    duration = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    model = sys.argv[3] if len(sys.argv) > 3 else "anthropic/claude-sonnet-4-5-20250929"
    
    if not os.path.exists(evaluation_path):
        print(f"Error: Evaluation file not found: {evaluation_path}")
        sys.exit(1)
    
    generate_video_script(evaluation_path, duration=duration, revision_model=model)

