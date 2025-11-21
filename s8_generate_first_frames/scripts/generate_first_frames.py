#!/usr/bin/env python3
"""
Generate first frame reference images for all scenes in parallel using nano-banana-pro.
Runs after generate_video_script.py and before generate_video_clips.py.
"""

import os
import sys
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

# Add path for imports
BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR / "s6_generate_reference_images" / "scripts"))

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    import replicate
except ImportError:
    print("ERROR: replicate package not installed. Run: pip install replicate")
    sys.exit(1)

from generate_universe_images import generate_image, get_replicate_token, slugify


def find_reference_images_for_scene(scene_data, universe_chars, universe_images_dir, max_images=5, image_summary=None):
    """
    Find reference image file paths for elements used in MULTIPLE scenes only.
    Uses image_generation_summary.json to map element names to actual file paths.
    Prioritizes: characters > props > locations
    Limits to max_images (nano-banana maximum is 5).
    
    Returns tuple of (list of image paths, list of element names for prompt).
    """
    reference_images = []
    element_names = []  # Track which elements we're providing
    elements_used = scene_data.get("elements_used", {})
    scene_num = scene_data.get("scene_number", 1)
    
    # Map character/location/prop names to their image files
    # Parse version names from elements_used (format: "Element Name - Version Name")
    def parse_element_name(element_str):
        """Parse element name and version from string like 'Element Name - Version Name' or just 'Element Name'."""
        if " - " in element_str:
            base_name, version_name = element_str.split(" - ", 1)
            return base_name.strip(), version_name.strip()
        return element_str.strip(), None
    
    characters = elements_used.get("characters", [])
    props = elements_used.get("props", [])
    locations = elements_used.get("locations", [])
    
    # Helper to find image path using image_summary (actual generated files)
    def find_image_path_via_summary(element_name, element_type, scene_num, expected_version_name=None):
        """Find image path using image_generation_summary.json (most reliable)."""
        if not image_summary:
            return (None, None)
        
        # First, find the matching universe element
        matching_universe_element = None
        for element in (universe_chars.get("characters", []) if element_type == "character" else 
                       universe_chars.get("universe", {}).get("locations", []) if element_type == "location" else
                       universe_chars.get("universe", {}).get("props", [])):
            universe_element_name = element.get("name", "")
            universe_base_name = universe_element_name.split("(")[0].strip() if "(" in universe_element_name else universe_element_name
            element_name_base = element_name.split("(")[0].strip() if "(" in element_name else element_name
            
            # Match by: exact name, base name, or if scene element name appears in universe name
            if (universe_element_name == element_name or 
                universe_base_name == element_name_base or 
                element_name in universe_element_name or
                element_name_base in universe_base_name or
                universe_base_name in element_name_base):
                matching_universe_element = element
                break
        
        if not matching_universe_element:
            return (None, None)
        
        scenes_used = matching_universe_element.get("scenes_used", [])
        if len(scenes_used) < 2:
            return (None, None)  # Skip single-scene elements
        
        # Debug: print what we're looking for
        # print(f"DEBUG: Looking for {element_name} ({element_type}), found universe element: {matching_universe_element.get('name')}")
        
        # Now find the matching summary element by checking if it matches the universe element
        for element_data in image_summary.get("elements", []):
            summary_element_name = element_data.get("element_name", "")
            summary_element_type = element_data.get("element_type", "")
            
            # Check if types match
            type_match = (
                (element_type == "character" and summary_element_type == "character") or
                (element_type == "location" and summary_element_type == "location") or
                (element_type == "prop" and summary_element_type == "prop")
            )
            
            if not type_match:
                continue
            
            # Match summary element to universe element by name similarity
            summary_base = summary_element_name.split("(")[0].strip() if "(" in summary_element_name else summary_element_name
            universe_base = matching_universe_element.get("name", "").split("(")[0].strip() if "(" in matching_universe_element.get("name", "") else matching_universe_element.get("name", "")
            
            # Normalize for comparison (handle plurals word-by-word)
            def normalize_words(name):
                words = name.lower().strip().split()
                normalized = []
                for word in words:
                    # Remove common plural endings
                    if word.endswith('s') and len(word) > 3:
                        normalized.append(word[:-1])
                    else:
                        normalized.append(word)
                return ' '.join(normalized)
            
            summary_norm = normalize_words(summary_base)
            universe_norm = normalize_words(universe_base)
            
            # Check if they refer to the same element (strict matching for name variations)
            # Only match if names are actually similar, not just sharing common words
            exact_match = summary_element_name == matching_universe_element.get("name")
            base_match = summary_base.lower() == universe_base.lower()
            normalized_match = summary_norm == universe_norm
            set_match = set(summary_norm.split()) == set(universe_norm.split())  # Same words (order-independent)
            
            # Only use substring matching if most words match (not just one word like "chef")
            words1 = set(summary_norm.split())
            words2 = set(universe_norm.split())
            common_words = words1 & words2
            # Require at least 2 words in common, or if one name is very short, require all words
            word_overlap = len(common_words) >= 2 or (min(len(words1), len(words2)) <= 2 and len(common_words) == min(len(words1), len(words2)))
            
            if (exact_match or base_match or normalized_match or set_match or word_overlap):
                
                # Find the version used in this scene
                images = element_data.get("images", {})
                if matching_universe_element.get("has_multiple_versions") and "versions" in matching_universe_element:
                    # If expected_version_name is provided from elements_used, use it for exact matching
                    # Otherwise, find version by scene_num
                    matching_version = None
                    if expected_version_name:
                        # Look for version with matching name
                        for version in matching_universe_element.get("versions", []):
                            if (slugify(version.get("version_name", "")) == slugify(expected_version_name) or
                                version.get("version_name", "").lower().strip() == expected_version_name.lower().strip()):
                                matching_version = version
                                break
                    else:
                        # Fallback: find version by scene_num
                        for version in matching_universe_element.get("versions", []):
                            version_scenes = version.get("scenes_used", [])
                            if scene_num in version_scenes:
                                matching_version = version
                                break
                    
                    if matching_version:
                        version_name = matching_version.get("version_name", "")
                        is_original = matching_version.get("is_original", True)
                        # Match image by exact version name match
                        exact_match = None
                        fallback_match = None
                        
                        # First pass: look for exact matches only (strict matching)
                        for img_name, img_data in images.items():
                            filepath = img_data.get("filepath")
                            
                            if not filepath or not os.path.exists(filepath):
                                continue
                            
                            # STRICT exact match: slug match or exact string match (case-insensitive)
                            if (slugify(img_name) == slugify(version_name) or 
                                version_name.lower().strip() == img_name.lower().strip()):
                                exact_match = (filepath, summary_element_name)
                                break  # Found exact match, use it immediately
                        
                        # If exact match found, return it immediately
                        if exact_match:
                            return exact_match
                        
                        # Second pass: fallback to is_original matching (only if no exact match)
                        for img_name, img_data in images.items():
                            img_is_original = img_data.get("is_original", True)
                            filepath = img_data.get("filepath")
                            
                            if not filepath or not os.path.exists(filepath):
                                continue
                            
                            # Fallback: match by is_original status
                            if img_is_original == is_original:
                                fallback_match = (filepath, summary_element_name)
                                break  # Found fallback match, use it
                        
                        # Return fallback match if found
                        if fallback_match:
                            return fallback_match
                else:
                    # Single version - use first available image
                    for img_name, img_data in images.items():
                        filepath = img_data.get("filepath")
                        if filepath and os.path.exists(filepath):
                            return (filepath, summary_element_name)
        
        return (None, None)
    
    # Helper to find image path and check if element appears in multiple scenes
    def find_image_path(element_name, element_type, scene_num):
        # First try using image_summary (most reliable - uses actual generated files)
        img_path, element_name_found = find_image_path_via_summary(element_name, element_type, scene_num)
        if img_path:
            return (img_path, element_name_found)
        # Find element in universe_chars
        if element_type == "character":
            elements_list = universe_chars.get("characters", [])
        elif element_type == "prop":
            elements_list = universe_chars.get("universe", {}).get("props", [])
        else:  # location
            elements_list = universe_chars.get("universe", {}).get("locations", [])
        
        for element in elements_list:
            # Match by exact name or by base name (e.g., "Main Chef" matches "Main Chef (Protagonist)")
            element_full_name = element.get("name", "")
            element_base_name = element_full_name.split("(")[0].strip() if "(" in element_full_name else element_full_name
            if element.get("name") == element_name or element_base_name == element_name or element_name in element_full_name:
                # ONLY include if element appears in MULTIPLE scenes
                scenes_used = element.get("scenes_used", [])
                if len(scenes_used) < 2:
                    # Skip - only appears in one scene, no need for reference
                    continue
                
                # Use the element's full name from universe for slug
                element_slug = slugify(element_full_name)
                
                # Check which version is used in this scene
                has_multiple_versions = element.get("has_multiple_versions", False)
                
                if has_multiple_versions and "versions" in element:
                    # Find version used in this scene
                    for version in element.get("versions", []):
                        version_scenes = version.get("scenes_used", [])
                        if scene_num in version_scenes:
                            version_name = version.get("version_name", "")
                            version_slug = slugify(version_name)
                            
                            # Construct image path - try multiple possible directory names
                            image_filename = f"{element_slug}_{version_slug}.jpg"
                            possible_dirs = [
                                element_slug,  # Try exact slug
                                slugify(element_name),  # Try scene's element name
                                slugify(element_base_name),  # Try base name without parentheses
                            ]
                            
                            for dir_name in possible_dirs:
                                image_path = os.path.join(
                                    universe_images_dir,
                                    "characters" if element_type == "character" else "locations",
                                    dir_name,
                                    image_filename
                                )
                                if os.path.exists(image_path):
                                    return (image_path, element_full_name)
                            
                            # Also try with just version slug as filename (if directory structure is different)
                            alt_filename = f"{dir_name}_{version_slug}.jpg"
                            for dir_name in possible_dirs:
                                alt_path = os.path.join(
                                    universe_images_dir,
                                    "characters" if element_type == "character" else "locations",
                                    dir_name,
                                    alt_filename
                                )
                                if os.path.exists(alt_path):
                                    return (alt_path, element_full_name)
                else:
                    # Single version element - try multiple possible directory names
                    image_filename = f"{element_slug}.jpg"
                    possible_dirs = [
                        element_slug,  # Try exact slug
                        slugify(element_name),  # Try scene's element name
                        slugify(element_base_name),  # Try base name without parentheses
                    ]
                    
                    # Props might be in different location
                    if element_type == "prop":
                        for dir_name in possible_dirs:
                            image_path = os.path.join(universe_images_dir, "props", dir_name, image_filename)
                            if os.path.exists(image_path):
                                return (image_path, element_full_name)
                    else:
                        for dir_name in possible_dirs:
                            image_path = os.path.join(
                                universe_images_dir,
                                "characters" if element_type == "character" else "locations",
                                dir_name,
                                image_filename
                            )
                            if os.path.exists(image_path):
                                return (image_path, element_full_name)
                        
                        # Also try with dir_name as prefix in filename
                        for dir_name in possible_dirs:
                            alt_filename = f"{dir_name}.jpg"
                            alt_path = os.path.join(
                                universe_images_dir,
                                "characters" if element_type == "character" else "locations",
                                dir_name,
                                alt_filename
                            )
                            if os.path.exists(alt_path):
                                return (alt_path, element_full_name)
        
        return (None, None)
    
    # PRIORITY 1: Collect reference images for characters (appearing in multiple scenes)
    character_images = []
    character_names = []
    seen_paths = set()  # Track seen image paths to avoid duplicates
    for char_str in characters:
        base_name, version_name = parse_element_name(char_str)
        img_path, element_name = find_image_path_via_summary(base_name, "character", scene_num, version_name)
        if not img_path:
            # Fallback to old method if summary lookup fails
            img_path, element_name = find_image_path(char_str, "character", scene_num)
        if img_path:
            if img_path not in seen_paths:
                character_images.append(img_path)
                character_names.append(element_name)
                seen_paths.add(img_path)
            else:
                print(f"    DEBUG: Duplicate path for {char_str}: {img_path}")
        else:
            print(f"    DEBUG: No image found for {char_str} (character, scene {scene_num})")
    
    # PRIORITY 2: Collect reference images for props (appearing in multiple scenes)
    prop_images = []
    prop_names = []
    for prop_str in props:
        base_name, version_name = parse_element_name(prop_str)
        img_path, element_name = find_image_path_via_summary(base_name, "prop", scene_num, version_name)
        if not img_path:
            # Fallback to old method if summary lookup fails
            img_path, element_name = find_image_path(prop_str, "prop", scene_num)
        if img_path and img_path not in seen_paths:
            prop_images.append(img_path)
            prop_names.append(element_name)
            seen_paths.add(img_path)
    
    # PRIORITY 3: Collect reference images for locations (appearing in multiple scenes)
    location_images = []
    location_names = []
    for loc_str in locations:
        base_name, version_name = parse_element_name(loc_str)
        img_path, element_name = find_image_path_via_summary(base_name, "location", scene_num, version_name)
        if not img_path:
            # Fallback to old method if summary lookup fails
            img_path, element_name = find_image_path(loc_str, "location", scene_num)
        if img_path and img_path not in seen_paths:
            location_images.append(img_path)
            location_names.append(element_name)
            seen_paths.add(img_path)
    
    # Combine with priority: characters > props > locations
    # Limit to max_images (nano-banana maximum is 5)
    chars_used = min(len(character_images), max_images)
    reference_images = character_images[:chars_used]
    element_names = character_names[:chars_used]
    remaining_slots = max_images - chars_used
    
    props_used = min(remaining_slots, len(prop_images))
    if props_used > 0:
        reference_images.extend(prop_images[:props_used])
        element_names.extend(prop_names[:props_used])
        remaining_slots -= props_used
    
    locs_used = min(remaining_slots, len(location_images))
    if locs_used > 0:
        reference_images.extend(location_images[:locs_used])
        element_names.extend(location_names[:locs_used])
    
    # Warn if we had to truncate
    total_available = len(character_images) + len(prop_images) + len(location_images)
    if total_available > max_images:
        print(f"    ⚠ Scene {scene_num}: {total_available} reference images available, limiting to {max_images} (nano-banana maximum)")
        print(f"      Using: {chars_used} character(s), {props_used} prop(s), {locs_used} location(s)")
    
    return reference_images, element_names


