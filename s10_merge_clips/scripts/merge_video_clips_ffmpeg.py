#!/usr/bin/env python3
"""
Merge multiple video clips into a single final video using ffmpeg.
Takes scene_prompts.json and merges all generated video clips in sequence.
"""

import os
import sys
import json
import subprocess
from pathlib import Path


def merge_video_clips(scene_prompts_path, video_dir=None, output_filename=None, model_suffix="veo3"):
    """
    Merge all video clips for scenes in scene_prompts.json into a single video using ffmpeg.
    
    Args:
        scene_prompts_path: Path to scene_prompts.json
        video_dir: Directory containing video clips (auto-detected if None)
        output_filename: Output filename (auto-generated if None)
        model_suffix: Suffix to identify video files (e.g., "veo3", "sora2")
    """
    print("=" * 80)
    print("VIDEO CLIP MERGER (FFmpeg)")
    print("=" * 80)
    
    # Check if ffmpeg is available
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("ERROR: ffmpeg not found. Please install ffmpeg.")
        sys.exit(1)
    
    # Load scene prompts
    print(f"\nLoading: {scene_prompts_path}")
    with open(scene_prompts_path, 'r', encoding='utf-8') as f:
        scene_prompts = json.load(f)
    
    scenes = scene_prompts.get("scenes", [])
    print(f"Found {len(scenes)} scenes to merge\n")
    
    # Determine video directory and base name
    scene_prompts_file = Path(scene_prompts_path)
    base_name = scene_prompts_file.stem.replace("_scene_prompts", "")
    
    if not video_dir:
        video_dir = Path("video_outputs") / base_name
    else:
        video_dir = Path(video_dir)
    
    if not video_dir.exists():
        raise FileNotFoundError(f"Video directory not found: {video_dir}")
    
    print(f"Video directory: {video_dir}\n")
    
    # Find all video clips in order
    video_files = []
    missing_scenes = []
    
    for scene in sorted(scenes, key=lambda x: x.get("scene_number", 0)):
        scene_num = scene.get("scene_number", 0)
        
        # Try to find video file with model suffix
        video_file = video_dir / f"{base_name}_p{scene_num}_{model_suffix}.mp4"
        
        if not video_file.exists():
            # Try without suffix
            video_file = video_dir / f"{base_name}_p{scene_num}.mp4"
        
        if video_file.exists():
            print(f"  ✓ Scene {scene_num}: {video_file.name}")
            video_files.append(str(video_file))
        else:
            print(f"  ✗ Scene {scene_num}: Video file not found")
            missing_scenes.append(scene_num)
    
    if not video_files:
        raise ValueError("No video clips found to merge")
    
    if missing_scenes:
        print(f"\n⚠ Warning: Missing scenes: {missing_scenes}")
    
    print(f"\nMerging {len(video_files)} clips using ffmpeg...")
    
    # Create concat file for ffmpeg
    concat_file = video_dir / "concat_list.txt"
    with open(concat_file, 'w') as f:
        for video_file in video_files:
            # Use absolute path to avoid path issues
            abs_path = os.path.abspath(video_file)
            # Escape single quotes and special characters for ffmpeg
            escaped_path = abs_path.replace("'", "'\\''")
            f.write(f"file '{escaped_path}'\n")
    
    # Determine output filename
    if not output_filename:
        output_filename = video_dir / f"{base_name}_final_{model_suffix}.mp4"
    else:
        # output_filename is provided - convert to Path and use as-is
        # (it's already a full path from the pipeline script)
        output_filename = Path(output_filename)
    
    # Create output directory if it doesn't exist
    output_filename.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"Output: {output_filename}\n")
    
    # Run ffmpeg concat
    try:
        cmd = [
            "ffmpeg",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_file),
            "-c", "copy",  # Copy streams without re-encoding (faster)
            "-y",  # Overwrite output file
            str(output_filename)
        ]
        
        print(f"Running: {' '.join(cmd)}\n")
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        # Clean up concat file
        concat_file.unlink()
        
        print(f"\n✓ Final video saved: {output_filename}")
        
        # Get video info
        info_cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(output_filename)]
        try:
            duration = subprocess.run(info_cmd, capture_output=True, text=True, check=True).stdout.strip()
            print(f"  Duration: {float(duration):.1f} seconds")
        except:
            pass
        
        return str(output_filename)
        
    except subprocess.CalledProcessError as e:
        # Clean up concat file on error
        if concat_file.exists():
            concat_file.unlink()
        print(f"\n✗ FFmpeg error:")
        print(e.stderr)
        raise


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python merge_video_clips_ffmpeg.py <scene_prompts.json> [video_dir] [output_filename] [model_suffix]")
        print("\nExample:")
        print("  python merge_video_clips_ffmpeg.py script_generation/.../scene_prompts.json")
        print("  python merge_video_clips_ffmpeg.py script_generation/.../scene_prompts.json video_outputs/... final_video.mp4 veo3")
        sys.exit(1)
    
    scene_prompts_path = sys.argv[1]
    video_dir = sys.argv[2] if len(sys.argv) > 2 else None
    output_filename = sys.argv[3] if len(sys.argv) > 3 else None
    model_suffix = sys.argv[4] if len(sys.argv) > 4 else "veo3"
    
    if not os.path.exists(scene_prompts_path):
        print(f"Error: Scene prompts file not found: {scene_prompts_path}")
        sys.exit(1)
    
    try:
        merge_video_clips(scene_prompts_path, video_dir, output_filename, model_suffix)
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

