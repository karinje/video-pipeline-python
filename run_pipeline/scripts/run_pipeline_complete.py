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

import os
import sys
import json
import re
import yaml
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import time

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Add step directories to path
BASE_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(BASE_DIR / "s1_generate_concepts" / "scripts"))
sys.path.insert(0, str(BASE_DIR / "s2_judge_concepts" / "scripts"))
sys.path.insert(0, str(BASE_DIR / "s4_revise_script" / "scripts"))
sys.path.insert(0, str(BASE_DIR / "s6_generate_reference_images" / "scripts"))
sys.path.insert(0, str(BASE_DIR / "s8_generate_first_frames" / "scripts"))
sys.path.insert(0, str(BASE_DIR / "s9_generate_video_clips" / "scripts"))
sys.path.insert(0, str(BASE_DIR / "s10_merge_clips" / "scripts"))

# Import pipeline modules
from generate_prompt import generate_prompt, slugify, clean_model_name
from generate_prompt import load_config as load_prompt_config
from execute_llm import execute_llm
from generate_video_script import (
    load_evaluation_json, load_concept_file, load_config_file,
    revise_script_for_video, generate_universe_and_characters,
    generate_scene_prompts
)
from generate_universe_images import generate_all_element_images
from generate_first_frames import generate_all_first_frames
from generate_sora2_clip import generate_sora2_clip
from merge_video_clips_ffmpeg import merge_video_clips
from judge_concepts import judge_batch, load_batch_summary


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
    print("STEP 0: Generate Concepts (Batch)")
    print("=" * 80)
    
    # Load base config
    base_config = load_prompt_config(config_path)
    brand_name = base_config["BRAND_NAME"]
    
    # Create batch folder
    batch_timestamp = datetime.now().strftime("%m%d_%H%M")
    batch_folder_name = f"{brand_name.lower()}_{batch_timestamp}"
    
    # Both results and prompts go to same outputs directory
    results_dir = os.path.join(results_base_dir, batch_folder_name)
    prompts_dir = results_dir  # Prompts saved alongside concepts
    os.makedirs(results_dir, exist_ok=True)
    os.makedirs(prompts_dir, exist_ok=True)
    
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


