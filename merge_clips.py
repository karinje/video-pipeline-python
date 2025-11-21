#!/usr/bin/env python3
"""
Merge video clips (p1, p2, p3, p4, p5) into a single video using FFmpeg.
"""

import subprocess
import sys
from pathlib import Path

def merge_clips(input_dir, output_name=None):
    """
    Merge video clips in order (p1, p2, p3, p4, p5) into a single video.
    
    Args:
        input_dir: Directory containing video clips
        output_name: Output filename (default: same as directory name)
    """
    input_dir = Path(input_dir)
    
    if not input_dir.exists():
        print(f"✗ Error: Directory not found: {input_dir}")
        return False
    
    # Find all video clips - try multiple patterns
    clips = []
    for i in range(1, 6):
        # Try different naming patterns (order matters - most specific first)
        patterns = [
            f"*_p{i}_*.mp4",           # sunvue_..._p1_veo_3_1_fast.mp4
            f"*p{i}*.mp4",              # any file with p1, p2, etc
            f"p{i}_*.mp4",              # p1_*.mp4
            f"*_p{i}.mp4",              # *_p1.mp4
            f"scene_{i}_*.mp4",         # scene_1_*.mp4
            f"*scene{i}*.mp4"           # *scene1*.mp4
        ]
        
        found = False
        for pattern in patterns:
            matches = sorted(list(input_dir.glob(pattern)))
            if matches:
                # Take first match, prefer exact p{i} match
                clip = matches[0]
                clips.append((i, clip))
                found = True
                break
        
        if not found:
            print(f"⚠ Warning: Scene {i} clip not found")
    
    # Sort by scene number and extract just the paths
    clips = [clip for _, clip in sorted(clips, key=lambda x: x[0])]
    
    if len(clips) == 0:
        print(f"✗ Error: No video clips found in {input_dir}")
        return False
    
    print(f"Found {len(clips)} clips to merge:")
    for i, clip in enumerate(clips, 1):
        print(f"  {i}. {clip.name}")
    
    # Determine output filename
    if output_name:
        output_path = input_dir / output_name
    else:
        output_path = input_dir / f"{input_dir.name}.mp4"
    
    # Create temporary file list for FFmpeg concat
    concat_file = input_dir / "concat_list.txt"
    with open(concat_file, 'w') as f:
        for clip in clips:
            # Use absolute path and escape single quotes
            abs_path = clip.resolve()
            f.write(f"file '{abs_path}'\n")
    
    print(f"\n→ Merging clips into: {output_path.name}")
    
    # Use FFmpeg to concatenate
    cmd = [
        "ffmpeg",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_file),
        "-c", "copy",  # Copy streams without re-encoding (fast)
        "-y",  # Overwrite output file
        str(output_path)
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print(f"✓ Successfully merged {len(clips)} clips")
        print(f"✓ Output: {output_path}")
        
        # Clean up temp file
        concat_file.unlink()
        
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ Error merging clips:")
        print(e.stderr)
        return False
    except FileNotFoundError:
        print("✗ Error: ffmpeg not found. Please install FFmpeg.")
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python merge_clips.py <input_directory> [output_filename]")
        print("\nExample:")
        print("  python merge_clips.py s9_generate_video_clips/outputs/sunvue_1120_2021/sunvue_transformation_instant_upgrade_generic_gpt_5.1")
        print("  python merge_clips.py s9_generate_video_clips/outputs/sunvue_1120_2021/sunvue_transformation_instant_upgrade_generic_gpt_5.1 sunvue_final.mp4")
        sys.exit(1)
    
    input_dir = sys.argv[1]
    output_name = sys.argv[2] if len(sys.argv) > 2 else None
    
    success = merge_clips(input_dir, output_name)
    sys.exit(0 if success else 1)

