#!/usr/bin/env python3
"""
Step 0c: Revise Concept Based on Judge Feedback
Takes expanded concept and judge evaluation, produces improved version.
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


def load_template(template_path):
    """Load prompt template from file."""
    with open(template_path, 'r', encoding='utf-8') as f:
        return f.read()


def load_concept_file(file_path):
    """Load concept content from file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read()


def load_evaluation(eval_path):
    """Load evaluation JSON."""
    with open(eval_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_brand_config(config_path):
    """Load brand configuration JSON."""
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def build_revision_prompt(original_concept, evaluation, brand_config, video_settings, template_path):
    """Build the revision prompt with all variables substituted."""
    
    # Load template
    template = load_template(template_path)
    
    # Get video settings
    num_clips = video_settings.get('num_clips', 5)
    clip_duration = video_settings.get('clip_duration', 6)
    total_duration = num_clips * clip_duration
    
    # Extract evaluation details
    total_score = evaluation.get('score', 0)
    strengths = evaluation.get('strengths', [])
    weaknesses = evaluation.get('weaknesses', [])
    
    strengths_text = "\n".join([f"- {s}" for s in strengths])
    weaknesses_text = "\n".join([f"- {w}" for w in weaknesses])
    
    # Substitute variables
    prompt = template.replace('{{original_concept}}', original_concept)
    prompt = prompt.replace('{{total_score}}', str(total_score))
    prompt = prompt.replace('{{strengths}}', strengths_text)
    prompt = prompt.replace('{{weaknesses}}', weaknesses_text)
    
    prompt = prompt.replace('{{num_clips}}', str(num_clips))
    prompt = prompt.replace('{{clip_duration}}', str(clip_duration))
    prompt = prompt.replace('{{total_duration}}', str(total_duration))
    
    # Brand context
    prompt = prompt.replace('{{BRAND_NAME}}', brand_config.get('BRAND_NAME', ''))
    prompt = prompt.replace('{{PRODUCT_DESCRIPTION}}', brand_config.get('PRODUCT_DESCRIPTION', ''))
    prompt = prompt.replace('{{BRAND_VALUES}}', brand_config.get('BRAND_VALUES', ''))
    prompt = prompt.replace('{{TARGET_AUDIENCE}}', brand_config.get('TARGET_AUDIENCE', ''))
    
    # Eyewear specifications
    prompt = prompt.replace('{{FRAME_STYLE}}', 
                           brand_config.get('FRAME_STYLE', 'Determine appropriate style'))
    prompt = prompt.replace('{{LENS_TYPE}}', 
                           brand_config.get('LENS_TYPE', 'Determine appropriate type'))
    prompt = prompt.replace('{{STYLE_PERSONA}}', 
                           brand_config.get('STYLE_PERSONA', 'Determine appropriate persona'))
    prompt = prompt.replace('{{WEARING_OCCASION}}', 
                           brand_config.get('WEARING_OCCASION', 'Various occasions'))
    
    return prompt


def call_llm(prompt, llm_model):
    """Call LLM to revise the concept."""
    
    if "/" in llm_model:
        provider, model = llm_model.split("/", 1)
    else:
        provider = "openai"
        model = llm_model
    
    if provider == "openai":
        return call_openai(prompt, model)
    elif provider == "anthropic":
        return call_anthropic(prompt, model)
    else:
        raise ValueError(f"Unsupported provider: {provider}")


def call_openai(prompt, model):
    """Call OpenAI API."""
    try:
        from openai import OpenAI
    except ImportError:
        raise ImportError("OpenAI package not installed. Run: pip install openai")
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not found in environment")
    
    client = OpenAI(api_key=api_key)
    
    params = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are an elite creative director specializing in eyewear advertising."},
            {"role": "user", "content": prompt}
        ],
    }
    
    if "gpt-5" in model or "o1" in model or "o3" in model:
        params["max_completion_tokens"] = 4000
        params["temperature"] = 1
    else:
        params["max_tokens"] = 4000
        params["temperature"] = 0.7
    
    response = client.chat.completions.create(**params)
    return response.choices[0].message.content


def call_anthropic(prompt, model):
    """Call Anthropic API."""
    try:
        from anthropic import Anthropic
    except ImportError:
        raise ImportError("Anthropic package not installed. Run: pip install anthropic")
    
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not found in environment")
    
    client = Anthropic(api_key=api_key)
    
    response = client.messages.create(
        model=model,
        max_tokens=4000,
        temperature=0.7,
        system="You are an elite creative director specializing in eyewear advertising.",
        messages=[
            {"role": "user", "content": prompt}
        ]
    )
    
    # Extract text from response
    content_parts = []
    for block in response.content:
        if hasattr(block, 'text'):
            content_parts.append(block.text)
    
    return '\n'.join(content_parts)