def generate_single_first_frame(scene_data, universe_chars, universe_images_dir, output_dir, base_name, resolution="480p", image_summary=None):
    """
    Generate first frame image for a single scene using reference images.
    
    Args:
        scene_data: Dict with scene_number, first_frame_image_prompt, elements_used, etc.
        universe_chars: Universe/characters JSON data
        universe_images_dir: Directory containing generated reference images
        output_dir: Directory to save first frame images
        base_name: Base filename prefix
        resolution: Video resolution (480p or 1080p)
        image_summary: Image generation summary JSON (maps element names to actual file paths)
    
    Returns:
        Tuple of (scene_number, output_path) or (scene_number, None) if failed
    """
    scene_num = scene_data.get("scene_number", 0)
    first_frame_prompt = scene_data.get("first_frame_image_prompt")
    
    if not first_frame_prompt:
        print(f"  ⚠ Scene {scene_num}: No first_frame_image_prompt found, skipping")
        return (scene_num, None)
    
    # Find reference images for elements appearing in MULTIPLE scenes only
    # Limit to 5 images (nano-banana maximum)
    # Priority: characters > props > locations
    # Use image_summary to map element names to actual file paths
    reference_images, element_names = find_reference_images_for_scene(scene_data, universe_chars, universe_images_dir, max_images=5, image_summary=image_summary)
    
    # Enhance prompt to mention which reference images are provided
    reference_info = ""
    if element_names:
        reference_info = f"\n\nREFERENCE IMAGES PROVIDED ({len(element_names)}): {', '.join(element_names)}\nCRITICAL: Use these reference images as visual references for character/location consistency. Blend them seamlessly and naturally into the scene - do NOT literally insert them as-is. Integrate the visual style, appearance, and key features from the references into the complete scene composition. You don't need to show all reference elements if the scene doesn't require it - focus on the gist and natural integration. The final image should look like a cohesive, natural scene, not a composite of separate images."
    else:
        reference_info = "\n\nNO REFERENCE IMAGES: Generate the scene from scratch following the prompt description."
    
    enhanced_prompt = f"{first_frame_prompt}{reference_info}"
    
    # Create output filename (nano-banana-pro outputs PNG)
    first_frame_filename = f"{base_name}_p{scene_num}_first_frame.png"
    output_path = os.path.join(output_dir, first_frame_filename)
    
    # Create debug directory for this scene
    debug_dir = os.path.join(output_dir, "debug", f"scene_{scene_num}")
    debug_name = f"first_frame_p{scene_num}"
    
    try:
        print(f"  Generating first frame for scene {scene_num}...")
        if reference_images:
            print(f"    Using {len(reference_images)} reference image(s) for characters/locations")
        
        # Use the existing generate_image function with reference images and debug logging
        # Pass resolution for nano-banana-pro (maps 480p/720p/1080p to 2K)
        generate_image(
            prompt=enhanced_prompt,
            image_input=reference_images if reference_images else None,
            output_path=output_path,
            debug_dir=debug_dir,
            debug_name=debug_name,
            resolution=resolution
        )
        
        print(f"    ✓ Scene {scene_num}: {os.path.basename(output_path)}")
        return (scene_num, output_path)
        
    except Exception as e:
        print(f"    ✗ Scene {scene_num}: Failed to generate first frame - {e}")
        return (scene_num, None)


