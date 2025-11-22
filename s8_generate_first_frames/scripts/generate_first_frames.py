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
    Find canonical reference image file paths for elements used in this scene.
    Uses image_generation_summary.json to map element names to actual file paths.
    Prioritizes: characters > props > locations
    Limits to max_images (nano-banana maximum is 5).
    
    Returns tuple of (list of image paths, list of element names).
    """
    reference_images = []
    element_names = []  # Track which elements we're providing
    elements_used = scene_data.get("elements_used", [])  # Simple list of element names
    scene_num = scene_data.get("scene_number", 1)
    
    # Separate elements by type (infer from universe_chars)
    characters = []
    props = []
    locations = []
    
    for elem_name in elements_used:
        # Check if it's a character
        if any(char.get('name') == elem_name for char in universe_chars.get('characters', [])):
            characters.append(elem_name)
        # Check if it's a prop
        elif any(prop.get('name') == elem_name for prop in universe_chars.get('universe', {}).get('props', [])):
            props.append(elem_name)
        # Check if it's a location
        elif any(loc.get('name') == elem_name for loc in universe_chars.get('universe', {}).get('locations', [])):
            locations.append(elem_name)
    
    # Helper to find image path using image_summary (actual generated files)
    def find_image_path_via_summary(element_name, element_type):
        """Find canonical image path using image_generation_summary.json."""
        if not image_summary:
            return (None, None)
        
        # Find matching element in image summary
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
            
            # Simple name matching
            if summary_element_name.lower().strip() == element_name.lower().strip():
                # Found match - get canonical image
                images = element_data.get("images", {})
                
                # Look for canonical version
                canonical_img = images.get("canonical", {})
                filepath = canonical_img.get("filepath")
                
                if filepath:
                    candidates = []
                    
                    # As-is (in case already absolute)
                    if os.path.isabs(filepath):
                        candidates.append(filepath)
                    
                    base_dir = image_summary.get("_base_dir")
                    if base_dir:
                        candidates.append(os.path.normpath(os.path.join(base_dir, filepath)))
                        candidates.append(os.path.normpath(os.path.join(os.path.dirname(base_dir), filepath)))
                    
                    if universe_images_dir:
                        candidates.append(os.path.normpath(os.path.join(universe_images_dir, filepath)))
                        candidates.append(os.path.normpath(os.path.join(os.path.dirname(universe_images_dir), filepath)))
                    
                    # Remove duplicates while preserving order
                    seen = set()
                    unique_candidates = []
                    for candidate in candidates:
                        if candidate not in seen:
                            unique_candidates.append(candidate)
                            seen.add(candidate)
                    
                    for candidate in unique_candidates:
                        if os.path.exists(candidate):
                            return (candidate, summary_element_name)
        
        # Final fallback: build canonical path from element name
        if universe_images_dir:
            type_map = {
                "character": "characters",
                "location": "locations",
                "prop": "props"
            }
            type_dir = type_map.get(element_type)
            if type_dir:
                slug = slugify(element_name)
                candidate = os.path.join(
                    universe_images_dir,
                    type_dir,
                    slug,
                    f"{slug}_canonical.png"
                )
                if os.path.exists(candidate):
                    return (candidate, element_name)
        
        return (None, None)
    
    # Collect canonical reference images for each element type
    character_images = []
    character_names = []
    seen_paths = set()  # Track seen image paths to avoid duplicates
    
    for char_name in characters:
        img_path, element_name = find_image_path_via_summary(char_name, "character")
        if img_path and img_path not in seen_paths:
                character_images.append(img_path)
                character_names.append(element_name)
                seen_paths.add(img_path)
    
    # Collect props
    prop_images = []
    prop_names = []
    for prop_name in props:
        img_path, element_name = find_image_path_via_summary(prop_name, "prop")
        if img_path and img_path not in seen_paths:
            prop_images.append(img_path)
            prop_names.append(element_name)
            seen_paths.add(img_path)
    
    # Collect locations
    location_images = []
    location_names = []
    for loc_name in locations:
        img_path, element_name = find_image_path_via_summary(loc_name, "location")
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
    
    # Find canonical reference images for elements
    # Limit to 5 images (nano-banana maximum)
    # Priority: characters > props > locations
    reference_images, element_names = find_reference_images_for_scene(scene_data, universe_chars, universe_images_dir, max_images=5, image_summary=image_summary)
    
    # The first_frame_prompt already contains reference image handling instructions
    # (Step 7 includes "REFERENCE IMAGES ATTACHED:" section with canonical states and modifications)
    # Just pass it directly with the reference images
    enhanced_prompt = first_frame_prompt
    
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
            summary = json.load(f)
            summary["_base_dir"] = os.path.dirname(summary_path)
            return summary
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

