#!/usr/bin/env python3
"""
Inspect outputs from a specific pipeline step.
Usage: python inspect_step_outputs.py <step_number> <batch_folder>
"""

import sys
from pathlib import Path
import json

def inspect_step(step_num, batch_folder):
    """Inspect outputs for a specific step."""
    
    step_info = {
        0: {
            "name": "Concept Generation",
            "output_dir": f"s1_generate_concepts/outputs/{batch_folder}",
            "files": ["*_batch_summary_*.json", "*.txt", "*_prompt.txt"]
        },
        1: {
            "name": "Evaluation",
            "output_dir": "s2_judge_concepts/outputs",
            "files": [f"{batch_folder.split('_')[0]}_evaluation_*.json", f"{batch_folder.split('_')[0]}_scores_*.csv"]
        },
        2: {
            "name": "Extract Best Concept",
            "output_dir": "s3_extract_best_concept/outputs",
            "files": [f"*_best_concept.json"]
        },
        3: {
            "name": "Revise Concept",
            "output_dir": f"s4_revise_concept/outputs/{batch_folder}",
            "files": ["*_revised.txt", "*_revised_evaluation.json"]
        },
        4: {
            "name": "Universe Generation",
            "output_dir": f"s5_generate_universe/outputs/{batch_folder}",
            "files": ["*_universe_characters.json"]
        },
        5: {
            "name": "Reference Images",
            "output_dir": f"s6_generate_reference_images/outputs/{batch_folder}",
            "files": ["image_generation_summary.json", "**/*.jpg", "**/*.png"]
        },
        6: {
            "name": "Scene Prompts",
            "output_dir": f"s7_generate_scene_prompts/outputs/{batch_folder}",
            "files": ["*_scene_prompts.json"]
        },
        7: {
            "name": "First Frames",
            "output_dir": f"s8_generate_first_frames/outputs/{batch_folder}",
            "files": ["*_first_frame.jpg", "first_frames_summary.json"]
        },
        8: {
            "name": "Video Clips",
            "output_dir": f"s9_generate_video_clips/outputs/{batch_folder}",
            "files": ["*.mp4", "debug/**/*.txt"]
        },
        9: {
            "name": "Final Video",
            "output_dir": f"s9_generate_video_clips/outputs/{batch_folder}",
            "files": ["*_final_*.mp4"]
        }
    }
    
    if step_num not in step_info:
        print(f"Invalid step number: {step_num}")
        print(f"Valid steps: {list(step_info.keys())}")
        return
    
    info = step_info[step_num]
    print("=" * 80)
    print(f"STEP {step_num}: {info['name']}")
    print("=" * 80)
    print(f"Output directory: {info['output_dir']}\n")
    
    output_path = Path(info['output_dir'])
    if not output_path.exists():
        print(f"✗ Output directory does not exist: {output_path}")
        return
    
    # Find concept name subdirectory if it exists
    subdirs = [d for d in output_path.iterdir() if d.is_dir()]
    if subdirs:
        output_path = subdirs[0]
        print(f"Found subdirectory: {output_path.name}\n")
    
    print("Files found:")
    files_found = []
    for pattern in info['files']:
        if '**' in pattern:
            # Recursive search
            for ext in ['.jpg', '.png', '.json', '.txt', '.mp4']:
                for f in output_path.rglob(f"*{ext}"):
                    if f.is_file():
                        files_found.append(f)
        else:
            for f in output_path.glob(pattern):
                if f.is_file():
                    files_found.append(f)
    
    # Deduplicate
    files_found = list(set(files_found))
    
    if not files_found:
        print("  ✗ No files found")
    else:
        for f in sorted(files_found):
            size = f.stat().st_size
            rel_path = f.relative_to(Path.cwd())
            print(f"  ✓ {rel_path} ({size:,} bytes)")
    
    # Special inspection for JSON files
    json_files = [f for f in files_found if f.suffix == '.json']
    if json_files:
        print("\nJSON file contents:")
        for json_file in json_files[:3]:  # Show first 3
            print(f"\n{json_file.name}:")
            try:
                with open(json_file, 'r') as f:
                    data = json.load(f)
                    print(json.dumps(data, indent=2)[:500] + "..." if len(str(data)) > 500 else json.dumps(data, indent=2))
            except Exception as e:
                print(f"  Error reading: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python inspect_step_outputs.py <step_number> <batch_folder>")
        print("Example: python inspect_step_outputs.py 4 rolex_1117_0203")
        sys.exit(1)
    
    step_num = int(sys.argv[1])
    batch_folder = sys.argv[2]
    inspect_step(step_num, batch_folder)



