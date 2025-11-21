#!/usr/bin/env python3
"""
Complete Video Generation Pipeline
Runs all steps from brand config (or evaluation JSON) to final merged video.

Steps:
0. Generate concepts (if start_from='brand_config')
1. Judge/evaluate concepts (if start_from='brand_config')
2. Extract best concept from evaluation
3. Revise script for video timing
4. Generate universe/characters
5. Generate reference images
6. Generate scene prompts
7. Generate first frame images
8. Generate video clips
9. Merge video clips into final video
"""

print("🚀 SCRIPT STARTING - Loading imports...")

import os
import sys
import json
import re
import yaml
import shutil
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import time

# Load environment variables
try:
    from dotenv import load_dotenv
    # Load .env from project root
    env_path = Path(__file__).resolve().parents[2] / ".env"
    load_dotenv(env_path)
except ImportError:
    pass

# Add step directories to path
BASE_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(BASE_DIR / "s0_expand_concept" / "scripts"))
sys.path.insert(0, str(BASE_DIR / "s1_generate_concepts" / "scripts"))
sys.path.insert(0, str(BASE_DIR / "s2_judge_concepts" / "scripts"))
sys.path.insert(0, str(BASE_DIR / "s4_revise_concept" / "scripts"))
sys.path.insert(0, str(BASE_DIR / "s5_generate_universe" / "scripts"))
sys.path.insert(0, str(BASE_DIR / "s6_generate_reference_images" / "scripts"))
sys.path.insert(0, str(BASE_DIR / "s7_generate_scene_prompts" / "scripts"))
sys.path.insert(0, str(BASE_DIR / "s8_generate_first_frames" / "scripts"))
sys.path.insert(0, str(BASE_DIR / "s9_generate_video_clips" / "scripts"))
sys.path.insert(0, str(BASE_DIR / "s10_merge_clips" / "scripts"))

print("✓ Basic imports done, loading pipeline modules...")

# Import pipeline modules
from generate_prompt import generate_prompt, slugify, clean_model_name
from generate_prompt import load_config as load_prompt_config
from execute_llm import execute_llm
from generate_video_script import (
    load_evaluation_json, load_concept_file, load_config_file,
    revise_script_for_video
)
# Import step 0 functions (direct concept)
from expand_concept import expand_concept
from judge_concept import judge_expanded_concept
from revise_concept import revise_concept
# Import step 3 function
sys.path.insert(0, str(BASE_DIR / "s3_extract_best_concept" / "scripts"))
from extract_best_concept import extract_best_concept as extract_best_concept_step3
from generate_universe import generate_universe_and_characters
from generate_scene_prompts import generate_scene_prompts
from generate_universe_images import generate_all_images
from generate_first_frames import generate_all_first_frames
from generate_sora2_clip import generate_sora2_clip
from merge_video_clips_ffmpeg import merge_video_clips
from judge_concepts import judge_batch, load_batch_summary, evaluate_single_concept

print("✓ All imports complete!\n")


def load_pipeline_config(config_path):
    """Load pipeline configuration file (YAML or JSON)."""
    with open(config_path, 'r', encoding='utf-8') as f:
        if config_path.endswith('.yaml') or config_path.endswith('.yml'):
            config = yaml.safe_load(f)
        else:
            config = json.load(f)
    return config


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


def run_single_concept_generation(template_path, config_path, provider, model, 
                                  prompts_dir, concepts_dir,
                                  reasoning_effort=None, thinking=None,
                                  brand_name=None, ad_style=None, template_name=None):
    """Generate a single concept (prompt + LLM call). Returns (prompt_path, concept_path, error)."""
    try:
        # Generate prompt
        model_slug = clean_model_name(model)
        prompt_path = generate_prompt(
            template_path, config_path, prompts_dir,
            brand_name=brand_name, ad_style=ad_style, 
            template_name=template_name, model_name=model_slug
        )
        
        # Execute LLM call
        concept_path = execute_llm(
            prompt_path, provider, model, concepts_dir,
            reasoning_effort=reasoning_effort, thinking=thinking
        )
        
        return prompt_path, concept_path, None
    except Exception as e:
        return None, None, str(e)


