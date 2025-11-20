#!/usr/bin/env python3
"""
Generate reference images for universe/characters using Replicate nano-banana.
Handles parallel execution for different elements, sequential for multi-version elements.
"""

import os
import sys
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

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


def get_replicate_token():
    """Get Replicate API token from environment."""
    # Check both common names
    token = os.getenv("REPLICATE_API_TOKEN") or os.getenv("REPLICATE_API_KEY")
    if not token:
        raise ValueError("REPLICATE_API_TOKEN or REPLICATE_API_KEY not found in environment. Add it to .env file.")
    # Set as environment variable for replicate library
    os.environ["REPLICATE_API_TOKEN"] = token
    return token


def slugify(text):
    """Convert text to filename-safe slug."""
    import re
    # Replace spaces and special chars with underscores
    text = re.sub(r'[^\w\s-]', '', text.lower())
    text = re.sub(r'[-\s]+', '_', text)
    # Remove multiple consecutive underscores
    text = re.sub(r'_+', '_', text)
    # Remove leading/trailing underscores
    return text.strip('_')


def generate_image(prompt, image_input=None, output_path=None, debug_dir=None, debug_name=None):
    """
    Generate image using Replicate nano-banana.
    
    Args:
        prompt: Text prompt for image generation
        image_input: List of image URLs or file paths (for sequential versions)
        output_path: Path to save the generated image
        debug_dir: Directory to save debug info (prompts, reference images)
        debug_name: Name for debug files (e.g., "version_1", "version_2")
    
    Returns:
        URL of generated image, or file path if URL not available
    """
    get_replicate_token()  # Ensure token is set
    
    # Save debug info
    if debug_dir and debug_name:
        os.makedirs(debug_dir, exist_ok=True)
        
        # Save prompt (save AFTER image_input is set, so we capture what was actually used)
        prompt_file = os.path.join(debug_dir, f"{debug_name}_prompt.txt")
        with open(prompt_file, 'w', encoding='utf-8') as f:
            f.write(f"PROMPT:\n{prompt}\n\n")
            if image_input:
                f.write(f"REFERENCE IMAGES:\n")
                for i, img in enumerate(image_input):
                    # Handle both file paths and URLs
                    img_str = str(img)
                    f.write(f"  {i+1}. {img_str}\n")
                    if isinstance(img, str) and os.path.exists(img):
                        f.write(f"      (Local file path)\n")
                    elif isinstance(img, str) and (img.startswith('http://') or img.startswith('https://')):
                        f.write(f"      (URL)\n")
            else:
                f.write("REFERENCE IMAGES: None\n")
        
        # Copy reference images if they're local files
        if image_input:
            for i, img_path in enumerate(image_input):
                if isinstance(img_path, str) and os.path.exists(img_path):
                    import shutil
                    ref_copy = os.path.join(debug_dir, f"{debug_name}_reference_{i+1}.jpg")
                    shutil.copy2(img_path, ref_copy)
    
    input_params = {
        "prompt": prompt,
        "aspect_ratio": "match_input_image" if image_input else "16:9",
        "output_format": "jpg"
    }
    
    if image_input:
        # Handle file paths - Replicate's Python SDK can accept file paths or file objects
        # It will automatically upload them and convert to URLs
        processed_input = []
        for img in image_input:
            if isinstance(img, str) and os.path.exists(img):
                # It's a file path - Replicate SDK should handle this automatically
                # Open file and pass - SDK will upload it
                file_obj = open(img, 'rb')
                processed_input.append(file_obj)
            elif isinstance(img, str) and (img.startswith('http://') or img.startswith('https://')):
                # It's a URL - use directly
                processed_input.append(img)
            else:
                # Already a file object or URL
                processed_input.append(img)
        input_params["image_input"] = processed_input
    
    try:
        output = replicate.run(
            "google/nano-banana",
            input=input_params
        )
        
        # Handle different output types from replicate.run()
        image_url = None
        image_data = None
        
        # Priority 1: Check if output has url() method (file-like object with URL)
        # Get URL FIRST before reading (reading might consume the stream)
        if hasattr(output, 'url') and callable(getattr(output, 'url')):
            try:
                image_url = output.url()
            except:
                pass
        
        # Priority 2: Check if output has read() method (file-like object)
        # Only read if we need binary data for saving
        if output_path and hasattr(output, 'read') and callable(getattr(output, 'read')):
            try:
                image_data = output.read()
            except:
                pass
        
        # Priority 3: Check if it's a string URL
        if not image_url and isinstance(output, str):
            image_url = output
        
        # Priority 4: Check if it's an iterator
        if not image_url and hasattr(output, '__iter__') and not isinstance(output, (str, bytes)):
            try:
                first_item = next(iter(output))
                if isinstance(first_item, str):
                    image_url = first_item
                elif hasattr(first_item, 'url') and callable(getattr(first_item, 'url')):
                    image_url = first_item.url()
                elif hasattr(first_item, 'read') and callable(getattr(first_item, 'read')):
                    image_data = first_item.read()
                else:
                    image_url = str(first_item)
            except StopIteration:
                raise ValueError("Replicate returned empty iterator")
        
        # Priority 5: Try to convert to string
        if not image_url and not image_data:
            image_url = str(output)
        
        # Save image if output_path provided
        if output_path:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            if image_data:
                # Write binary data directly
                with open(output_path, "wb") as f:
                    f.write(image_data)
                # If we have image_data but no URL, try to get URL from output object
                if not image_url and hasattr(output, 'url') and callable(getattr(output, 'url')):
                    try:
                        image_url = output.url()
                    except:
                        pass
            elif image_url:
                # Download from URL
                import requests
                response = requests.get(image_url)
                response.raise_for_status()
                with open(output_path, "wb") as f:
                    f.write(response.content)
            else:
                raise ValueError("Could not determine image data or URL from Replicate output")
            
            print(f"  ✓ Saved: {output_path}")
        
        # Return URL if available (for sequential versions)
        # If no URL but image was saved, return None (sequential input will be skipped)
        if image_url and (image_url.startswith('http://') or image_url.startswith('https://')):
            return image_url
        elif image_data and output_path:
            # Image was saved but no URL - this is OK, just return None
            # Sequential versions won't use this as input
            return None
        else:
            # Could not get URL or save image
            raise ValueError("Could not extract image URL or save image from Replicate output")
    
    except Exception as e:
        print(f"  ✗ Error generating image: {e}")
        return None


