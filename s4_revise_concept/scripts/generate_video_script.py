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

# Add path for imports
BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR / "s1_generate_concepts" / "scripts"))

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

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
    best_ad_style = None
    best_brand_name = None
    
    # Get brand name from summary
    brand_name = data.get("summary", {}).get("brand", "")
    
    for eval_group in data.get("evaluations", []):
        ad_style = eval_group.get("ad_style", "")
        group_brand = eval_group.get("brand_name", brand_name)
        for eval_item in eval_group.get("evaluations", []):
            score = eval_item.get("score", 0)
            if score > best_score:
                best_score = score
                best_concept = eval_item.copy()  # Make a copy to avoid modifying original
                best_ad_style = ad_style
                best_brand_name = group_brand
    
    if not best_concept:
        raise ValueError("No concepts found in evaluation file")
    
    # Add metadata to best_concept if not already present
    if best_ad_style and "ad_style" not in best_concept:
        best_concept["ad_style"] = best_ad_style
    if best_brand_name and "brand_name" not in best_concept:
        best_concept["brand_name"] = best_brand_name
    
    return best_concept, best_score


def load_concept_file(file_path):
    """Load concept file content."""
    # Handle old paths (results/) and new paths (s1_generate_concepts/outputs/)
    if not os.path.exists(file_path):
        # Try updating old path to new path
        if file_path.startswith("results/"):
            new_path = file_path.replace("results/", "s1_generate_concepts/outputs/", 1)
            if os.path.exists(new_path):
                file_path = new_path
    
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read()


