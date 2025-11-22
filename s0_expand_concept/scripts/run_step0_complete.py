#!/usr/bin/env python3
"""
Step 0 Complete: Run all three sub-steps (0a, 0b, 0c) in sequence.

This script packages:
- Step 0a: Expand Concept
- Step 0b: Judge Expanded Concept  
- Step 0c: Revise Concept Based on Feedback

All steps use the same LLM model (default: Opus 4.1).
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

# Import step functions
from expand_concept import expand_concept
from judge_concept import judge_expanded_concept
from revise_concept import revise_concept


def run_step0_complete(concept_input, brand_config_path, llm_model, output_dir=None, video_settings=None):
    """
    Run complete Step 0 pipeline: expand, judge, and revise.
    
    Args:
        concept_input: High-level concept text or path to concept file
        brand_config_path: Path to brand config JSON
        llm_model: LLM model to use for all steps (format: "provider/model")
        output_dir: Directory to save outputs (default: s0_expand_concept/outputs)
        video_settings: Dict with num_clips, clip_duration (default: 5 clips, 6s each)
    
    Returns:
        Dict with paths to all output files
    """
    
    print(f"\n{'='*80}")
    print(f"STEP 0 COMPLETE: EXPAND → JUDGE → REVISE")
    print(f"{'='*80}")
    print(f"LLM Model: {llm_model} (used for all steps)")
    print(f"{'='*80}\n")
    
    # Default video settings
    if video_settings is None:
        video_settings = {
            "num_clips": 5,
            "clip_duration": 8  # Default to 8 seconds
        }
    
    # Default output directory
    if output_dir is None:
        script_dir = Path(__file__).parent
        output_dir = str(script_dir.parent / "outputs")
    
    # Check if concept_input is a file or text
    concept_path = Path(concept_input)
    if concept_path.exists() and concept_path.is_file():
        print(f"Reading concept from file: {concept_path}")
        with open(concept_path, 'r', encoding='utf-8') as f:
            concept_text = f.read().strip()
    else:
        concept_text = concept_input
    
    # Step 0a: Expand Concept
    print(f"\n{'#'*80}")
    print(f"# STEP 0a: EXPAND CONCEPT")
    print(f"{'#'*80}\n")
    
    expanded_file, metadata = expand_concept(
        concept_text, 
        brand_config_path, 
        video_settings, 
        llm_model, 
        output_dir
    )
    
    expanded_file = Path(expanded_file)
    metadata_file = expanded_file.parent / f"{metadata['concept_name']}_metadata.json"
    
    # Step 0b: Judge Expanded Concept
    print(f"\n{'#'*80}")
    print(f"# STEP 0b: JUDGE EXPANDED CONCEPT")
    print(f"{'#'*80}\n")
    
    evaluation_file, evaluation_data = judge_expanded_concept(
        str(expanded_file),
        str(metadata_file),
        llm_model,  # Use same model for judging
        str(expanded_file.parent)
    )
    
    evaluation_file = Path(evaluation_file)
    original_score = evaluation_data.get('score', 0)
    
    # Step 0c: Revise Concept
    print(f"\n{'#'*80}")
    print(f"# STEP 0c: REVISE CONCEPT")
    print(f"{'#'*80}\n")
    
    revised_file, revision_metadata = revise_concept(
        str(expanded_file),
        str(evaluation_file),
        brand_config_path,
        video_settings,
        llm_model,  # Use same model for revision
        str(expanded_file.parent)
    )
    
    revised_file = Path(revised_file)
    
    # Summary
    print(f"\n{'='*80}")
    print(f"STEP 0 COMPLETE - SUMMARY")
    print(f"{'='*80}")
    print(f"Original Score: {original_score}/100")
    print(f"\nOutput Files:")
    print(f"  ✓ Expanded: {expanded_file}")
    print(f"  ✓ Evaluation: {evaluation_file}")
    print(f"  ✓ Revised: {revised_file}")
    print(f"\nOutput Directory: {expanded_file.parent}")
    print(f"{'='*80}\n")
    
    return {
        "expanded_file": str(expanded_file),
        "metadata_file": str(metadata_file),
        "evaluation_file": str(evaluation_file),
        "revised_file": str(revised_file),
        "original_score": original_score,
        "output_dir": str(expanded_file.parent)
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python run_step0_complete.py <concept_text_or_file> [brand_config] [llm_model] [output_dir] [--num-clips N] [--clip-duration N]")
        print("\nExample:")
        print('  python run_step0_complete.py "The World Comes Into Focus..." ../../s1_generate_concepts/inputs/configs/sunglasses.json')
        print('  python run_step0_complete.py inputs/concepts/world_comes_into_focus.txt ../../s1_generate_concepts/inputs/configs/sunglasses.json anthropic/claude-opus-4-1-20250805')
        print('  python run_step0_complete.py inputs/concepts/world_comes_into_focus.txt ../../s1_generate_concepts/inputs/configs/sunglasses.json --num-clips 4 --clip-duration 8')
        print("\nDefault brand config: ../../s1_generate_concepts/inputs/configs/sunglasses.json")
        print("Default LLM model: anthropic/claude-opus-4-1-20250805")
        print("Default output directory: ../outputs (resolves to s0_expand_concept/outputs/)")
        print("Default video settings: num_clips=5, clip_duration=8 seconds")
        sys.exit(1)
    
    concept_input = sys.argv[1]
    brand_config_path = "../../s1_generate_concepts/inputs/configs/sunglasses.json"
    llm_model = "anthropic/claude-opus-4-1-20250805"
    output_dir = None
    num_clips = 5
    clip_duration = 8
    
    # Parse arguments (positional and optional flags)
    i = 2
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == '--num-clips' and i + 1 < len(sys.argv):
            num_clips = int(sys.argv[i + 1])
            i += 2
        elif arg == '--clip-duration' and i + 1 < len(sys.argv):
            clip_duration = int(sys.argv[i + 1])
            i += 2
        elif arg.startswith('--'):
            i += 1
        else:
            # Positional arguments
            if brand_config_path == "../../s1_generate_concepts/inputs/configs/sunglasses.json" and os.path.exists(arg):
                brand_config_path = arg
            elif llm_model == "anthropic/claude-opus-4-1-20250805" and not os.path.exists(arg):
                llm_model = arg
            elif output_dir is None:
                output_dir = arg
            i += 1
    
    # Build video_settings
    video_settings = {
        "num_clips": num_clips,
        "clip_duration": clip_duration
    }
    
    if not os.path.exists(brand_config_path):
        print(f"Error: Brand config not found: {brand_config_path}")
        sys.exit(1)
    
    results = run_step0_complete(concept_input, brand_config_path, llm_model, output_dir, video_settings)
    
    print("\n✓ Step 0 complete! All files saved.")
    print(f"  Final revised concept: {results['revised_file']}")