def load_image_generation_summary(universe_images_dir):
    """Load image_generation_summary.json to map element names to actual file paths."""
    summary_path = os.path.join(universe_images_dir, "image_generation_summary.json")
    if os.path.exists(summary_path):
        with open(summary_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


def generate_all_first_frames(scene_prompts_path, universe_chars_path=None, universe_images_dir=None, output_dir=None, resolution="480p", max_workers=5):
    """
    Generate first frame images for all scenes in parallel using reference images.
    
    Args:
        scene_prompts_path: Path to scene_prompts.json
        universe_chars_path: Path to universe_characters.json (auto-detected if None)
        universe_images_dir: Directory containing generated reference images (auto-detected if None)
        output_dir: Where to save first frame images (default: first_frames/{json_prefix}/)
        resolution: Video resolution (480p or 1080p)
        max_workers: Number of parallel workers
    """
    print("=" * 80)
    print("FIRST FRAME IMAGE GENERATOR")
    print("=" * 80)
    
    # Load scene prompts
    print(f"\nLoading: {scene_prompts_path}")
    with open(scene_prompts_path, 'r', encoding='utf-8') as f:
        scene_prompts = json.load(f)
    
    # Auto-detect universe_characters.json and images directory
    scene_prompts_file = Path(scene_prompts_path)
    scene_prompts_dir = scene_prompts_file.parent
    base_name = scene_prompts_file.stem.replace("_scene_prompts", "")
    
    if not universe_chars_path:
        universe_chars_path = os.path.join(scene_prompts_dir, f"{base_name}_universe_characters.json")
    
    if not universe_images_dir:
        universe_images_dir = os.path.join("universe_characters", base_name)
    
    # Load universe/characters
    print(f"Loading: {universe_chars_path}")
    if not os.path.exists(universe_chars_path):
        print(f"⚠ Warning: Universe characters file not found: {universe_chars_path}")
        print(f"  First frames will be generated without reference images")
        universe_chars = {}
    else:
        with open(universe_chars_path, 'r', encoding='utf-8') as f:
            universe_chars = json.load(f)
    
    if not os.path.exists(universe_images_dir):
        print(f"⚠ Warning: Universe images directory not found: {universe_images_dir}")
        print(f"  First frames will be generated without reference images")
        universe_images_dir = None
        image_summary = None
    else:
        # Load image_generation_summary.json to map element names to actual file paths
        image_summary = load_image_generation_summary(universe_images_dir)
        if image_summary:
            print(f"  ✓ Loaded image generation summary (maps element names to actual file paths)")
        else:
            print(f"  ⚠ No image_generation_summary.json found - will try directory-based matching")
    
    # Determine output directory
    if not output_dir:
        json_prefix = base_name
        output_dir = os.path.join("first_frames", json_prefix)
    
    os.makedirs(output_dir, exist_ok=True)
    print(f"\nOutput directory: {output_dir}/")
    print(f"Resolution: {resolution} (aspect ratio: 16:9)")
    print(f"Universe images: {universe_images_dir if universe_images_dir and os.path.exists(universe_images_dir) else 'Not found'}")
    print(f"Parallel workers: {max_workers}\n")
    
    # Get API token
    try:
        get_replicate_token()
    except ValueError as e:
        print(f"ERROR: {e}")
        sys.exit(1)
    
    scenes = scene_prompts.get("scenes", [])
    print(f"Found {len(scenes)} scenes to process\n")
    
    if not scenes:
        print("No scenes found in scene_prompts.json")
        return {}
    
    # Generate first frames in parallel
    first_frames = {}
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_scene = {
            executor.submit(generate_single_first_frame, scene, universe_chars, universe_images_dir, output_dir, base_name, resolution, image_summary): scene
            for scene in scenes
        }
        
        # Collect results as they complete
        for future in as_completed(future_to_scene):
            scene = future_to_scene[future]
            try:
                scene_num, output_path = future.result()
                if output_path:
                    first_frames[scene_num] = output_path
            except Exception as e:
                scene_num = scene.get("scene_number", 0)
                print(f"  ✗ Scene {scene_num}: Exception - {e}")
    
    elapsed_time = time.time() - start_time
    
    print("\n" + "=" * 80)
    print("FIRST FRAME GENERATION COMPLETE")
    print("=" * 80)
    print(f"Total scenes processed: {len(first_frames)}/{len(scenes)}")
    print(f"Time elapsed: {elapsed_time:.1f}s")
    print(f"Output directory: {output_dir}/")
    print("=" * 80)
    
    # Save summary
    summary = {
        "scene_prompts_file": str(scene_prompts_path),
        "output_dir": output_dir,
        "resolution": resolution,
        "aspect_ratio": "16:9",
        "total_scenes": len(scenes),
        "generated_frames": len(first_frames),
        "first_frames": {
            scene_num: os.path.basename(path) 
            for scene_num, path in sorted(first_frames.items())
        }
    }
    
    summary_file = os.path.join(output_dir, "first_frames_summary.json")
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2)
    print(f"\nSummary saved: {summary_file}")
    
    return first_frames


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python generate_first_frames.py <scene_prompts.json> [universe_characters.json] [universe_images_dir] [output_dir] [resolution] [max_workers]")
        print("\nExample:")
        print("  python generate_first_frames.py script_generation/rolex_1115_1833/rolex_achievement_inspirational_advanced_claude_sonnet_4.5/rolex_achievement_inspirational_advanced_claude_sonnet_4.5_scene_prompts.json")
        sys.exit(1)
    
    scene_prompts_path = sys.argv[1]
    universe_chars_path = sys.argv[2] if len(sys.argv) > 2 else None
    universe_images_dir = sys.argv[3] if len(sys.argv) > 3 else None
    output_dir = sys.argv[4] if len(sys.argv) > 4 else None
    resolution = sys.argv[5] if len(sys.argv) > 5 else "480p"
    max_workers = int(sys.argv[6]) if len(sys.argv) > 6 else 5
    
    try:
        generate_all_first_frames(
            scene_prompts_path,
            universe_chars_path=universe_chars_path,
            universe_images_dir=universe_images_dir,
            output_dir=output_dir,
            resolution=resolution,
            max_workers=max_workers
        )
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