def load_config_file(config_path):
    """Load config JSON file."""
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def revise_script_for_video(concept_content, config, model="anthropic/claude-sonnet-4-5-20250929", duration=30, weaknesses=None):
    """Revise concept based on judge feedback and ensure it can be rendered in specified duration."""
    
    weaknesses_section = ""
    if weaknesses and len(weaknesses) > 0:
        weaknesses_list = "\n".join([f"{i+1}. {w}" for i, w in enumerate(weaknesses)])
        weaknesses_section = f"""

**JUDGE FEEDBACK - WEAKNESSES TO ADDRESS:**
{weaknesses_list}

**YOUR TASK:** Address the identified weaknesses with AS FEW CHANGES AS POSSIBLE.

**CRITICAL PRINCIPLE:**
The MORE changes you make, the MORE risk you introduce NEW weaknesses. Be surgical, not radical.

**YOUR APPROACH:**
1. Analyze each weakness - what's the MINIMUM change needed to fix it?
2. Preserve everything that's working (the strengths)
3. Only modify what's necessary to address the specific issues raised
4. Ask yourself: "Will this change introduce new problems?"
5. If a weakness requires major changes to fix, consider whether it's worth the risk

**REMEMBER:**
- The original concept scored well, so most of it is working
- Don't reinvent the concept unless absolutely necessary
- Small, targeted fixes are safer than dramatic overhauls
- Your goal is to improve the score, not create an entirely new concept
"""
    
    prompt = f"""You are an elite ad concept strategist. Review this 5-scene ad concept and IMPROVE it based on expert judge feedback.

**BRAND CONTEXT:**
- Brand: {config.get('BRAND_NAME', 'N/A')}
- Product: {config.get('PRODUCT_DESCRIPTION', 'N/A')}
- Tagline: {config.get('TAGLINE', 'N/A')}

**ORIGINAL CONCEPT:**
{concept_content}
{weaknesses_section}

**ADDITIONAL CONSTRAINTS:**
- Total duration: {duration} seconds (approximately {duration//5} seconds per scene, ±3 seconds)
- Each scene must be clear and renderable by AI video generation models
- Maintain visual and narrative coherence across all 5 scenes

**INSTRUCTIONS:**
1. Read the original concept carefully
2. Read the identified weaknesses
3. For EACH weakness, determine the minimum change needed to address it
4. Make your changes while preserving what's working
5. Ensure scenes are appropriately paced for {duration//5} seconds each
6. Verify your changes don't introduce new problems

**OUTPUT FORMAT:**
Return the IMPROVED 5-scene concept in the EXACT same format as the input.

After the 5 scenes, add a section "**STANDOUT ELEMENTS:**" with 1-2 sentences describing what is particularly standout, memorable, or compelling about this REVISED concept."""
    
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
    
    prompt = f"""You are a professional video director creating prompts for AI video generation (Veo 3 Fast, Sora 2).

**CRITICAL CONTEXT**: Each scene will be generated INDEPENDENTLY by the video AI model. Each prompt must be COMPLETELY SELF-CONTAINED with all necessary information.

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

**SORA 2 PROMPTING BEST PRACTICES:**
1. **Each scene prompt must be self-contained** - include style/aesthetic in EVERY scene (not just the first one)
2. **Be specific, not vague** - "wet asphalt, neon reflections" beats "beautiful street"
3. **Clear who, where, what** - Explicitly state who is in the frame, where they are, what they're doing
4. **For montage/multi-shot scenes**: Clearly distinguish each shot/moment so they don't blend together
5. **Dialogue**: Always specify WHO is speaking (character name or narrator with voice description)
6. **Keep motion simple**: One clear camera move, one clear subject action per shot
7. **Lighting**: Describe quality and source, not just "well lit"

**INSTRUCTIONS:**
For EACH of the 5 scenes, create:

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

4. **first_frame_image_prompt**: Complete image gen prompt matching {resolution} {aspect_ratio}. Must include:
   - Style description (hyper-realistic, photorealistic)
   - All characters/locations from elements_used clearly visible
   - Camera framing, lighting, composition details
   - Ready for nano-banana with reference images

5. **elements_used**: Characters/props/locations from universe_characters that appear in MULTIPLE scenes.
   - Use EXACT names from ALLOWED lists
   - Include version name if has_multiple_versions: "Name - Version Name"
   - Only include if scenes_used has 2+ scene numbers

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
      "first_frame_image_prompt": "[Hyper-realistic image prompt with all elements visible]",
      "elements_used": {{
        "characters": ["Exact Name - Version Name"],
        "locations": ["Exact Name - Version Name"],
        "props": ["Exact Name"]
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


def generate_video_script(evaluation_path, config_file, output_base_dir="script_generation", 
                          revision_model="anthropic/claude-sonnet-4-5-20250929",
                          duration=30):
    """
    Main function: Extract best concept, revise, and generate video production assets.
    
    Args:
        evaluation_path: Path to evaluation JSON from Step 2
        config_file: Path to brand config JSON file (required)
        output_base_dir: Base directory for outputs (default: script_generation)
        revision_model: LLM model for revision (default: claude-sonnet-4-5-20250929)
        duration: Video duration in seconds (default: 30)
    """
    print(f"\n{'='*80}")
    print("VIDEO SCRIPT GENERATOR")
    print(f"{'='*80}\n")
    
    # Step 1: Load evaluation and find best concept
    print("Step 1: Extracting best-scoring concept from evaluation...")
    best_concept, best_score = load_evaluation_json(evaluation_path)
    concept_file = best_concept.get("file")
    
    print(f"  ✓ Best score: {best_score}/100")
    print(f"  ✓ Concept file: {concept_file}")
    print(f"  ✓ Model: {best_concept.get('model')} | Template: {best_concept.get('template')}")
    
    # Load concept content
    concept_content = load_concept_file(concept_file)
    
    # Load config file - resolve path
    if not os.path.isabs(config_file):
        # Try relative to current working directory first, then BASE_DIR
        if os.path.exists(config_file):
            config_file = os.path.abspath(config_file)
        else:
            config_file = str(BASE_DIR / config_file)
    
    if not os.path.exists(config_file):
        raise FileNotFoundError(f"Config file not found: {config_file}")
    
    print(f"  ✓ Config file: {config_file}")
    config = load_config_file(config_file)
    
    # Extract batch folder from concept file path
    concept_path = Path(concept_file)
    batch_folder = concept_path.parent.name  # e.g., "rolex_1115_1833"
    
    # Create output directory structure
    # Use s4_revise_concept/outputs/ for consistency with pipeline
    if output_base_dir == "script_generation":
        output_base_dir = str(BASE_DIR / "s4_revise_concept" / "outputs")
    # Resolve output_base_dir relative to BASE_DIR if not absolute
    if not os.path.isabs(output_base_dir):
        output_base_dir = str(BASE_DIR / output_base_dir)
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
    if len(sys.argv) < 3:
        print("Usage: python generate_video_script.py <evaluation_json> <config_json> [duration] [model]")
        print("\nExample:")
        print("  python generate_video_script.py evaluations/rolex_evaluation_claude_4.5_1115_1848.json s1_generate_concepts/inputs/configs/rolex.json")
        print("  python generate_video_script.py evaluations/rolex_evaluation_claude_4.5_1115_1848.json s1_generate_concepts/inputs/configs/rolex.json 30")
        print("  python generate_video_script.py evaluations/rolex_evaluation_claude_4.5_1115_1848.json s1_generate_concepts/inputs/configs/rolex.json 30 openai/gpt-5.1")
        sys.exit(1)
    
    evaluation_path = sys.argv[1]
    config_file = sys.argv[2]
    duration = int(sys.argv[3]) if len(sys.argv) > 3 else 30
    model = sys.argv[4] if len(sys.argv) > 4 else "anthropic/claude-sonnet-4-5-20250929"
    
    if not os.path.exists(evaluation_path):
        print(f"Error: Evaluation file not found: {evaluation_path}")
        sys.exit(1)
    
    if not os.path.exists(config_file):
        print(f"Error: Config file not found: {config_file}")
        sys.exit(1)
    
    generate_video_script(evaluation_path, config_file, duration=duration, revision_model=model)