def generate_concepts_batch(config_path, creative_direction, ad_styles, templates, models,
                           results_base_dir="results", prompts_base_dir="prompts_history",
                           temp_config_dir="temp_configs", max_workers=8):
    """
    Step 0: Generate concepts for all AD_STYLE/template/model combinations.
    
    Returns:
        (batch_folder_name, batch_summary_path)
    """
    print("=" * 80)
    print("STEP 1: Generate Concepts (Batch)")
    print("=" * 80)
    
    # Load base config
    base_config = load_prompt_config(config_path)
    brand_name = base_config["BRAND_NAME"]
    
    # Create batch folder
    batch_timestamp = datetime.now().strftime("%m%d_%H%M")
    batch_folder_name = f"{brand_name.lower()}_{batch_timestamp}"
    
    # Both results and prompts go to same outputs directory
    # Resolve paths relative to BASE_DIR if not absolute
    if not os.path.isabs(results_base_dir):
        results_base_dir = str(BASE_DIR / results_base_dir)
    results_dir = os.path.join(results_base_dir, batch_folder_name)
    prompts_dir = results_dir  # Prompts saved alongside concepts
    # Clear folder if it exists (for clean regeneration)
    clear_output_folder(results_dir)
    
    print(f"Brand: {brand_name}")
    print(f"Batch Folder: {batch_folder_name}")
    print(f"Creative Direction: {creative_direction}")
    print(f"Total combinations: {len(ad_styles)} styles × {len(templates)} templates × {len(models)} models = {len(ad_styles) * len(templates) * len(models)} runs\n")
    
    results_summary = []
    results_lock = threading.Lock()
    total_runs = len(ad_styles) * len(templates) * len(models)
    completed_runs = 0
    
    # Build tasks
    tasks = []
    for ad_style in ad_styles:
        temp_config = create_temp_config(base_config, ad_style, creative_direction, temp_config_dir)
        
        # Handle both list format [["path", "name"]] and dict format [{"path": "path", "name": "name"}]
        for template_item in templates:
            if isinstance(template_item, dict):
                template_path = template_item.get("path")
                template_name = template_item.get("name")
            else:
                template_path, template_name = template_item[0], template_item[1]
            
            # Resolve template path relative to project root if not absolute
            if not os.path.isabs(template_path):
                template_path = str(BASE_DIR / template_path)
            
            for model_config in models:
                # Handle both list format ["provider", "model", ...] and dict format {"provider": "...", "model": "..."}
                if isinstance(model_config, dict):
                    provider = model_config.get("provider")
                    model = model_config.get("model")
                    reasoning_effort = model_config.get("reasoning_effort")
                    thinking = model_config.get("thinking")
                else:
                    provider = model_config[0]
                    model = model_config[1]
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
    
    print(f"Running {total_runs} tasks in parallel (max {max_workers} concurrent)...\n")
    
    def run_task(task):
        """Run a single concept generation task."""
        start_time = time.time()
        ad_style = task["ad_style"]
        template_name = task["template_name"]
        provider = task["provider"]
        model = task["model"]
        
        task_id = f"{ad_style[:15]}...{template_name[:3]}...{provider[:3]}"
        print(f"  → Started: {task_id}", flush=True)
        
        try:
            prompt_path, concept_path, error = run_single_concept_generation(
                task["template_path"], task["temp_config"], provider, model,
                task["prompts_dir"], task["results_dir"],
                task["reasoning_effort"], task["thinking"],
                task["brand_name"], ad_style, template_name
            )
            
            elapsed = time.time() - start_time
            
            if error:
                print(f"  ✗ Failed: {task_id} ({elapsed:.1f}s) - {error}", flush=True)
                return {
                    "ad_style": ad_style,
                    "template": template_name,
                    "provider": provider,
                    "model": model,
                    "status": "ERROR",
                    "error": error
                }
            else:
                # Save to results with descriptive filename
                brand_slug = slugify(brand_name)
                style_slug = slugify(ad_style)
                model_slug = clean_model_name(model)
                result_filename = f"{brand_slug}_{style_slug}_{template_name}_{model_slug}.txt"
                result_path = os.path.join(results_dir, result_filename)
                
                # Copy concept to results
                if concept_path and os.path.exists(concept_path):
                    with open(concept_path, 'r', encoding='utf-8') as f:
                        concept_content = f.read()
                    with open(result_path, 'w', encoding='utf-8') as f:
                        f.write(concept_content)
                
                print(f"  ✓ Completed: {task_id} ({elapsed:.1f}s)", flush=True)
                
                return {
                    "ad_style": ad_style,
                    "template": template_name,
                    "provider": provider,
                    "model": model,
                    "status": "SUCCESS",
                    "file": result_path,
                    "prompt_file": prompt_path
                }
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"  ✗ Exception: {task_id} ({elapsed:.1f}s) - {str(e)}", flush=True)
            return {
                "ad_style": ad_style,
                "template": template_name,
                "provider": provider,
                "model": model,
                "status": "ERROR",
                "error": str(e)
            }
    
    # Execute in parallel
    batch_start = time.time()
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_task = {executor.submit(run_task, task): task for task in tasks}
        
        for future in as_completed(future_to_task):
            completed_runs += 1
            result = future.result()
            
            with results_lock:
                results_summary.append(result)
            
            if result["status"] == "SUCCESS":
                print(f"[{completed_runs}/{total_runs}] ✓ {os.path.basename(result.get('file', ''))}")
            else:
                print(f"[{completed_runs}/{total_runs}] ✗ {result.get('error', 'Unknown error')}")
    
    batch_elapsed = time.time() - batch_start
    print(f"\n✓ All concept generation completed in {batch_elapsed:.1f}s\n")
    
    # Save batch summary
    summary = {
        "brand_name": brand_name,
        "batch_folder": batch_folder_name,
        "creative_direction": creative_direction,
        "timestamp": datetime.now().isoformat(),
        "total_runs": total_runs,
        "successful": len([r for r in results_summary if r["status"] == "SUCCESS"]),
        "failed": len([r for r in results_summary if r["status"] == "ERROR"]),
        "results": results_summary
    }
    
    summary_filename = f"{brand_name.lower()}_batch_summary_{batch_timestamp}.json"
    summary_path = os.path.join(results_base_dir, batch_folder_name, summary_filename)
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2)
    
    print(f"✓ Batch summary saved: {summary_path}\n")
    
    return batch_folder_name, summary_path




def clear_output_folder(folder_path):
    """
    Delete all contents of a folder if it exists, then recreate the folder.
    Used to ensure clean output when regenerating steps.
    """
    folder = Path(folder_path)
    if folder.exists() and folder.is_dir():
        # Delete all contents
        for item in folder.iterdir():
            if item.is_file():
                item.unlink()
            elif item.is_dir():
                shutil.rmtree(item)
        print(f"  🗑️  Cleared existing folder: {folder}")
    # Ensure folder exists (will create if it doesn't exist)
    folder.mkdir(parents=True, exist_ok=True)


