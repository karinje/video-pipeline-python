#!/usr/bin/env python3
"""
Extract Best Concept from Evaluation
Takes evaluation JSON and extracts the highest-scoring concept.
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime


def load_evaluation_json(evaluation_path):
    """
    Load evaluation JSON and find best scoring concept.
    
    Args:
        evaluation_path: Path to evaluation JSON file
    
    Returns:
        (best_concept_dict, best_score) tuple
    """
    print(f"Loading evaluation: {evaluation_path}")
    
    with open(evaluation_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    best_concept = None
    best_score = -1
    best_ad_style = None
    best_brand_name = None
    
    # Get brand name from summary
    brand_name = data.get("summary", {}).get("brand", "")
    
    for eval_group in data.get("evaluations", []):
        ad_style = eval_group.get("ad_style", "")
        group_brand = eval_group.get("brand_name", brand_name)
        for eval_item in eval_group.get("evaluations", []):
            score = eval_item.get("score", 0)
            if score > best_score:
                best_score = score
                best_concept = eval_item.copy()  # Make a copy to avoid modifying original
                best_ad_style = ad_style
                best_brand_name = group_brand
    
    if not best_concept:
        raise ValueError("No concepts found in evaluation file")
    
    # Add metadata to best_concept if not already present
    if best_ad_style and "ad_style" not in best_concept:
        best_concept["ad_style"] = best_ad_style
    if best_brand_name and "brand_name" not in best_concept:
        best_concept["brand_name"] = best_brand_name
    
    return best_concept, best_score


def extract_best_concept(evaluation_path, output_dir=None):
    """
    Extract best concept from evaluation and save metadata.
    
    Args:
        evaluation_path: Path to evaluation JSON
        output_dir: Directory to save best concept metadata (auto-detected if None)
    
    Returns:
        Path to best concept metadata JSON
    """
    print("=" * 80)
    print("EXTRACT BEST CONCEPT FROM EVALUATION")
    print("=" * 80)
    print()
    
    # Load evaluation and find best concept
    best_concept, best_score = load_evaluation_json(evaluation_path)
    
    # Display results
    print(f"✓ Best concept found:")
    print(f"  - File: {best_concept.get('file')}")
    print(f"  - Score: {best_score}/100")
    print(f"  - Model: {best_concept.get('model')}")
    print(f"  - Template: {best_concept.get('template')}")
    print()
    
    # Determine output directory
    if not output_dir:
        eval_file = Path(evaluation_path)
        # Use same directory as evaluation file
        output_dir = eval_file.parent
    else:
        output_dir = Path(output_dir)
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Create metadata file
    metadata = {
        "evaluation_file": str(evaluation_path),
        "extracted_at": datetime.now().isoformat(),
        "best_concept": {
            "file": best_concept.get("file"),
            "score": best_score,
            "model": best_concept.get("model"),
            "template": best_concept.get("template"),
            "provider": best_concept.get("provider", ""),
            "ad_style": best_concept.get("ad_style", ""),
            "brand_name": best_concept.get("brand_name", ""),
            "strengths": best_concept.get("strengths", []),
            "weaknesses": best_concept.get("weaknesses", []),
            "explanation": best_concept.get("explanation", "")
        }
    }
    
    # Save metadata
    eval_basename = Path(evaluation_path).stem.replace("_evaluation", "")
    output_file = output_dir / f"{eval_basename}_best_concept.json"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"✓ Best concept metadata saved: {output_file}")
    print()
    
    return str(output_file)


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python extract_best_concept.py <evaluation_json> [output_dir]")
        print()
        print("Example:")
        print("  python extract_best_concept.py s2_judge_concepts/outputs/rolex_evaluation_claude_4.5_1117_0205.json")
        sys.exit(1)
    
    evaluation_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None
    
    if not os.path.exists(evaluation_path):
        print(f"Error: Evaluation file not found: {evaluation_path}")
        sys.exit(1)
    
    try:
        output_file = extract_best_concept(evaluation_path, output_dir)
        print("=" * 80)
        print("SUCCESS")
        print("=" * 80)
        print(f"Best concept metadata: {output_file}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