def generate_element_images(element, element_type, output_dir, json_prefix):
    """
    Generate images for a single element (character, location, or prop).
    Handles both single-version and multi-version elements.
    
    Args:
        element: Element dict from JSON
        element_type: 'characters', 'locations', or 'props'
        output_dir: Base output directory
        json_prefix: Prefix for folder naming (e.g., "rolex_achievement_inspirational_advanced_claude_sonnet_4.5")
    
    Returns:
        Dict with element name and generated image paths/URLs
    """
    element_name = element.get("name", "unknown")
    element_slug = slugify(element_name)
    
    print(f"\n  Processing {element_type[:-1]}: {element_name}")
    
    result = {
        "element_name": element_name,
        "element_type": element_type[:-1],  # Remove 's' from plural
        "images": {}
    }
    
    # Debug directory for this element - place inside output_dir
    debug_base_dir = os.path.join(output_dir, "debug", "nano-banana-prompts", json_prefix, element_type, element_slug)
    
    # Check if element has multiple versions
    has_multiple_versions = element.get("has_multiple_versions", False)
    
    if has_multiple_versions and "versions" in element:
        # Sequential generation for multi-version elements
        versions = element["versions"]
        previous_image_url = None  # URL from Replicate (preferred)
        previous_image_path = None  # Local file path (fallback for upload)
        
        for version in versions:
            version_name = version.get("version_name", "unknown")
            version_slug = slugify(version_name)
            is_original = version.get("is_original", False)
            
            # Create output path
            filename = f"{element_slug}_{version_slug}.jpg"
            filepath = os.path.join(output_dir, json_prefix, element_type, element_slug, filename)
            
            # Get image generation prompt
            image_prompt = version.get("image_generation_prompt", "")
            if not image_prompt:
                print(f"    ⚠ Skipping {version_name}: No image_generation_prompt found")
                continue
            
            print(f"    Generating: {version_name} {'(original)' if is_original else '(transformed)'}")
            
            # For transformed versions, use previous image as input
            image_input = None
            if not is_original:
                # Prefer URL from previous generation (if available)
                if previous_image_url:
                    image_input = [previous_image_url]
                    print(f"      Using previous version URL: {previous_image_url}")
                # Fallback: pass file path - Replicate SDK will handle upload automatically
                elif previous_image_path and os.path.exists(previous_image_path):
                    # Pass file path - Replicate Python SDK accepts file paths and handles upload
                    image_input = [previous_image_path]
                    print(f"      Using previous version file path: {previous_image_path}")
                    print(f"      (Replicate SDK will upload automatically)")
            
            # Debug directory for this version
            version_slug = slugify(version_name)
            debug_dir = os.path.join(debug_base_dir, version_slug)
            debug_name = version_slug
            
            # Generate image
            image_url = generate_image(
                prompt=image_prompt,
                image_input=image_input,
                output_path=filepath,
                debug_dir=debug_dir,
                debug_name=debug_name
            )
            
            if filepath and os.path.exists(filepath):
                result["images"][version_name] = {
                    "url": image_url if image_url else None,
                    "filepath": filepath,
                    "is_original": is_original,
                    "references_original": version.get("references_original_version")
                }
                # For next version: we need a URL for image_input
                # If we got a URL from Replicate, use it
                if image_url and (image_url.startswith('http://') or image_url.startswith('https://')):
                    previous_image_url = image_url
                    previous_image_path = filepath
                    print(f"      ✓ Image saved with URL: {image_url}")
                else:
                    # No URL from Replicate - we'll need to upload the file
                    # But for now, store the path and we'll handle upload in next iteration
                    previous_image_url = None
                    previous_image_path = filepath
                    print(f"      ✓ Image saved to: {filepath}")
                    print(f"      ⚠ No URL from Replicate - will try file object for next version")
            else:
                print(f"    ⚠ Image saved but no URL available (can't be used as reference for next version)")
                previous_image_url = None
                previous_image_path = None
    
    else:
        # Single version - simple generation
        image_prompt = element.get("image_generation_prompt", "")
        if not image_prompt:
            # Try description as fallback
            image_prompt = element.get("description", "")
        
        if not image_prompt:
            print(f"    ⚠ Skipping: No image_generation_prompt or description found")
            return result
        
        # Create output path
        filename = f"{element_slug}.jpg"
        filepath = os.path.join(output_dir, json_prefix, element_type, element_slug, filename)
        
        print(f"    Generating single version...")
        
        # Debug directory for single version
        debug_dir = os.path.join(debug_base_dir, "default")
        debug_name = element_slug
        
        # Generate image
        image_url = generate_image(
            prompt=image_prompt,
            output_path=filepath,
            debug_dir=debug_dir,
            debug_name=debug_name
        )
        
        if filepath and os.path.exists(filepath):
            result["images"]["default"] = {
                "url": image_url if image_url else None,
                "filepath": filepath
            }
            if image_url:
                print(f"      ✓ Image saved with URL: {image_url}")
            else:
                print(f"      ✓ Image saved to: {filepath}")
                print(f"      ⚠ No URL from Replicate")
        else:
            print(f"    ⚠ Image generation failed - file not found: {filepath}")
    
    return result