def run_pipeline_complete(config_path="pipeline_config.json"):
    """
    Run the complete video generation pipeline.
    
    Pipeline modes:
    - start_from='direct_concept': Steps 0a/0b/0c → 5-10 (expand concept → optional judge/revise → video)
    - start_from='brand_config': Steps 1-10 (generate concepts → evaluate → video)
    - start_from='evaluation_json': Steps 3-10 (use existing evaluation → video)
    """
    print("=" * 80)
    print("COMPLETE VIDEO GENERATION PIPELINE")
    print("=" * 80)
    pipeline_start_time = time.time()
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Track step times
    step_times = {}
    
    # Load configuration
    print("Loading pipeline configuration...")
    config = load_pipeline_config(config_path)
    print(f"  ✓ Config loaded: {config_path}\n")
    
    # Extract config sections
    mode_cfg = config.get("pipeline_mode", {})
    input_cfg = config.get("input", {})
    output_cfg = config.get("output", {})
    video_cfg = config.get("video_settings", {})
    models_cfg = config.get("models", {})
    image_cfg = config.get("image_generation", {})
    video_gen_cfg = config.get("video_generation", {})
    step_cfg = config.get("pipeline_steps", {})
    concept_cfg = config.get("concept_generation", {})
    eval_cfg = config.get("evaluation", {})
    
    start_from = mode_cfg.get("start_from", "brand_config")
    config_file = input_cfg.get("config_file")
    # Resolve config file path relative to project root
    if not os.path.isabs(config_file):
        config_file = str(BASE_DIR / config_file)
    config_data = load_prompt_config(config_file)  # Use same load_config function
    brand_name = config_data.get("BRAND_NAME", "unknown")
    
    evaluation_path = None
    batch_folder_name = None
    concept_file = None
    concept_content = None
    
    # Step 0: Expand Concept (if starting from direct_concept)
    if start_from == "direct_concept":
        print("=" * 80)
        print("MODE: Direct Concept → Video")
        print("=" * 80)
        print("Steps: 0a (expand) → 0b (judge, optional) → 0c (revise, optional) → 5-10 (video)\n")
        
        # Get concept text
        concept_text = input_cfg.get("direct_concept_text")
        if not concept_text:
            concept_file_input = input_cfg.get("direct_concept_file")
            if concept_file_input:
                with open(concept_file_input, 'r', encoding='utf-8') as f:
                    concept_text = f.read()
            else:
                raise ValueError("direct_concept_text or direct_concept_file required for direct_concept mode")
        
        # Get video settings for expansion
        video_settings = {
            "num_clips": video_cfg.get("num_clips", 5),
            "clip_duration": video_cfg.get("clip_duration", 6)
        }
        
        llm_model = models_cfg.get("llm_model", "openai/gpt-5.1")
        judge_model = eval_cfg.get("judge_model", "anthropic/claude-sonnet-4-5-20250929")
        
        # Step 0a: Expand Concept
        if step_cfg.get("run_concept_expansion", True):
            print("=" * 80)
            print("STEP 0a: Expand Concept")
            print("=" * 80)
            step0a_start = time.time()
            
            output_dir = output_cfg.get("step0_output_dir", "s0_expand_concept/outputs")
            if not os.path.isabs(output_dir):
                output_dir = str(BASE_DIR / output_dir)
            
            expanded_file, metadata = expand_concept(
                concept_text, config_file, video_settings, llm_model, output_dir
            )
            
            concept_file = expanded_file
            concept_content = load_concept_file(concept_file)
            metadata_file = Path(expanded_file).parent / f"{metadata['concept_name']}_metadata.json"
            
            step_times["Step 0a: Expand Concept"] = time.time() - step0a_start
            print(f"  ✓ Expanded concept: {expanded_file}\n")
        else:
            raise ValueError("run_concept_expansion must be true for direct_concept mode")
        
        # Step 0b: Judge Concept (optional)
        evaluation_file = None
        if step_cfg.get("run_concept_judging", True):
            print("=" * 80)
            print("STEP 0b: Judge Expanded Concept")
            print("=" * 80)
            step0b_start = time.time()
            
            output_dir_0b = str(Path(concept_file).parent)
            evaluation_file, evaluation_data = judge_expanded_concept(
                concept_file, str(metadata_file), judge_model, output_dir_0b
            )
            
            step_times["Step 0b: Judge Concept"] = time.time() - step0b_start
            print(f"  ✓ Evaluation: {evaluation_file}\n")
        else:
            print("=" * 80)
            print("STEP 0b: Judge Expanded Concept")
            print("=" * 80)
            print("  ⏭  Skipped (run_concept_judging=false)\n")
            step_times["Step 0b: Judge Concept"] = 0.0
        
        # Step 0c: Revise Concept (optional)
        if step_cfg.get("run_concept_revision", True) and evaluation_file:
            print("=" * 80)
            print("STEP 0c: Revise Concept")
            print("=" * 80)
            step0c_start = time.time()
            
            output_dir_0c = str(Path(concept_file).parent)
            revised_file, revision_metadata = revise_concept(
                concept_file, evaluation_file, config_file, 
                video_settings, llm_model, output_dir_0c
            )
            
            # Use revised concept
            concept_file = revised_file
            concept_content = load_concept_file(concept_file)
            
            step_times["Step 0c: Revise Concept"] = time.time() - step0c_start
            print(f"  ✓ Revised concept: {revised_file}\n")
        else:
            print("=" * 80)
            print("STEP 0c: Revise Concept")
            print("=" * 80)
            if not evaluation_file:
                print("  ⏭  Skipped (no evaluation from Step 0b)\n")
            else:
                print("  ⏭  Skipped (run_concept_revision=false)\n")
            step_times["Step 0c: Revise Concept"] = 0.0
        
        # Set batch folder name and concept name for output organization
        batch_folder_name = Path(concept_file).parent.name
        # Use concept name from metadata (without _revised suffix)
        concept_name = metadata.get('concept_name', Path(concept_file).stem.replace('_revised', ''))
        
        # Skip to Step 5 (universe generation)
        print("=" * 80)
        print("Skipping Steps 1-4 (using direct concept)")
        print("=" * 80)
        print("  ⏭  Step 1: Generate Concepts (not needed)")
        print("  ⏭  Step 2: Judge Concepts (not needed)")
        print("  ⏭  Step 3: Extract Best (not needed)")
        print("  ⏭  Step 4: Revise Concept (done in Step 0c)")
        print()
        
        step_times["Step 1: Generate Concepts"] = 0.0
        step_times["Step 2: Judge/Evaluate Concepts"] = 0.0
        step_times["Step 3: Extract Best Concept"] = 0.0
        step_times["Step 4: Revise Concept"] = 0.0
        
    # Step 1: Generate Concepts (if starting from brand_config)
    elif start_from == "brand_config":
        step1_start = time.time()
        if step_cfg.get("run_step_1", True):
            print("  → Running (run_step_1=true)")
            # Use AD_STYLE from brand config first, fall back to pipeline config's ad_styles list
            brand_ad_style = config_data.get("AD_STYLE")
            if brand_ad_style:
                ad_styles = [brand_ad_style]
                print(f"  → Using AD_STYLE from brand config: {brand_ad_style}")
            else:
                ad_styles = concept_cfg.get("ad_styles", [])
                print(f"  → AD_STYLE not in brand config, using pipeline config: {ad_styles}")
            templates = concept_cfg.get("templates", [])
            models = concept_cfg.get("models", [])
            creative_direction = concept_cfg.get("creative_direction", "")
            max_workers = concept_cfg.get("concept_parallel_workers", 8)
            
            batch_folder_name, batch_summary_path = generate_concepts_batch(
                config_file, creative_direction, ad_styles, templates, models,
                output_cfg.get("results_base_dir", "s1_generate_concepts/outputs"),
                output_cfg.get("prompts_base_dir", "s1_generate_concepts/outputs"),
                max_workers=max_workers
            )
            step_times["Step 1: Generate Concepts"] = time.time() - step1_start
            print(f"  ✓ Batch summary: {batch_summary_path}\n")
        else:
            print("  ⏭  Skipped (run_step_1=false)")
            step_times["Step 1: Generate Concepts"] = 0.0
            # Find existing batch summary
            results_base = Path(output_cfg.get("results_base_dir", "s1_generate_concepts/outputs"))
            batch_folders = sorted([d for d in results_base.iterdir() if d.is_dir() and d.name.startswith(brand_name.lower())], 
                                 key=lambda x: x.stat().st_mtime, reverse=True)
            if batch_folders:
                batch_folder_name = batch_folders[0].name
                summary_files = list(batch_folders[0].glob("*_batch_summary_*.json"))
                if summary_files:
                    batch_summary_path = str(summary_files[0])
                    print(f"  ✓ Using existing batch: {batch_folder_name}\n")
                else:
                    raise FileNotFoundError(f"No batch summary found in {batch_folders[0]}")
            else:
                raise FileNotFoundError("No existing batch found and run_step_1=false")
        
        # Step 2: Judge Concepts
        step2_start = time.time()
        if step_cfg.get("run_step_2", True):
            print("=" * 80)
            print("STEP 2: Judge/Evaluate Concepts")
            print("=" * 80)
            print("  → Running (run_step_2=true)")
            
            judge_model = eval_cfg.get("judge_model", "anthropic/claude-sonnet-4-5-20250929")
            eval_output_dir = eval_cfg.get("evaluation_output_dir", "s2_judge_concepts/outputs")
            # Resolve eval_output_dir relative to BASE_DIR if not absolute
            if not os.path.isabs(eval_output_dir):
                eval_output_dir = str(BASE_DIR / eval_output_dir)
            
            evaluation_path, csv_path = judge_batch(batch_summary_path, judge_model, eval_output_dir)
            step_times["Step 2: Judge/Evaluate Concepts"] = time.time() - step2_start
            print(f"  ✓ Evaluation saved: {evaluation_path}\n")
        else:
            print("=" * 80)
            print("STEP 2: Judge/Evaluate Concepts")
            print("=" * 80)
            print("  ⏭  Skipped (run_step_2=false)")
            step_times["Step 2: Judge/Evaluate Concepts"] = 0.0
            # Find existing evaluation
            eval_dir = Path(eval_cfg.get("evaluation_output_dir", "s2_judge_concepts/outputs"))
            eval_files = sorted([f for f in eval_dir.glob(f"{brand_name.lower()}_evaluation_*.json")],
                              key=lambda x: x.stat().st_mtime, reverse=True)
            if eval_files:
                evaluation_path = str(eval_files[0])
                print(f"  ✓ Using existing evaluation: {evaluation_path}\n")
            else:
                raise FileNotFoundError("No existing evaluation found and run_step_2=false")
    else:
        # Start from evaluation JSON
        evaluation_path = input_cfg.get("evaluation_json")
        if not evaluation_path or not os.path.exists(evaluation_path):
            raise FileNotFoundError(f"Evaluation file not found: {evaluation_path}")
    
    # Step 3: Extract best concept from evaluation (skip if using direct_concept)
    if start_from != "direct_concept":
        print("=" * 80)
        print("STEP 3: Extract Best Concept from Evaluation")
        print("=" * 80)
        step3_start = time.time()
        
        if step_cfg.get("run_step_3", True):
            print(f"  → Running (run_step_3=true)")
            # Use step 3's extract_best_concept function to save output
            step3_output_dir = output_cfg.get("step3_output_dir", "s3_extract_best_concept/outputs")
            # Resolve path relative to BASE_DIR if not absolute
            if not os.path.isabs(step3_output_dir):
                step3_output_dir = str(BASE_DIR / step3_output_dir)
            
            best_concept_metadata_file = extract_best_concept_step3(evaluation_path, step3_output_dir)
            
            # Also load for use in pipeline
            best_concept, best_score = load_evaluation_json(evaluation_path)
            concept_file = best_concept.get("file")
            if not concept_file or not os.path.exists(concept_file):
                raise FileNotFoundError(f"Concept file not found: {concept_file}")
            
            concept_content = load_concept_file(concept_file)
            
            print(f"  ✓ Best concept: {os.path.basename(concept_file)}")
            print(f"  ✓ Score: {best_score}/100")
            print(f"  ✓ Model: {best_concept.get('model')}")
            print(f"  ✓ Template: {best_concept.get('template')}")
            print(f"  ✓ Metadata saved: {best_concept_metadata_file}\n")
            step_times["Step 3: Extract Best Concept"] = time.time() - step3_start
        else:
            print(f"  ⏭  Skipped (run_step_3=false)")
            # Load existing best concept metadata
            # (This would need to be cached somewhere for this to work)
            print(f"  ⚠  Warning: Step 3 skip not fully implemented - always run this step\n")
            best_concept, best_score = load_evaluation_json(evaluation_path)
            concept_file = best_concept.get("file")
            concept_content = load_concept_file(concept_file)
            print(f"  ✓ Using: {os.path.basename(concept_file)} ({best_score}/100)\n")
            step_times["Step 3: Extract Best Concept"] = 0.0
    
    # Determine output directory (concept_file already set from Step 0 if direct_concept mode)
    if batch_folder_name:
        output_base = output_cfg.get("base_output_dir", "s4_revise_concept/outputs")
        # Resolve relative to BASE_DIR if not absolute
        if not os.path.isabs(output_base):
            output_base = str(BASE_DIR / output_base)
        output_base = Path(output_base)
        concept_name = Path(concept_file).stem
        output_dir = output_base / batch_folder_name / concept_name
    else:
        # When steps 1-3 are skipped, extract batch folder from concept file path
        concept_path = Path(concept_file)
        batch_folder_name = concept_path.parent.name  # Extract from concept file path
        output_base = output_cfg.get("base_output_dir", "s4_revise_concept/outputs")
        # Resolve relative to BASE_DIR if not absolute
        if not os.path.isabs(output_base):
            output_base = str(BASE_DIR / output_base)
        output_base = Path(output_base)
        concept_name = Path(concept_file).stem
        output_dir = output_base / batch_folder_name / concept_name
    
    # Step 4: Revise concept based on judge feedback (skip if using direct_concept - already done in Step 0c)
    if start_from != "direct_concept":
        print("=" * 80)
        print("STEP 4: Revise Concept Based on Judge Feedback")
        print("=" * 80)
        step4_start = time.time()
        # Get duration - use total_duration if provided, otherwise legacy duration_seconds
        total_duration = video_cfg.get("total_duration")
        duration = total_duration if total_duration is not None else video_cfg.get("duration_seconds", 30)
        llm_model = models_cfg.get("llm_model", "anthropic/claude-sonnet-4-5-20250929")
        revised_file = output_dir / f"{concept_name}_revised.txt"
        
        # Extract weaknesses from judge evaluation for the best concept
        weaknesses = best_concept.get("weaknesses", [])
        
        if step_cfg.get("run_step_4", True):
            print(f"  → Running (run_step_4=true) - will overwrite if exists")
            clear_output_folder(output_dir)
            print(f"Output directory: {output_dir}\n")
            print(f"  → Addressing {len(weaknesses)} judge weaknesses")
            revised_script = revise_script_for_video(concept_content, config_data, llm_model, duration, weaknesses)
            with open(revised_file, 'w', encoding='utf-8') as f:
                f.write(revised_script)
            print(f"  ✓ Saved: {revised_file}")
            
            # Comparative re-judging: judge sees both concepts side-by-side
            # ALWAYS runs when Step 4 is enabled - no file existence checks, always overwrites
            print(f"  → Comparative judging: comparing original vs revised...")
            judge_model = eval_cfg.get("judge_model", "anthropic/claude-sonnet-4-5-20250929")
            
            # Extract info from best_concept
            ad_style = best_concept.get("ad_style", config_data.get("AD_STYLE", "Unknown"))
            brand_name = best_concept.get("brand_name", config_data.get("BRAND_NAME", "Unknown"))
            original_score = best_concept.get("score", 0)
            weaknesses_addressed = best_concept.get("weaknesses", [])
            
            # Create comparative judging prompt
            comparative_prompt = f"""You are an expert ad concept evaluator. You will compare TWO versions of the same ad concept: ORIGINAL and REVISED.

**CONTEXT:**
- Brand: {brand_name}
- Ad Style: {ad_style}
- The REVISED concept was created to address specific weaknesses in the ORIGINAL
- Your job is to determine if the revision improved the concept

**ORIGINAL CONCEPT (scored {original_score}/100):**
{concept_content}

**WEAKNESSES IDENTIFIED IN ORIGINAL:**
{chr(10).join([f"{i+1}. {w}" for i, w in enumerate(weaknesses_addressed)])}

**REVISED CONCEPT:**
{revised_script}

**YOUR TASK:**
1. Compare both concepts carefully
2. Determine if the REVISED version successfully addresses the weaknesses
3. Evaluate if the revision introduced any NEW weaknesses
4. Score BOTH concepts on the same 0-100 scale
5. Provide a clear explanation of which is better and why

**SCORING CRITERIA (same as original evaluation):**
- Narrative Quality (20 points)
- Emotional Impact (20 points)
- Brand Integration (15 points)
- Memorability (15 points)
- Visual Clarity (15 points)
- Success Likelihood (15 points)

**OUTPUT FORMAT (JSON):**
```json
{{
  "original_score": <0-100>,
  "revised_score": <0-100>,
  "improvement": <positive or negative number>,
  "winner": "original" or "revised",
  "explanation": "Detailed comparison explaining which is better and why",
  "weaknesses_addressed": ["List of weaknesses that were successfully fixed"],
  "new_weaknesses_introduced": ["List of any new problems the revision created"],
  "recommendation": "Use original" or "Use revised" or "Scores too close to call"
}}
```

Be objective and analytical. Small differences (±5 points) mean they're roughly equal."""
            
            # Call judge LLM with comparative prompt
            provider_judge, model_judge = judge_model.split("/", 1) if "/" in judge_model else ("anthropic", judge_model)
            
            print(f"  → Calling {provider_judge}/{model_judge} for comparative judging...")
            print(f"  → This may take 30-90 seconds with extended thinking...")
            
            try:
                if provider_judge == "openai":
                    from execute_llm import call_openai
                    api_key = os.getenv("OPENAI_API_KEY")
                    response = call_openai(comparative_prompt, model_judge, api_key, reasoning_effort="high")
                else:
                    from execute_llm import call_anthropic
                    api_key = os.getenv("ANTHROPIC_API_KEY")
                    # Use proportional thinking: 1024 tokens minimum for revision task (~1k word output)
                    response = call_anthropic(comparative_prompt, model_judge, api_key, thinking=1024)
                
                print(f"  ✓ Comparative judge response received, parsing...")
                
                # Parse JSON response
                if "```json" in response:
                    json_text = response.split("```json")[1].split("```")[0]
                elif "```" in response:
                    json_text = response.split("```")[1].split("```")[0]
                else:
                    json_text = response.strip()
                
                comparison = json.loads(json_text)
                
                revised_evaluation = {
                    "comparison": comparison,
                    "judge_model": judge_model,
                    "method": "comparative"
                }
                
                improvement = comparison.get("improvement", 0)
                revised_score = comparison.get("revised_score", 0)
                
                print(f"  ✓ Original score: {original_score}/100")
                print(f"  ✓ Revised score:  {revised_score}/100")
                print(f"  ✓ Winner: {comparison.get('winner', 'unknown').upper()}")
                if improvement > 0:
                    print(f"  ✓ Improvement: +{improvement} points 🎉")
                elif improvement == 0:
                    print(f"  → No change in score")
                else:
                    print(f"  ⚠ Score decreased: {improvement} points")
                print(f"  → Recommendation: {comparison.get('recommendation', 'N/A')}")
                
            except Exception as e:
                print(f"  ⚠ Comparative judging failed: {str(e)}")
                print(f"  → Skipping score comparison\n")
                revised_evaluation = {"error": str(e), "method": "comparative"}
                improvement = None
            
            # Save re-evaluation result (always overwrite)
            rejudge_file = output_dir / f"{concept_name}_revised_evaluation.json"
            # Explicitly delete if exists to ensure overwrite
            if rejudge_file.exists():
                rejudge_file.unlink()
            with open(rejudge_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "original_evaluation": best_concept,
                    "revised_evaluation": revised_evaluation,
                    "improvement": improvement
                }, f, indent=2)
            print(f"  ✓ Re-evaluation saved: {rejudge_file}")
            
            # Determine which version to use for downstream steps
            # ALWAYS use revised concept when Step 4 runs (it's the output of this step)
            if improvement is not None:
                winner = comparison.get("winner", "original")
                if winner == "revised" and improvement > 0:
                    print(f"  → Using REVISED concept for downstream steps (scored higher)")
                    final_concept = revised_script
                    final_concept_file = revised_file
                elif winner == "revised" or improvement >= 0:
                    print(f"  → Using REVISED concept for downstream steps (Step 4 output)")
                    final_concept = revised_script
                    final_concept_file = revised_file
                else:
                    print(f"  → Using REVISED concept for downstream steps (Step 4 output, despite lower score)")
                    final_concept = revised_script
                    final_concept_file = revised_file
            else:
                # If comparative judging failed, still use revised (it's the output of Step 4)
                print(f"  → Using REVISED concept for downstream steps (Step 4 output)")
                final_concept = revised_script
                final_concept_file = revised_file
            
            print()
            step_times["Step 4: Revise Concept"] = time.time() - step4_start
        else:
            print(f"  ⏭  Skipped (run_step_4=false)")
            step_times["Step 4: Revise Concept"] = 0.0
            # When skipping, check if revised file exists, otherwise use original
            if revised_file.exists():
                with open(revised_file, 'r', encoding='utf-8') as f:
                    final_concept = f.read()
                final_concept_file = revised_file
                print(f"  ✓ Using existing revised: {revised_file}\n")
            else:
                final_concept = concept_content
                final_concept_file = concept_file
                print(f"  ✓ Using original: {concept_file}\n")
    else:
        # direct_concept mode: Step 4 already done in Step 0c
        final_concept = concept_content
        final_concept_file = concept_file
        print("  ✓ Using concept from Step 0 (revision already done in Step 0c if enabled)\n")
    
    # Step 5: Generate universe and characters
    print("=" * 80)
    print("STEP 5: Generate Universe and Characters")
    print("=" * 80)
    step5_start = time.time()
    # Step 5 has its own output directory
    universe_output_base = Path("s5_generate_universe/outputs")
    universe_output_dir = universe_output_base / batch_folder_name / concept_name
    universe_file = universe_output_dir / f"{concept_name}_universe_characters.json"
    
    if step_cfg.get("run_step_5", True):
        print(f"  → Running (run_step_5=true) - will overwrite if exists")
        clear_output_folder(universe_output_dir)
        print(f"  → Input: {Path(final_concept_file).name}")
        # Use llm_thinking from config, default to 1500 for reasonable speed/quality balance
        universe_thinking = models_cfg.get("llm_thinking", 1500)
        universe_chars = generate_universe_and_characters(final_concept, config_data, llm_model, thinking=universe_thinking)
        with open(universe_file, 'w', encoding='utf-8') as f:
            json.dump(universe_chars, f, indent=2)
        step_times["Step 5: Generate Universe"] = time.time() - step5_start
        print(f"  ✓ Saved: {universe_file}\n")
    else:
        print(f"  ⏭  Skipped (run_step_5=false)")
        step_times["Step 5: Generate Universe"] = 0.0
        if universe_file.exists():
            with open(universe_file, 'r', encoding='utf-8') as f:
                universe_chars = json.load(f)
            print(f"  ✓ Using existing: {universe_file}\n")
        else:
            # Create empty structure for skipped step
            universe_chars = {}
            print(f"  ⚠  No existing universe file found (step skipped)\n")
    
    # Step 6: Generate reference images
    print("=" * 80)
    print("STEP 6: Generate Reference Images for Universe/Characters")
    print("=" * 80)
    step6_start = time.time()
    universe_images_base = Path(output_cfg.get("universe_images_dir", "s6_generate_reference_images/outputs"))
    # generate_all_images adds json_prefix (concept_name) to output_base_dir
    # So we pass: {base}/{batch} and it creates: {base}/{batch}/{concept}
    output_base_dir_for_step6 = universe_images_base / batch_folder_name
    # The actual images dir (where summary.json will be) is where generate_all_images creates it
    universe_images_dir = universe_images_base / batch_folder_name / concept_name
    
    if step_cfg.get("run_step_6", True):
        print(f"  → Running (run_step_6=true) - will overwrite if exists")
        clear_output_folder(universe_images_dir)
        generate_all_images(
            str(universe_file),
            str(output_base_dir_for_step6),
            max_workers=image_cfg.get("parallel_workers", 5)
        )
        step_times["Step 6: Generate Reference Images"] = time.time() - step6_start
        print(f"  ✓ Images saved to: {universe_images_dir}\n")
    else:
        print(f"  ⏭  Skipped (run_step_6=false)")
        step_times["Step 6: Generate Reference Images"] = 0.0
        print(f"  ✓ Using existing images: {universe_images_dir}\n")
    
    # Step 7: Generate scene prompts
    print("=" * 80)
    print("STEP 7: Generate Scene Prompts")
    print("=" * 80)
    step7_start = time.time()
    # Step 7 has its own output directory
    scene_prompts_output_base = Path("s7_generate_scene_prompts/outputs")
    scene_prompts_output_dir = scene_prompts_output_base / batch_folder_name / concept_name
    scenes_file = scene_prompts_output_dir / f"{concept_name}_scene_prompts.json"
    
    resolution = video_cfg.get("resolution", "720p")
    image_summary_path = universe_images_dir / "image_generation_summary.json"
    llm_thinking = models_cfg.get("llm_thinking", 0)  # Default to 0 (disabled) for speed
    video_model = models_cfg.get("video_model", "google/veo-3-fast")  # Get video model early for step 7
    
    if step_cfg.get("run_step_7", True):
        print(f"  → Running (run_step_7=true) - will overwrite if exists")
        clear_output_folder(scene_prompts_output_dir)
        # Get flexible duration inputs from config
        clip_duration = video_cfg.get("clip_duration")
        num_clips = video_cfg.get("num_clips")
        total_duration = video_cfg.get("total_duration")
        enable_visual_effects = video_cfg.get("enable_visual_effects", True)  # Default to True if not specified
        # Use total_duration if provided, otherwise use legacy duration
        if total_duration is not None:
            duration = total_duration
        scene_prompts = generate_scene_prompts(
            final_concept, universe_chars, config_data,
            duration, llm_model, resolution,
            str(image_summary_path) if image_summary_path.exists() else None,
            thinking=llm_thinking,
            clip_duration=clip_duration,
            num_clips=num_clips,
            video_model=video_model,
            enable_visual_effects=enable_visual_effects
        )
        with open(scenes_file, 'w', encoding='utf-8') as f:
            json.dump(scene_prompts, f, indent=2)
        step_times["Step 7: Generate Scene Prompts"] = time.time() - step7_start
        print(f"  ✓ Saved: {scenes_file}\n")
    else:
        print(f"  ⏭  Skipped (run_step_7=false)")
        step_times["Step 7: Generate Scene Prompts"] = 0.0
        if scenes_file.exists():
            with open(scenes_file, 'r') as f:
                scene_prompts = json.load(f)
            print(f"  ✓ Using existing: {scenes_file}\n")
        else:
            scene_prompts = {"scenes": []}
            print(f"  ⚠  No existing scene prompts file found (step skipped)\n")
    
    # Step 8: Generate first frames
    print("=" * 80)
    print("STEP 8: Generate First Frame Images")
    print("=" * 80)
    step8_start = time.time()
    first_frames_base = Path(output_cfg.get("first_frames_dir", "s8_generate_first_frames/outputs"))
    # Include batch folder to match reference images location
    first_frames_dir = first_frames_base / batch_folder_name / concept_name
    
    if step_cfg.get("run_step_8", True):
        print(f"  → Running (run_step_8=true) - will overwrite if exists")
        clear_output_folder(first_frames_dir)
        generate_all_first_frames(
            str(scenes_file),
            str(universe_file),
            str(universe_images_dir),
            str(first_frames_dir),
            resolution,
            max_workers=image_cfg.get("image_parallel_workers", 5)
        )
        step_times["Step 8: Generate First Frames"] = time.time() - step8_start
        print(f"  ✓ First frames saved to: {first_frames_dir}\n")
    else:
        print(f"  ⏭  Skipped (run_step_8=false)")
        step_times["Step 8: Generate First Frames"] = 0.0
        print(f"  ✓ Using existing frames: {first_frames_dir}\n")
    
    # Step 9: Generate video clips
    print("=" * 80)
    print("STEP 9: Generate Video Clips")
    print("=" * 80)
    step9_start = time.time()
    # video_model already defined above for step 7
    video_outputs_base = Path(output_cfg.get("video_outputs_dir", "s9_generate_video_clips/outputs"))
    # Include batch folder for consistency
    video_output_dir = video_outputs_base / batch_folder_name / concept_name
    
    # Reconstruct first_frames_dir (same logic as Step 8)
    first_frames_base = Path(output_cfg.get("first_frames_dir", "s8_generate_first_frames/outputs"))
    first_frames_dir = first_frames_base / batch_folder_name / concept_name
    
    # Only get scenes if step 7 ran or file exists
    if step_cfg.get("run_step_7", True) or scenes_file.exists():
        scenes = scene_prompts.get("scenes", [])
    else:
        scenes = []
    
    model_suffix = video_model.split('/')[-1].replace('-', '_')
    
    if step_cfg.get("run_step_9", True):
        print(f"  → Running (run_step_9=true) - PARALLEL EXECUTION")
        clear_output_folder(video_output_dir)
        # Ensure Replicate API token is available
        if not os.getenv("REPLICATE_API_TOKEN") and not os.getenv("REPLICATE_API_KEY"):
            print("  ✗ ERROR: REPLICATE_API_TOKEN or REPLICATE_API_KEY not found in environment")
            print("  Please add to .env file or export as environment variable\n")
            return
        
        # Get aspect ratio from video config (defaults to 16:9)
        aspect_ratio = str(video_cfg.get("aspect_ratio", "16:9"))
        if aspect_ratio not in ["16:9", "9:16", "1:1"]:
            aspect_ratio = "16:9"
        
        # Prepare tasks for parallel execution
        tasks = []
        # Check if first_frames_dir exists before processing
        if not first_frames_dir.exists():
            print(f"  ✗ ERROR: First frames directory not found: {first_frames_dir}")
            print(f"  Please ensure Step 8 completed successfully\n")
            return
        
        for scene in scenes:
            scene_num = scene.get("scene_number", 0)
            # Check for .png first (nano-banana-pro), fallback to .jpg (nano-banana)
            first_frame_path = first_frames_dir / f"{concept_name}_p{scene_num}_first_frame.png"
            if not first_frame_path.exists():
                first_frame_path = first_frames_dir / f"{concept_name}_p{scene_num}_first_frame.jpg"
            
            if not first_frame_path.exists():
                print(f"  ✗ Scene {scene_num}: First frame not found at: {first_frame_path}")
                # List what files actually exist
                existing = list(first_frames_dir.glob(f"*p{scene_num}*"))
                if existing:
                    print(f"    Found similar files: {[f.name for f in existing[:3]]}")
                continue
            
            output_clip = video_output_dir / f"{concept_name}_p{scene_num}_{model_suffix}.mp4"
            tasks.append({
                "scene": scene,
                "scene_num": scene_num,
                "first_frame_path": str(first_frame_path),
                "output_clip": str(output_clip),
                "video_model": video_model,
                "aspect_ratio": aspect_ratio
            })
        
        if len(tasks) == 0:
            print(f"  ✗ ERROR: No valid tasks found. All scenes were skipped.")
            print(f"  First frames directory: {first_frames_dir}")
            print(f"  Concept name: {concept_name}")
            print(f"  Please check that Step 8 completed and files exist.\n")
            return
        
        print(f"  Generating {len(tasks)} video clips in parallel...")
        
        # Execute video generation in parallel
        generated_clips = []
        clips_lock = threading.Lock()
        
        def generate_clip_task(task):
            scene_num = task["scene_num"]
            try:
                generate_sora2_clip(
                    task["scene"],
                    task["first_frame_path"],
                    task["output_clip"],
                    video_model=task["video_model"],
                    aspect_ratio=task["aspect_ratio"]
                )
                with clips_lock:
                    generated_clips.append(task["output_clip"])
                return {"status": "SUCCESS", "scene": scene_num, "output": task["output_clip"]}
            except Exception as e:
                return {"status": "FAILED", "scene": scene_num, "error": str(e)}
        
        # Use ThreadPoolExecutor for parallel execution (max 3 concurrent to avoid API rate limits)
        max_workers = min(3, len(tasks))
        completed = 0
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_task = {executor.submit(generate_clip_task, task): task for task in tasks}
            
            for future in as_completed(future_to_task):
                completed += 1
                result = future.result()
                
                if result["status"] == "SUCCESS":
                    print(f"  [{completed}/{len(tasks)}] ✓ Scene {result['scene']} complete")
                else:
                    print(f"  [{completed}/{len(tasks)}] ✗ Scene {result['scene']} failed: {result['error']}")
        
        step_times["Step 9: Generate Video Clips"] = time.time() - step9_start
        print(f"\n  ✓ Generated {len(generated_clips)}/{len(tasks)} clips in parallel\n")
    else:
        print(f"  ⏭  Skipped (run_step_9=false)")
        step_times["Step 9: Generate Video Clips"] = 0.0
        expected_clips = [
            video_output_dir / f"{concept_name}_p{scene.get('scene_number', 0)}_{model_suffix}.mp4"
            for scene in scenes
        ]
        generated_clips = [str(clip) for clip in expected_clips if clip.exists()]
        print(f"  ✓ Using existing clips: {len(generated_clips)}/{len(scenes)} scenes\n")
    
    # Step 10: Merge video clips
    print("=" * 80)
    print("STEP 10: Merge Video Clips into Final Video")
    print("=" * 80)
    step10_start = time.time()
    
    # Create output directory for merged video (separate from video clips)
    merge_outputs_base = Path(output_cfg.get("merge_outputs_dir", "s10_merge_clips/outputs"))
    merge_output_dir = merge_outputs_base / batch_folder_name / concept_name
    merge_output_dir.mkdir(parents=True, exist_ok=True)
    
    final_video = merge_output_dir / f"{concept_name}_final_{model_suffix}.mp4"
    
    if step_cfg.get("run_step_10", True):
        print(f"  → Running (run_step_10=true)")
        merge_video_clips(
            str(scenes_file),
            str(video_output_dir),
            str(final_video),
            model_suffix
        )
        step_times["Step 10: Merge Video Clips"] = time.time() - step10_start
        print(f"  ✓ Final video: {final_video}\n")
    else:
        print(f"  ⏭  Skipped (run_step_10=false)")
        step_times["Step 10: Merge Video Clips"] = 0.0
        print(f"  ✓ Using existing: {final_video}\n")
    
    # Calculate total time
    pipeline_total_time = time.time() - pipeline_start_time
    
    # Summary
    print("=" * 80)
    print("PIPELINE STEP TIMING SUMMARY")
    print("=" * 80)
    total_time = 0.0
    for step_name in sorted(step_times.keys()):
        step_time = step_times[step_name]
        total_time += step_time
        if step_time == 0.0:
            status = "SKIPPED"
            time_str = "0.0s"
        else:
            status = "COMPLETED"
            if step_time < 60:
                time_str = f"{step_time:.1f}s"
            else:
                time_str = f"{step_time/60:.1f}m ({step_time:.1f}s)"
        print(f"  {step_name:.<50} {status:>10} {time_str:>10}")
    print("=" * 80)
    if total_time < 60:
        print(f"  Total Pipeline Time: {total_time:.1f} seconds")
    else:
        print(f"  Total Pipeline Time: {total_time/60:.1f} minutes ({total_time:.1f} seconds)")
    print("=" * 80)
    print()
    
    print("=" * 80)
    print("PIPELINE COMPLETE")
    print("=" * 80)
    print(f"Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    print("Generated Files:")
    print(f"  - Revised script: {revised_file}")
    print(f"  - Universe/Characters: {universe_file}")
    print(f"  - Scene prompts: {scenes_file}")
    print(f"  - Reference images: {universe_images_dir}")
    print(f"  - First frames: {first_frames_dir}")
    print(f"  - Video clips: {video_output_dir}")
    print(f"  - Final merged video: {final_video}")
    print(f"  - Merge outputs: {merge_output_dir}")
    if batch_folder_name:
        print(f"  - Batch folder: {batch_folder_name}")
    if evaluation_path:
        print(f"  - Evaluation: {evaluation_path}")
    print("=" * 80)
    
    return {
        "revised_script": str(revised_file),
        "universe_characters": str(universe_file),
        "scene_prompts": str(scenes_file),
        "universe_images": str(universe_images_dir),
        "first_frames": str(first_frames_dir),
        "video_clips": str(video_output_dir),
        "final_video": str(final_video),
        "merge_outputs": str(merge_output_dir),
        "batch_folder": batch_folder_name,
        "evaluation": evaluation_path
    }


def main():
    """Main entry point."""
    if len(sys.argv) > 1:
        config_path = sys.argv[1]
    else:
        # Try YAML first, then JSON
        script_dir = Path(__file__).parent
        config_dir = script_dir.parent / "configs"
        if (config_dir / "pipeline_config.yaml").exists():
            config_path = str(config_dir / "pipeline_config.yaml")
        elif (config_dir / "pipeline_config.yml").exists():
            config_path = str(config_dir / "pipeline_config.yml")
        elif (config_dir / "pipeline_config.json").exists():
            config_path = str(config_dir / "pipeline_config.json")
        else:
            # Fallback to root directory
            if os.path.exists("pipeline_config.yaml"):
                config_path = "pipeline_config.yaml"
            elif os.path.exists("pipeline_config.yml"):
                config_path = "pipeline_config.yml"
            else:
                config_path = "pipeline_config.json"
    
    if not os.path.exists(config_path):
        print(f"Error: Config file not found: {config_path}")
        print("\nUsage: python run_pipeline_complete.py [pipeline_config.yaml|pipeline_config.json]")
        print("Default: pipeline_config.yaml (or pipeline_config.json if YAML not found)")
        sys.exit(1)
    
    try:
        run_pipeline_complete(config_path)
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

