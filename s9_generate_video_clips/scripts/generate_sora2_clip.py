#!/usr/bin/env python3
"""
Generate video clip for a single scene using OpenAI Sora 2 via Replicate.
Takes first frame image, video prompt, audio descriptions, and generates video.
"""

import os
import sys
import json
from pathlib import Path

# Load environment variables
try:
    from dotenv import load_dotenv
    # Load .env from project root (3 levels up from this script)
    env_path = Path(__file__).resolve().parents[3] / ".env"
    load_dotenv(env_path)
except ImportError:
    pass

try:
    import replicate
except ImportError:
    print("ERROR: replicate package not installed. Run: pip install replicate")
    sys.exit(1)


def get_replicate_token():
    """Get Replicate API token from environment."""
    token = os.getenv("REPLICATE_API_TOKEN") or os.getenv("REPLICATE_API_KEY")
    if not token:
        raise ValueError("REPLICATE_API_TOKEN or REPLICATE_API_KEY not found in environment")
    return token


def generate_sora2_clip(scene_data, first_frame_image_path, output_path, video_model="google/veo-3.1-fast", aspect_ratio="16:9"):
    """
    Generate video clip using Sora 2, Veo 3 Fast, or Veo 3.1 Fast.
    
    Args:
        scene_data: Dict with video_prompt, audio_background, audio_dialogue
        first_frame_image_path: Path to first frame image (local file)
        output_path: Where to save output video
        video_model: Model to use - "openai/sora-2", "google/veo-3-fast", or "google/veo-3.1-fast"
        aspect_ratio: Video aspect ratio (16:9 = landscape)
    """
    video_prompt = scene_data.get("video_prompt", "")
    audio_background = scene_data.get("audio_background", "")
    audio_dialogue = scene_data.get("audio_dialogue")
    visual_effects = scene_data.get("visual_effects", [])
    
    # Combine prompts
    combined_prompt = video_prompt
    
    if audio_background:
        combined_prompt += f"\n\nBackground Music: {audio_background}"
    
    if audio_dialogue:
        # audio_dialogue already includes speaker name and voice characteristics
        # Format is: "Character Name: dialogue" or "Narrator (voice): dialogue"
        combined_prompt += f"\n\n{audio_dialogue}"
    
    # Add visual effects instructions if present
    if visual_effects:
        combined_prompt += "\n\n**VISUAL EFFECTS TO IMPLEMENT:**"
        for effect in visual_effects:
            effect_name = effect.get("name", "")
            effect_desc = effect.get("description", "")
            effect_timing = effect.get("timing", "")
            combined_prompt += f"\n- **{effect_name}**: {effect_desc}"
            if effect_timing:
                combined_prompt += f" (Timing: {effect_timing})"
    
    # Check if first frame image exists
    if not os.path.exists(first_frame_image_path):
        raise FileNotFoundError(f"First frame image not found: {first_frame_image_path}")
    
    # Determine model name and settings
    is_sora2 = video_model == "openai/sora-2"
    if is_sora2:
        model_name = "Sora-2"
    elif "veo-3.1" in video_model:
        model_name = "Veo 3.1 Fast"
    else:
        model_name = "Veo 3 Fast"
    
    print(f"  Generating video with {model_name}...")
    print(f"    Prompt length: {len(combined_prompt)} chars")
    print(f"    First frame: {os.path.basename(first_frame_image_path)}")
    print(f"    Duration: {scene_data.get('duration_seconds', 6)} seconds")
    print(f"    Aspect ratio: {aspect_ratio}")
    if not is_sora2:
        print(f"    Resolution: 720p")
        print(f"    Generate audio: True")
    
    # Create debug directory and save prompt
    debug_dir = os.path.join(os.path.dirname(output_path), "debug", f"scene_{scene_data.get('scene_number', 1)}")
    os.makedirs(debug_dir, exist_ok=True)
    model_short = "sora2" if is_sora2 else "veo3"
    debug_prompt_file = os.path.join(debug_dir, f"{model_short}_p{scene_data.get('scene_number', 1)}_prompt.txt")
    with open(debug_prompt_file, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write(f"{model_name.upper()} PROMPT (EXACT SENT TO API)\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"Model: {video_model}\n")
        f.write(f"Scene Number: {scene_data.get('scene_number', 1)}\n")
        f.write(f"First Frame Image: {first_frame_image_path}\n")
        f.write(f"Duration: {scene_data.get('duration_seconds', 6)} seconds\n")
        f.write(f"Aspect Ratio: {aspect_ratio}\n")
        if not is_sora2:
            f.write(f"Resolution: 720p\n")
            f.write(f"Generate Audio: True\n")
        f.write("\n")
        f.write("COMBINED PROMPT:\n")
        f.write("-" * 80 + "\n")
        f.write(combined_prompt)
        f.write("\n" + "-" * 80 + "\n\n")
        f.write("BREAKDOWN:\n")
        f.write(f"Video Prompt: {scene_data.get('video_prompt', '')[:200]}...\n\n")
        f.write(f"Audio Background: {scene_data.get('audio_background', '')}\n\n")
        f.write(f"Audio Dialogue: {scene_data.get('audio_dialogue', 'None')}\n\n")
        visual_effects = scene_data.get('visual_effects', [])
        if visual_effects:
            f.write(f"Visual Effects ({len(visual_effects)}):\n")
            for effect in visual_effects:
                f.write(f"  - {effect.get('name', 'Unknown')}: {effect.get('description', '')} (Timing: {effect.get('timing', 'N/A')})\n")
        else:
            f.write("Visual Effects: None\n")
    print(f"    ✓ Saved prompt to: {debug_prompt_file}")
    
    try:
        # Get Replicate API token
        api_token = os.getenv("REPLICATE_API_TOKEN") or os.getenv("REPLICATE_API_KEY")
        if not api_token:
            raise ValueError("REPLICATE_API_TOKEN or REPLICATE_API_KEY not found in environment")
        
        # Set in environment for replicate.run() to use
        os.environ["REPLICATE_API_TOKEN"] = api_token
        
        # Upload image file first to get URI
        # Replicate SDK will handle upload when we pass file path
        # But we need to use the client.files API to get a URI
        client = replicate.Client(api_token=api_token)
        
        # Upload the image file to get a URI
        print(f"    Uploading first frame image...")
        with open(first_frame_image_path, "rb") as f:
            file_obj = client.files.create(f)
            image_uri = file_obj.urls["get"]
        
        print(f"    Image uploaded: {image_uri[:50]}...")
        
        # Save image URI to debug file
        with open(debug_prompt_file, 'a', encoding='utf-8') as f:
            f.write(f"\nFirst Frame Image URI: {image_uri}\n")
        
        # Prepare input data based on model
        if is_sora2:
            # Sora-2 API parameters
            scene_duration = scene_data.get("duration_seconds", 6)
            # Sora-2 only accepts 4, 8, or 12 seconds
            valid_durations = [4, 8, 12]
            scene_duration = min(valid_durations, key=lambda x: abs(x - scene_duration))
            if scene_duration != scene_data.get("duration_seconds", 6):
                print(f"    ⚠ Duration adjusted from {scene_data.get('duration_seconds', 6)}s to {scene_duration}s (Sora-2 requirement)")
            # Sora-2 uses "landscape" or "portrait" for aspect_ratio
            if aspect_ratio == "16:9":
                sora_aspect = "landscape"
            elif aspect_ratio == "9:16":
                sora_aspect = "portrait"
            else:
                # Default to landscape for other ratios
                sora_aspect = "landscape"
                print(f"    ⚠ Aspect ratio {aspect_ratio} not explicitly supported, defaulting to landscape")
            
            input_data = {
                "prompt": combined_prompt,
                "seconds": scene_duration,
                "aspect_ratio": sora_aspect,
                "input_reference": image_uri
            }
            
            # Save full input data to debug file
            with open(debug_prompt_file, 'a', encoding='utf-8') as f:
                f.write("\n" + "=" * 80 + "\n")
                f.write("FULL API INPUT DATA:\n")
                f.write("=" * 80 + "\n")
                f.write(f"prompt: {combined_prompt}\n\n")
                f.write(f"seconds: {scene_duration}\n\n")
                f.write(f"aspect_ratio: {sora_aspect}\n\n")
                f.write(f"input_reference: {image_uri}\n")
        else:
            # Veo 3/3.1 Fast API parameters
            scene_duration = scene_data.get("duration_seconds", 6)
            # Veo 3/3.1 Fast only accepts 4, 6, or 8 seconds
            valid_durations = [4, 6, 8]
            scene_duration = min(valid_durations, key=lambda x: abs(x - scene_duration))
            if scene_duration != scene_data.get("duration_seconds", 6):
                print(f"    ⚠ Duration adjusted from {scene_data.get('duration_seconds', 6)}s to {scene_duration}s ({model_name} requirement)")
            
            input_data = {
                "image": image_uri,
                "prompt": combined_prompt,
                "duration": scene_duration,
                "resolution": "720p",
                "aspect_ratio": "16:9",
                "generate_audio": True
            }
        
        # Save full input data to debug file
        with open(debug_prompt_file, 'a', encoding='utf-8') as f:
            f.write("\n" + "=" * 80 + "\n")
            f.write("FULL API INPUT DATA:\n")
            f.write("=" * 80 + "\n")
            f.write(f"image: {image_uri}\n\n")
            f.write(f"prompt: {combined_prompt}\n\n")
            f.write(f"duration: {scene_duration}\n\n")
            f.write(f"resolution: 720p\n\n")
            f.write(f"aspect_ratio: 16:9\n\n")
            f.write(f"generate_audio: True\n")
        
        output = replicate.run(
            video_model,
            input=input_data
        )
        
        # Save output video
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Handle different output types (Veo 3.1 returns FileOutput with .url() and .read() methods)
        if hasattr(output, 'read'):
            # File-like object (preferred method for Veo 3.1)
            with open(output_path, "wb") as f:
                f.write(output.read())
        elif hasattr(output, 'url'):
            # URL method - download it
            import urllib.request
            urllib.request.urlretrieve(output.url(), output_path)
        elif isinstance(output, str):
            # String URL
            import urllib.request
            urllib.request.urlretrieve(output, output_path)
        else:
            # Try to iterate (some Replicate outputs are iterators)
            with open(output_path, "wb") as f:
                for chunk in output:
                    if hasattr(chunk, 'read'):
                        f.write(chunk.read())
                    elif isinstance(chunk, bytes):
                        f.write(chunk)
        
        print(f"    ✓ Saved: {output_path}")
        return output_path
        
    except Exception as e:
        print(f"    ✗ Failed: {e}")
        raise


def main():
    """Main entry point."""
    if len(sys.argv) < 4:
        print("Usage: python generate_sora2_clip.py <scene_prompts.json> <scene_number> <first_frame_image_path> [output_path]")
        print("\nExample:")
        print("  python generate_sora2_clip.py script_generation/.../scene_prompts.json 1 first_frames/.../p1_first_frame.png")
        sys.exit(1)
    
    scene_prompts_path = sys.argv[1]
    scene_number = int(sys.argv[2])
    first_frame_path = sys.argv[3]
    output_path = sys.argv[4] if len(sys.argv) > 4 else None
    
    # Load scene prompts
    print(f"Loading: {scene_prompts_path}")
    with open(scene_prompts_path, 'r', encoding='utf-8') as f:
        scene_prompts = json.load(f)
    
    # Find scene
    scenes = scene_prompts.get("scenes", [])
    scene_data = None
    for scene in scenes:
        if scene.get("scene_number") == scene_number:
            scene_data = scene
            break
    
    if not scene_data:
        raise ValueError(f"Scene {scene_number} not found in scene_prompts.json")
    
    # Determine output path
    if not output_path:
        scene_prompts_file = Path(scene_prompts_path)
        base_name = scene_prompts_file.stem.replace("_scene_prompts", "")
        output_dir = Path("video_outputs") / base_name
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{base_name}_p{scene_number}_veo3.mp4"
    
    # Get API token and set in environment
    try:
        token = get_replicate_token()
        os.environ["REPLICATE_API_TOKEN"] = token
    except ValueError as e:
        print(f"ERROR: {e}")
        sys.exit(1)
    
    print(f"\nGenerating video for Scene {scene_number}...")
    print(f"Output: {output_path}\n")
    
    try:
        generate_sora2_clip(scene_data, first_frame_path, str(output_path))
        print(f"\n✓ Video generation complete: {output_path}")
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