def generate_all_images(json_path, output_base_dir="universe_characters", max_workers=5):
    """
    Main function: Generate all images from universe_characters.json.
    
    Args:
        json_path: Path to universe_characters.json file
        output_base_dir: Base directory for output images
        max_workers: Number of parallel workers for image generation (default: 5)
    """
    print(f"\n{'='*80}")
    print("UNIVERSE/CHARACTERS IMAGE GENERATOR")
    print(f"{'='*80}\n")
    
    # Load JSON file
    print(f"Loading: {json_path}")
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Extract JSON prefix from filename (e.g., "rolex_achievement_inspirational_advanced_claude_sonnet_4.5")
    json_filename = Path(json_path).stem
    json_prefix = json_filename.replace("_universe_characters", "")
    
    print(f"JSON prefix: {json_prefix}")
    print(f"Output directory: {output_base_dir}/{json_prefix}/")
    
    # Collect all elements to process
    # ONLY process elements that appear in 2+ scenes (reference images are only for multi-scene elements)
    tasks = []
    
    # Process characters - only if they appear in 2+ scenes
    for char in data.get("characters", []):
        scenes_used = char.get("scenes_used", [])
        if len(scenes_used) >= 2:
            tasks.append(("characters", char))
        else:
            print(f"  ⏭  Skipping {char.get('name', 'unknown')}: only appears in {len(scenes_used)} scene(s)")
    
    # Process locations - only if they appear in 2+ scenes
    for loc in data.get("universe", {}).get("locations", []):
        scenes_used = loc.get("scenes_used", [])
        if len(scenes_used) >= 2:
            tasks.append(("locations", loc))
        else:
            print(f"  ⏭  Skipping {loc.get('name', 'unknown')}: only appears in {len(scenes_used)} scene(s)")
    
    # Process props - only if they appear in 2+ scenes
    for prop in data.get("universe", {}).get("props", []):
        scenes_used = prop.get("scenes_used", [])
        if len(scenes_used) >= 2:
            tasks.append(("props", prop))
        else:
            print(f"  ⏭  Skipping {prop.get('name', 'unknown')}: only appears in {len(scenes_used)} scene(s)")
    
    print(f"\nFound {len(tasks)} elements to process (multi-scene elements only)")
    print(f"Processing in parallel (multi-version elements will run sequentially)...")
    print(f"Max workers: {max_workers}\n")
    
    # Process elements in parallel
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_task = {
            executor.submit(
                generate_element_images,
                element,
                element_type,
                output_base_dir,
                json_prefix
            ): (element_type, element.get("name", "unknown"))
            for element_type, element in tasks
        }
        
        for future in as_completed(future_to_task):
            element_type, element_name = future_to_task[future]
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                print(f"  ✗ Error processing {element_type} {element_name}: {e}")
    
    # Save summary JSON
    summary = {
        "json_file": str(json_path),
        "json_prefix": json_prefix,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "elements": results
    }
    
    summary_path = os.path.join(output_base_dir, json_prefix, "image_generation_summary.json")
    os.makedirs(os.path.dirname(summary_path), exist_ok=True)
    
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    
    print(f"\n{'='*80}")
    print("IMAGE GENERATION COMPLETE")
    print(f"{'='*80}")
    print(f"Summary saved: {summary_path}")
    print(f"Total elements processed: {len(results)}")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python generate_universe_images.py <universe_characters.json>")
        print("Example: python generate_universe_images.py script_generation/rolex_1115_1833/rolex_achievement_inspirational_advanced_claude_sonnet_4.5/rolex_achievement_inspirational_advanced_claude_sonnet_4.5_universe_characters.json")
        sys.exit(1)
    
    json_path = sys.argv[1]
    
    if not os.path.exists(json_path):
        print(f"ERROR: File not found: {json_path}")
        sys.exit(1)
    
    # Check for Replicate token
    try:
        get_replicate_token()
    except ValueError as e:
        print(f"ERROR: {e}")
        sys.exit(1)
    
    generate_all_images(json_path)

