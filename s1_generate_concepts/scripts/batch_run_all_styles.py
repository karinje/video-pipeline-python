#!/usr/bin/env python3
"""
Batch Runner: Generate concepts for all AD_STYLE options
Takes a brand config and creative direction, then runs all style combinations
with both templates and multiple models.
"""

import os
import json
import sys
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import time

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # dotenv not installed, will use system environment variables
    pass

from run_single_concept import run_pipeline


# All available AD_STYLE options
# TESTING: Only 1 style for now
ALL_AD_STYLES = [
    #"Humor - Hilarious",  # A - Humor (selected) - TESTING
    # "Humor - Playful",
    # "Humor - Sarcastic/Witty",
    # "Sentiment - Heartwarming",  # B - Sentiment (selected)
    # "Sentiment - Tear-jerking",
    # "Sentiment - Nostalgic",
     "Achievement - Inspirational",  # C - Achievement (selected)
    # "Achievement - Empowering",
    # "Achievement - Understated",
    # "Adventure - Thrilling",  # D - Adventure (selected)
    # "Adventure - Wonder-filled",
    # "Adventure - Epic",
    # "Reversal - Thought-provoking",  # E - Reversal (selected)
    # "Reversal - Mind-blowing",
    # "Reversal - Clever"
]

# Models to test (provider, model_name, reasoning_effort, thinking)
# For GPT-5.1: use reasoning_effort='high' for max thinking
# For Claude: use thinking=True or int (budget_tokens) for extended thinking
# Max thinking for Claude: set high budget_tokens (e.g., 8000-10000)
MODELS = [
    ("openai", "gpt-5.1", "high", None),  # GPT-5.1 with max thinking (reasoning_effort='high')
    ("anthropic", "claude-sonnet-4-5-20250929", None, 10000),  # Claude Sonnet 4.5 (Nov 2025) with max extended thinking (10000 budget_tokens)
]

# Templates to test
TEMPLATES = [
    ("prompt_templates/advanced_structured.md", "advanced"),
    ("prompt_templates/generic_simple.md", "generic"),
]


def slugify(text):
    """Convert text to filename-friendly slug."""
    # Replace spaces, hyphens, slashes with single underscore
    slug = text.lower().replace(" ", "_").replace("-", "_").replace("/", "_")
    # Remove multiple consecutive underscores
    import re
    slug = re.sub(r'_+', '_', slug)
    # Remove leading/trailing underscores
    slug = slug.strip('_')
    return slug


def load_config(config_path):
    """Load brand config."""
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def create_temp_config(base_config, ad_style, creative_direction, temp_dir="temp_configs"):
    """Create temporary config file with specific AD_STYLE and CREATIVE_DIRECTION."""
    os.makedirs(temp_dir, exist_ok=True)
    
    config = base_config.copy()
    config["AD_STYLE"] = ad_style
    config["CREATIVE_DIRECTION"] = creative_direction
    
    # Create filename from brand and style
    brand_slug = slugify(config["BRAND_NAME"])
    style_slug = slugify(ad_style)
    filename = f"{brand_slug}_{style_slug}.json"
    temp_path = os.path.join(temp_dir, filename)
    
    with open(temp_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2)
    
    return temp_path


def run_single_pipeline(template_path, config_path, provider, model, 
                       prompts_dir, concepts_dir,
                       reasoning_effort=None, thinking=None,
                       brand_name=None, ad_style=None, template_name=None):
    """Run pipeline and return output paths."""
    try:
        # Run pipeline (output will show parallel execution)
        prompt_path, concept_path = run_pipeline(
            template_path, config_path, provider, model, 
            prompts_dir, concepts_dir,
            reasoning_effort=reasoning_effort, thinking=thinking,
            brand_name=brand_name, ad_style=ad_style, template_name=template_name
        )
        
        return concept_path, prompt_path, None
        
    except Exception as e:
        return None, None, str(e)


def clean_model_name(model_name):
    """Clean model name for filename - remove dates, standardize format."""
    # Handle Claude model names with dates
    if "claude-sonnet-4-5" in model_name or "claude_sonnet_4_5" in model_name:
        return "claude_sonnet_4.5"
    elif "claude-opus-4" in model_name or "claude_opus_4" in model_name:
        return "claude_opus_4"
    elif "claude-haiku-4-5" in model_name or "claude_haiku_4_5" in model_name:
        return "claude_haiku_4.5"
    # Handle GPT model names
    elif "gpt-5.1" in model_name or "gpt_5_1" in model_name:
        return "gpt_5.1"
    elif "gpt-4o" in model_name:
        return "gpt_4o"
    # Fallback: slugify and remove dates
    model_slug = slugify(model_name)
    # Remove date patterns (YYYYMMDD or YYYY-MM-DD)
    import re
    model_slug = re.sub(r'_\d{8}', '', model_slug)  # Remove _20250929
    model_slug = re.sub(r'_\d{4}_\d{2}_\d{2}', '', model_slug)  # Remove _2025_09_29
    return model_slug


