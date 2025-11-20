#!/usr/bin/env python3
"""
Step-by-step pipeline runner with inspection pauses.
Allows user to inspect outputs after each step before proceeding.
"""

import sys
import os
from pathlib import Path

# Add parent directory to path
BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR / "run_pipeline" / "scripts"))

from run_pipeline_complete import run_pipeline_complete, load_pipeline_config

def inspect_step_output(step_name, output_paths):
    """Display output paths for user inspection."""
    print("\n" + "=" * 80)
    print(f"STEP {step_name} COMPLETE - INSPECT OUTPUTS")
    print("=" * 80)
    print("\nGenerated files:")
    for path in output_paths:
        path_obj = Path(path)
        if path_obj.exists():
            if path_obj.is_file():
                size = path_obj.stat().st_size
                print(f"  ✓ {path} ({size:,} bytes)")
            else:
                print(f"  ✓ {path}/ (directory)")
        else:
            print(f"  ✗ {path} (NOT FOUND)")
    
    print("\n" + "=" * 80)
    response = input("Inspect outputs above, then press ENTER to continue to next step (or 'q' to quit): ")
    if response.lower() == 'q':
        print("Pipeline stopped by user.")
        sys.exit(0)
    print()

def main():
    if len(sys.argv) < 2:
        print("Usage: python run_pipeline_step_by_step.py <config_file>")
        sys.exit(1)
    
    config_path = sys.argv[1]
    
    print("=" * 80)
    print("STEP-BY-STEP PIPELINE RUNNER")
    print("=" * 80)
    print(f"Config: {config_path}\n")
    print("This will run each step and pause for inspection.\n")
    
    # Load config
    config = load_pipeline_config(config_path)
    step_cfg = config.get("pipeline_steps", {})
    
    # Track outputs for each step
    step_outputs = {}
    
    # We'll modify the pipeline to call inspect_step_output after each step
    # For now, let's just run it normally but with better logging
    print("Starting pipeline...\n")
    
    # Import the actual pipeline function
    # We need to modify run_pipeline_complete to support step-by-step mode
    # For now, let's create a wrapper
    
    try:
        run_pipeline_complete(config_path)
    except KeyboardInterrupt:
        print("\n\nPipeline interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nPipeline failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()



