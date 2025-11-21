#!/usr/bin/env python3
"""
Step 0b: Judge Expanded Concept
Evaluates a single expanded concept using the same judge logic from Step 2.
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime

# Add s2_judge_concepts to path to reuse judge functions
script_dir = Path(__file__).parent
project_root = script_dir.parent.parent
s2_scripts = project_root / "s2_judge_concepts" / "scripts"
sys.path.insert(0, str(s2_scripts))

from judge_concepts import (
    create_single_judge_prompt,
    call_judge_llm
)

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def load_concept_file(file_path):
    """Load concept content from file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read()


def load_metadata(metadata_path):
    """Load concept metadata."""
    with open(metadata_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def judge_expanded_concept(concept_file, metadata_file, judge_model, output_dir):
    """
    Judge a single expanded concept using Step 2's judge logic.
    
    Args:
        concept_file: Path to expanded concept file
        metadata_file: Path to metadata JSON
        judge_model: LLM model for judging (format: "provider/model")
        output_dir: Directory to save evaluation
    
    Returns:
        Path to evaluation JSON
    """
    
    print(f"\n{'='*80}")
    print(f"STEP 0b: JUDGE EXPANDED CONCEPT")
    print(f"{'='*80}")
    print(f"Judge Model: {judge_model}")
    print(f"{'='*80}\n")
    
    # Load concept and metadata
    concept_content = load_concept_file(concept_file)
    metadata = load_metadata(metadata_file)
    
    brand_name = metadata.get('brand_name', 'Unknown')
    concept_name = metadata.get('concept_name', 'concept')
    
    print(f"Brand: {brand_name}")
    print(f"Concept: {concept_name}")
    print(f"\nEvaluating concept...")
    
    # Determine ad_style from concept or use generic
    # For direct concepts, we don't have a specific ad_style, so use generic
    ad_style = "Eyewear Advertisement"
    
    # Create judge prompt (reusing Step 2 logic)
    judge_prompt = create_single_judge_prompt(
        ad_style=ad_style,
        brand_name=brand_name,
        concept_content=concept_content,
        model_name="expanded_concept",
        template_name="direct"
    )
    
    # Call judge LLM
    print(f"Calling {judge_model}...")
    response = call_judge_llm(judge_prompt, judge_model)
    
    # Parse JSON response
    if "```json" in response:
        response = response.split("```json")[1].split("```")[0]
    elif "```" in response:
        response = response.split("```")[1].split("```")[0]
    
    evaluation = json.loads(response.strip())
    
    # Add metadata
    evaluation["brand_name"] = brand_name
    evaluation["concept_name"] = concept_name
    evaluation["judge_model"] = judge_model
    evaluation["timestamp"] = datetime.now().isoformat()
    evaluation["concept_file"] = str(concept_file)
    
    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Save evaluation
    eval_file = output_path / f"{concept_name}_evaluation.json"
    with open(eval_file, 'w', encoding='utf-8') as f:
        json.dump(evaluation, f, indent=2)
    
    # Print results
    score = evaluation.get('score', 0)
    strengths = evaluation.get('strengths', [])
    weaknesses = evaluation.get('weaknesses', [])
    explanation = evaluation.get('explanation', '')
    
    print(f"\n{'='*80}")
    print(f"EVALUATION COMPLETE")
    print(f"{'='*80}")
    print(f"Score: {score}/100")
    print(f"\nStrengths:")
    for s in strengths:
        print(f"  ✓ {s}")
    print(f"\nWeaknesses:")
    for w in weaknesses:
        print(f"  ✗ {w}")
    print(f"\nExplanation: {explanation}")
    print(f"\nEvaluation saved: {eval_file}")
    print(f"{'='*80}\n")
    
    return str(eval_file), evaluation


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python judge_concept.py <concept_file> <metadata_file> [judge_model] [output_dir]")
        print("\nExample:")
        print("  python judge_concept.py ../outputs/sunvue_1120_1234/sunvue_world_comes_into_focus_expanded.txt ../outputs/sunvue_1120_1234/sunvue_world_comes_into_focus_metadata.json")
        print("  python judge_concept.py <concept_file> <metadata_file> anthropic/claude-sonnet-4-5-20250929")
        print("\nDefault judge model: anthropic/claude-sonnet-4-5-20250929")
        print("Default output directory: Same as concept file directory")
        sys.exit(1)
    
    concept_file = sys.argv[1]
    metadata_file = sys.argv[2]
    judge_model = sys.argv[3] if len(sys.argv) > 3 else "anthropic/claude-sonnet-4-5-20250929"
    output_dir = sys.argv[4] if len(sys.argv) > 4 else str(Path(concept_file).parent)
    
    if not os.path.exists(concept_file):
        print(f"Error: Concept file not found: {concept_file}")
        sys.exit(1)
    
    if not os.path.exists(metadata_file):
        print(f"Error: Metadata file not found: {metadata_file}")
        sys.exit(1)
    
    judge_expanded_concept(concept_file, metadata_file, judge_model, output_dir)