def run_pipeline_complete(config_path="pipeline_config.json"):
    """
    Run the complete video generation pipeline.
    
    Pipeline modes:
    - start_from='brand_config': Steps 0-9 (generate concepts → evaluate → video)
    - start_from='evaluation_json': Steps 2-9 (use existing evaluation → video)
    """
    print("=" * 80)
    print("COMPLETE VIDEO GENERATION PIPELINE")
    print("=" * 80)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
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
    advanced_cfg = config.get("advanced", {})
    concept_cfg = config.get("concept_generation", {})
    eval_cfg = config.get("evaluation", {})
    
    start_from = mode_cfg.get("start_from", "brand_config")
    config_file = input_cfg.get("config_file")
    config_data = load_prompt_config(config_file)  # Use same load_config function
    brand_name = config_data.get("BRAND_NAME", "unknown")
    
    evaluation_path = None
    batch_folder_name = None
    
    # Step 0: Generate Concepts (if starting from brand_config)
    if start_from == "brand_config":
        if not mode_cfg.get("skip_concept_generation", False):
            ad_styles = concept_cfg.get("ad_styles", [])
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
            print(f"  ✓ Batch summary: {batch_summary_path}\n")
        else:
            # Find existing batch summary
            results_base = Path(output_cfg.get("results_base_dir", "s1_generate_concepts/outputs"))
            batch_folders = sorted([d for d in results_base.iterdir() if d.is_dir() and d.name.startswith(brand_name.lower())], 
                                 key=lambda x: x.stat().st_mtime, reverse=True)
            if batch_folders:
                batch_folder_name = batch_folders[0].name
                summary_files = list(batch_folders[0].glob("*_batch_summary_*.json"))
                if summary_files:
                    batch_summary_path = str(summary_files[0])
                    print(f"  ⚠ Using existing batch: {batch_folder_name}\n")
                else:
                    raise FileNotFoundError(f"No batch summary found in {batch_folders[0]}")
            else:
                raise FileNotFoundError("No existing batch found and skip_concept_generation=True")
        
        # Step 1: Judge Concepts
        if not mode_cfg.get("skip_evaluation", False):
            print("=" * 80)
            print("STEP 1: Judge/Evaluate Concepts")
            print("=" * 80)
            
            judge_model = eval_cfg.get("judge_model", "anthropic/claude-sonnet-4-5-20250929")
            eval_output_dir = eval_cfg.get("evaluation_output_dir", "s2_judge_concepts/outputs")
            
            evaluation_path = judge_batch(batch_summary_path, judge_model, eval_output_dir)
            print(f"  ✓ Evaluation saved: {evaluation_path}\n")
        else:
            # Find existing evaluation
            eval_dir = Path(eval_cfg.get("evaluation_output_dir", "s2_judge_concepts/outputs"))
            eval_files = sorted([f for f in eval_dir.glob(f"{brand_name.lower()}_evaluation_*.json")],
                              key=lambda x: x.stat().st_mtime, reverse=True)
            if eval_files:
                evaluation_path = str(eval_files[0])
                print(f"  ⚠ Using existing evaluation: {evaluation_path}\n")
            else:
                raise FileNotFoundError("No existing evaluation found and skip_evaluation=True")
    else:
        # Start from evaluation JSON
        evaluation_path = input_cfg.get("evaluation_json")
        if not evaluation_path or not os.path.exists(evaluation_path):
            raise FileNotFoundError(f"Evaluation file not found: {evaluation_path}")
    
    # Step 2: Extract best concept from evaluation
    print("=" * 80)
    print("STEP 2: Extract Best Concept from Evaluation")
    print("=" * 80)
    
    best_concept, best_score = load_evaluation_json(evaluation_path)
    concept_file = best_concept.get("file")
    if not concept_file or not os.path.exists(concept_file):
        raise FileNotFoundError(f"Concept file not found: {concept_file}")
    
    concept_content = load_concept_file(concept_file)
    
    print(f"  ✓ Best concept: {os.path.basename(concept_file)}")
    print(f"  ✓ Score: {best_score}/100")
    print(f"  ✓ Model: {best_concept.get('model')}")
    print(f"  ✓ Template: {best_concept.get('template')}\n")
    
    # Determine output directory
    if batch_folder_name:
        output_base = Path(output_cfg.get("base_output_dir", "s4_revise_script/outputs"))
        concept_name = Path(concept_file).stem
        output_dir = output_base / batch_folder_name / concept_name
    else:
        evaluation_file = Path(evaluation_path)
        batch_folder = evaluation_file.stem.replace("_evaluation", "").replace("evaluation_", "")
        timestamp = datetime.now().strftime("%m%d_%H%M")
        batch_folder = f"{brand_name.lower()}_{timestamp}"
        output_base = Path(output_cfg.get("base_output_dir", "s4_revise_script/outputs"))
        concept_name = Path(concept_file).stem
        output_dir = output_base / batch_folder / concept_name
    
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Output directory: {output_dir}\n")
    
    # Step 3: Revise script for video
    print("=" * 80)
    print("STEP 3: Revise Script for Video Generation")
    print("=" * 80)
    duration = video_cfg.get("duration_seconds", 30)
    llm_model = models_cfg.get("llm_model", "anthropic/claude-sonnet-4-5-20250929")
    
    revised_script = revise_script_for_video(concept_content, config_data, llm_model, duration)
    revised_file = output_dir / f"{concept_name}_revised.txt"
    with open(revised_file, 'w', encoding='utf-8') as f:
        f.write(revised_script)
    print(f"  ✓ Saved: {revised_file}\n")
    
    # Step 4: Generate universe and characters
    print("=" * 80)
    print("STEP 4: Generate Universe and Characters")
    print("=" * 80)
    universe_chars = generate_universe_and_characters(revised_script, config_data, llm_model)
    universe_file = output_dir / f"{concept_name}_universe_characters.json"
    with open(universe_file, 'w', encoding='utf-8') as f:
        json.dump(universe_chars, f, indent=2)
    print(f"  ✓ Saved: {universe_file}\n")
    
    # Step 5: Generate reference images
    print("=" * 80)
    print("STEP 5: Generate Reference Images for Universe/Characters")
    print("=" * 80)
    universe_images_base = Path(output_cfg.get("universe_images_dir", "s6_generate_reference_images/outputs"))
    universe_images_dir = universe_images_base / concept_name
    
    if advanced_cfg.get("skip_image_generation", False) and universe_images_dir.exists():
        print(f"  ⚠ Skipping image generation (images already exist)\n")
    else:
        generate_all_element_images(
            str(universe_file),
            str(universe_images_dir),
            max_workers=image_cfg.get("image_parallel_workers", 5)
        )
        print(f"  ✓ Images saved to: {universe_images_dir}\n")
    
    # Step 6: Generate scene prompts
    print("=" * 80)
    print("STEP 6: Generate Scene Prompts")
    print("=" * 80)
    resolution = video_cfg.get("resolution", "720p")
    image_summary_path = universe_images_dir / "image_generation_summary.json"
    
    scenes_file = output_dir / f"{concept_name}_scene_prompts.json"
    if not advanced_cfg.get("regenerate_scene_prompts", False) and scenes_file.exists():
        print(f"  ⚠ Scene prompts already exist, loading...\n")
        with open(scenes_file, 'r') as f:
            scene_prompts = json.load(f)
    else:
        scene_prompts = generate_scene_prompts(
            revised_script, universe_chars, config_data,
            duration, llm_model, resolution,
            str(image_summary_path) if image_summary_path.exists() else None
        )
        with open(scenes_file, 'w', encoding='utf-8') as f:
            json.dump(scene_prompts, f, indent=2)
        print(f"  ✓ Saved: {scenes_file}\n")
    
    # Step 7: Generate first frames
    print("=" * 80)
    print("STEP 7: Generate First Frame Images")
    print("=" * 80)
    first_frames_base = Path(output_cfg.get("first_frames_dir", "s8_generate_first_frames/outputs"))
    first_frames_dir = first_frames_base / concept_name
    
    if advanced_cfg.get("skip_first_frames", False) and first_frames_dir.exists():
        print(f"  ⚠ Skipping first frame generation (frames already exist)\n")
    else:
        generate_all_first_frames(
            str(scenes_file),
            str(universe_file),
            str(universe_images_dir),
            str(first_frames_dir),
            resolution,
            max_workers=image_cfg.get("image_parallel_workers", 5)
        )
        print(f"  ✓ First frames saved to: {first_frames_dir}\n")
    
    # Step 8: Generate video clips
    print("=" * 80)
    print("STEP 8: Generate Video Clips")
    print("=" * 80)
    video_model = models_cfg.get("video_model", "google/veo-3-fast")
    video_outputs_base = Path(output_cfg.get("video_outputs_dir", "s9_generate_video_clips/outputs"))
    video_output_dir = video_outputs_base / concept_name
    
    scenes = scene_prompts.get("scenes", [])
    generated_clips = []
    
    if advanced_cfg.get("skip_video_clips", False):
        print(f"  ⚠ Skipping video clip generation (clips may already exist)\n")
    else:
        for scene in scenes:
            scene_num = scene.get("scene_number", 0)
            first_frame_path = first_frames_dir / f"{concept_name}_p{scene_num}_first_frame.jpg"
            
            if not first_frame_path.exists():
                print(f"  ✗ Scene {scene_num}: First frame not found, skipping")
                continue
            
            model_suffix = video_model.split('/')[-1].replace('-', '_')
            output_clip = video_output_dir / f"{concept_name}_p{scene_num}_{model_suffix}.mp4"
            
            if output_clip.exists() and not advanced_cfg.get("regenerate_scene_prompts", False):
                print(f"  ⚠ Scene {scene_num}: Clip already exists, skipping")
                continue
            
            print(f"  Generating Scene {scene_num}...")
            try:
                generate_sora2_clip(scene, str(first_frame_path), str(output_clip))
                generated_clips.append(str(output_clip))
                print(f"    ✓ Scene {scene_num} complete\n")
            except Exception as e:
                print(f"    ✗ Scene {scene_num} failed: {e}\n")
    
    # Step 9: Merge video clips
    print("=" * 80)
    print("STEP 9: Merge Video Clips into Final Video")
    print("=" * 80)
    model_suffix = video_model.split('/')[-1].replace('-', '_')
    final_video = video_output_dir / f"{concept_name}_final_{model_suffix}.mp4"
    
    merge_video_clips(
        str(scenes_file),
        str(video_output_dir),
        str(final_video),
        model_suffix
    )
    print(f"  ✓ Final video: {final_video}\n")
    
    # Summary
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
    print(f"  - Final video: {final_video}")
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