def revise_concept(concept_file, evaluation_file, brand_config_path, video_settings, llm_model, output_dir):
    """
    Revise concept based on judge feedback.
    
    Args:
        concept_file: Path to expanded concept file
        evaluation_file: Path to evaluation JSON
        brand_config_path: Path to brand config JSON
        video_settings: Dict with num_clips, clip_duration
        llm_model: LLM model to use (format: "provider/model")
        output_dir: Directory to save revised concept
    
    Returns:
        Path to revised concept file
    """
    
    print(f"\n{'='*80}")
    print(f"STEP 0c: REVISE CONCEPT")
    print(f"{'='*80}")
    print(f"LLM Model: {llm_model}")
    print(f"{'='*80}\n")
    
    # Load files
    original_concept = load_concept_file(concept_file)
    evaluation = load_evaluation(evaluation_file)
    brand_config = load_brand_config(brand_config_path)
    
    concept_name = evaluation.get('concept_name', 'concept')
    brand_name = evaluation.get('brand_name', 'Unknown')
    original_score = evaluation.get('score', 0)
    
    print(f"Brand: {brand_name}")
    print(f"Concept: {concept_name}")
    print(f"Original score: {original_score}/100")
    
    print(f"\nWeaknesses to address:")
    for w in evaluation.get('weaknesses', []):
        print(f"  ✗ {w}")
    
    print(f"\nStrengths to maintain:")
    for s in evaluation.get('strengths', []):
        print(f"  ✓ {s}")
    
    # Build revision prompt
    script_dir = Path(__file__).parent
    template_path = script_dir.parent / "inputs" / "prompt_templates" / "revise_concept_template.md"
    
    print(f"\nBuilding revision prompt...")
    prompt = build_revision_prompt(original_concept, evaluation, brand_config, video_settings, template_path)
    
    # Call LLM
    print(f"Calling {llm_model}...")
    revised_concept = call_llm(prompt, llm_model)
    
    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Save revised concept
    output_file = output_path / f"{concept_name}_revised.txt"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(revised_concept)
    
    # Save revision metadata
    revision_metadata = {
        "concept_name": concept_name,
        "brand_name": brand_name,
        "timestamp": datetime.now().isoformat(),
        "llm_model": llm_model,
        "original_file": str(concept_file),
        "evaluation_file": str(evaluation_file),
        "revised_file": str(output_file),
        "original_score": original_score,
        "weaknesses_addressed": evaluation.get('weaknesses', []),
        "strengths_maintained": evaluation.get('strengths', [])
    }
    
    metadata_file = output_path / f"{concept_name}_revision_metadata.json"
    with open(metadata_file, 'w', encoding='utf-8') as f:
        json.dump(revision_metadata, f, indent=2)
    
    print(f"\n{'='*80}")
    print(f"REVISION COMPLETE")
    print(f"{'='*80}")
    print(f"Revised concept: {output_file}")
    print(f"Metadata: {metadata_file}")
    print(f"{'='*80}\n")
    
    return str(output_file), revision_metadata


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python revise_concept.py <concept_file> <evaluation_file> [brand_config] [llm_model] [output_dir]")
        print("\nExample:")
        print("  python revise_concept.py ../outputs/sunvue_1120_1234/sunvue_world_comes_into_focus_expanded.txt ../outputs/sunvue_1120_1234/sunvue_world_comes_into_focus_evaluation.json")
        print("  python revise_concept.py <concept_file> <evaluation_file> ../../s1_generate_concepts/inputs/configs/sunglasses.json anthropic/claude-sonnet-4-5-20250929")
        print("\nDefault brand config: ../../s1_generate_concepts/inputs/configs/sunglasses.json")
        print("Default LLM model: openai/gpt-5.1")
        print("Default output directory: Same as concept file directory")
        sys.exit(1)
    
    concept_file = sys.argv[1]
    evaluation_file = sys.argv[2]
    brand_config_path = sys.argv[3] if len(sys.argv) > 3 else "../../s1_generate_concepts/inputs/configs/sunglasses.json"
    llm_model = sys.argv[4] if len(sys.argv) > 4 else "openai/gpt-5.1"
    output_dir = sys.argv[5] if len(sys.argv) > 5 else str(Path(concept_file).parent)
    
    # Default video settings
    video_settings = {
        "num_clips": 5,
        "clip_duration": 6
    }
    
    if not os.path.exists(concept_file):
        print(f"Error: Concept file not found: {concept_file}")
        sys.exit(1)
    
    if not os.path.exists(evaluation_file):
        print(f"Error: Evaluation file not found: {evaluation_file}")
        sys.exit(1)
    
    if not os.path.exists(brand_config_path):
        print(f"Error: Brand config not found: {brand_config_path}")
        sys.exit(1)
    
    revise_concept(concept_file, evaluation_file, brand_config_path, video_settings, llm_model, output_dir)