def save_result_to_results_dir(concept_path, brand_name, ad_style, template_name, model_name, results_dir="results"):
    """Copy concept to results directory with descriptive filename."""
    os.makedirs(results_dir, exist_ok=True)
    
    if not concept_path or not os.path.exists(concept_path):
        return None
    
    # Read concept content
    with open(concept_path, 'r', encoding='utf-8') as f:
        concept_content = f.read()
    
    # Create descriptive filename
    brand_slug = slugify(brand_name)
    style_slug = slugify(ad_style)
    model_slug = clean_model_name(model_name)  # Use cleaned model name
    filename = f"{brand_slug}_{style_slug}_{template_name}_{model_slug}.txt"
    result_path = os.path.join(results_dir, filename)
    
    # Write to results directory
    with open(result_path, 'w', encoding='utf-8') as f:
        f.write(concept_content)
    
    return result_path


def batch_run_all_styles(config_path, creative_direction, results_base_dir="results", prompts_base_dir="prompts_history", temp_config_dir="temp_configs"):
    """
    Run all AD_STYLE combinations.
    
    Args:
        config_path: Path to brand config JSON
        creative_direction: Creative direction string (e.g., "Create a 30 second Instagram ad for luxury watches with elegant gold aesthetics")
        results_base_dir: Base directory for results
        prompts_base_dir: Base directory for prompts
        temp_config_dir: Directory for temporary config files
    """
    # Load base config
    base_config = load_config(config_path)
    brand_name = base_config["BRAND_NAME"]
    
    # Create batch-specific subdirectory name: brand_MMDD_HHMM
    from datetime import datetime
    batch_timestamp = datetime.now().strftime("%m%d_%H%M")
    batch_folder_name = f"{brand_name.lower()}_{batch_timestamp}"
    
    # Create batch-specific directories
    results_dir = os.path.join(results_base_dir, batch_folder_name)
    prompts_dir = os.path.join(prompts_base_dir, batch_folder_name)
    os.makedirs(results_dir, exist_ok=True)
    os.makedirs(prompts_dir, exist_ok=True)
    
    print(f"\n{'='*80}")
    print(f"BATCH RUN: {brand_name}")
    print(f"Batch Folder: {batch_folder_name}")
    print(f"Creative Direction: {creative_direction}")
    print(f"Total combinations: {len(ALL_AD_STYLES)} styles × {len(TEMPLATES)} templates × {len(MODELS)} models = {len(ALL_AD_STYLES) * len(TEMPLATES) * len(MODELS)} runs")
    print(f"{'='*80}\n")
    
    results_summary = []
    results_lock = threading.Lock()  # Thread-safe results list
    total_runs = len(ALL_AD_STYLES) * len(TEMPLATES) * len(MODELS)
    completed_runs = 0
    
    # Build all tasks
    tasks = []
    for ad_style in ALL_AD_STYLES:
        # Create temp config for this style
        temp_config = create_temp_config(base_config, ad_style, creative_direction, temp_config_dir)
        
        for template_path, template_name in TEMPLATES:
            for model_config in MODELS:
                provider, model = model_config[0], model_config[1]
                reasoning_effort = model_config[2] if len(model_config) > 2 else None
                thinking = model_config[3] if len(model_config) > 3 else None
                
                tasks.append({
                    "ad_style": ad_style,
                    "temp_config": temp_config,
                    "template_path": template_path,
                    "template_name": template_name,
                    "provider": provider,
                    "model": model,
                    "reasoning_effort": reasoning_effort,
                    "thinking": thinking,
                    "brand_name": brand_name,
                    "results_dir": results_dir,
                    "prompts_dir": prompts_dir
                })
    
    print(f"Running {total_runs} tasks in parallel (max 8 concurrent)...\n")
    
    # Run tasks in parallel using ThreadPoolExecutor
    def run_task(task):
        """Run a single task and return result."""
        start_time = time.time()
        ad_style = task["ad_style"]
        template_name = task["template_name"]
        provider = task["provider"]
        model = task["model"]
        reasoning_effort = task["reasoning_effort"]
        thinking = task["thinking"]
        
        model_display = f"{model}"
        if reasoning_effort:
            model_display += f" (thinking:{reasoning_effort})"
        if thinking:
            model_display += f" (extended-thinking)"
        
        task_id = f"{ad_style[:10]}...{template_name[:3]}...{provider[:3]}"
        print(f"  → Started: {task_id}", flush=True)
        
        try:
            # Run pipeline
            concept_path, prompt_path, error = run_single_pipeline(
                task["template_path"], task["temp_config"], provider, model,
                prompts_dir=task["prompts_dir"], concepts_dir=task["results_dir"],
                reasoning_effort=reasoning_effort, thinking=thinking,
                brand_name=task["brand_name"], ad_style=ad_style, template_name=template_name
            )
            
            elapsed = time.time() - start_time
            print(f"  ✓ Completed: {task_id} ({elapsed:.1f}s)", flush=True)
            
            if error:
                return {
                    "ad_style": ad_style,
                    "template": template_name,
                    "provider": provider,
                    "model": model,
                    "reasoning_effort": reasoning_effort,
                    "thinking": thinking,
                    "status": "ERROR",
                    "error": error,
                    "display": f"{ad_style} | {template_name} | {provider} {model_display}"
                }
            else:
                # Save concept to results directory
                result_path = save_result_to_results_dir(
                    concept_path, task["brand_name"], ad_style, template_name, model, task["results_dir"]
                )
                
                if result_path:
                    return {
                        "ad_style": ad_style,
                        "template": template_name,
                        "provider": provider,
                        "model": model,
                        "reasoning_effort": reasoning_effort,
                        "thinking": thinking,
                        "status": "SUCCESS",
                        "file": result_path,
                        "prompt_file": prompt_path,  # Prompt is already saved in prompts_history with matching name
                        "display": f"{ad_style} | {template_name} | {provider} {model_display}"
                    }
                else:
                    return {
                        "ad_style": ad_style,
                        "template": template_name,
                        "provider": provider,
                        "model": model,
                        "reasoning_effort": reasoning_effort,
                        "thinking": thinking,
                        "status": "NO_OUTPUT",
                        "display": f"{ad_style} | {template_name} | {provider} {model_display}"
                    }
        except Exception as e:
            return {
                "ad_style": ad_style,
                "template": template_name,
                "provider": provider,
                "model": model,
                "reasoning_effort": reasoning_effort,
                "thinking": thinking,
                "status": "ERROR",
                "error": str(e),
                "display": f"{ad_style} | {template_name} | {provider} {model_display}"
            }
    
    # Execute tasks in parallel (max 8 workers to avoid rate limits)
    print("Submitting all tasks to thread pool...")
    batch_start = time.time()
    with ThreadPoolExecutor(max_workers=8) as executor:
        # Submit all tasks at once (they run in parallel)
        future_to_task = {executor.submit(run_task, task): task for task in tasks}
        print(f"✓ {len(future_to_task)} tasks submitted, running in parallel...\n")
        
        # Process results as they complete (not in order)
        for future in as_completed(future_to_task):
            completed_runs += 1
            result = future.result()
            
            # Thread-safe append
            with results_lock:
                results_summary.append(result)
            
            # Print result (results may complete out of order)
            if result["status"] == "ERROR":
                print(f"[{completed_runs}/{total_runs}] {result['display']}... ❌ ERROR: {result.get('error', 'Unknown error')}")
            elif result["status"] == "SUCCESS":
                print(f"[{completed_runs}/{total_runs}] {result['display']}... ✓ Saved: {os.path.basename(result['file'])}")
            else:
                print(f"[{completed_runs}/{total_runs}] {result['display']}... ⚠ No output")
    
    batch_elapsed = time.time() - batch_start
    print(f"\n✓ All tasks completed in {batch_elapsed:.1f}s (parallel execution)\n")
    
    # Ensure results directory exists before saving summary
    os.makedirs(results_dir, exist_ok=True)
    
    # Save summary (format: MMDD_HHMM)
    summary_path = os.path.join(results_dir, f"{slugify(brand_name)}_batch_summary_{datetime.now().strftime('%m%d_%H%M')}.json")
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump({
            "brand": brand_name,
            "creative_direction": creative_direction,
            "total_runs": total_runs,
            "results": results_summary
        }, f, indent=2)
    
    # Print final summary
    print(f"\n{'='*80}")
    print("BATCH RUN COMPLETE")
    print(f"{'='*80}")
    print(f"Total runs: {total_runs}")
    print(f"Successful: {sum(1 for r in results_summary if r['status'] == 'SUCCESS')}")
    print(f"Errors: {sum(1 for r in results_summary if r['status'] == 'ERROR')}")
    print(f"Results saved to: {results_dir}/")
    print(f"Summary saved to: {summary_path}")
    print(f"{'='*80}\n")
    
    # Cleanup temp configs
    import shutil
    if os.path.exists(temp_config_dir):
        shutil.rmtree(temp_config_dir)
        print(f"Cleaned up temporary configs: {temp_config_dir}/")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python batch_run_all_styles.py <config_path> <creative_direction> [results_dir]")
        print("\nExample:")
        print('  python batch_run_all_styles.py configs/rolex.json "Create a 30 second Instagram ad for luxury watches with elegant gold aesthetics"')
        print("\nThis will:")
        print("  - Run all 15 AD_STYLE options")
        print("  - Use both advanced and generic templates")
        print("  - Test multiple models (gpt-5.1, sonnet-4.5, etc.)")
        print("  - Save results with descriptive filenames: brand_adstyle_template_model.txt")
        sys.exit(1)
    
    config_path = sys.argv[1]
    creative_direction = sys.argv[2]
    results_dir = sys.argv[3] if len(sys.argv) > 3 else "results"
    
    if not os.path.exists(config_path):
        print(f"Error: Config file not found: {config_path}")
        sys.exit(1)
    
    batch_run_all_styles(config_path, creative_direction, results_dir)

