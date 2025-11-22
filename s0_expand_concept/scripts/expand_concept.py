#!/usr/bin/env python3
"""
Step 0a: Expand Concept
Takes a high-level ad concept and expands it into a detailed scene-by-scene narrative.
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


def load_brand_config(config_path):
    """Load brand configuration JSON."""
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def build_expand_prompt(concept_text, brand_config, video_settings, template_path):
    """Build the expansion prompt with all variables substituted."""
    
    # Load template
    template = load_template(template_path)
    
    # Get video settings
    num_clips = video_settings.get('num_clips', 5)
    clip_duration = video_settings.get('clip_duration', 6)
    total_duration = num_clips * clip_duration
    
    # Substitute all variables
    prompt = template.replace('{{concept_text}}', concept_text)
    prompt = prompt.replace('{{num_clips}}', str(num_clips))
    prompt = prompt.replace('{{clip_duration}}', str(clip_duration))
    prompt = prompt.replace('{{total_duration}}', str(total_duration))
    
    # Brand context
    prompt = prompt.replace('{{BRAND_NAME}}', brand_config.get('BRAND_NAME', ''))
    prompt = prompt.replace('{{PRODUCT_DESCRIPTION}}', brand_config.get('PRODUCT_DESCRIPTION', ''))
    prompt = prompt.replace('{{BRAND_VALUES}}', brand_config.get('BRAND_VALUES', ''))
    prompt = prompt.replace('{{VALUE_PROPOSITION}}', brand_config.get('VALUE_PROPOSITION', ''))
    prompt = prompt.replace('{{BRAND_PERSONALITY}}', brand_config.get('BRAND_PERSONALITY', ''))
    prompt = prompt.replace('{{TARGET_AUDIENCE}}', brand_config.get('TARGET_AUDIENCE', ''))
    prompt = prompt.replace('{{AD_STYLE}}', brand_config.get('AD_STYLE', ''))
    prompt = prompt.replace('{{CREATIVE_DIRECTION}}', brand_config.get('CREATIVE_DIRECTION', ''))
    
    # Eyewear specifications (with fallback text)
    prompt = prompt.replace('{{FRAME_STYLE}}', 
                           brand_config.get('FRAME_STYLE', 'Determine appropriate style based on concept'))
    prompt = prompt.replace('{{LENS_TYPE}}', 
                           brand_config.get('LENS_TYPE', 'Determine appropriate type based on concept'))
    prompt = prompt.replace('{{LENS_FEATURES}}', 
                           brand_config.get('LENS_FEATURES', 'Standard features appropriate for style'))
    prompt = prompt.replace('{{STYLE_PERSONA}}', 
                           brand_config.get('STYLE_PERSONA', 'Determine appropriate persona based on concept'))
    prompt = prompt.replace('{{WEARING_OCCASION}}', 
                           brand_config.get('WEARING_OCCASION', 'Various occasions appropriate for style'))
    prompt = prompt.replace('{{FRAME_MATERIAL}}', 
                           brand_config.get('FRAME_MATERIAL', 'High-quality materials appropriate for style'))
    
    return prompt


def call_llm(prompt, llm_model):
    """Call LLM to expand the concept."""
    
    if "/" in llm_model:
        provider, model = llm_model.split("/", 1)
    else:
        # Default to openai if no provider specified
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
    
    # Handle different model types
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
        temperature=1.0,  # Higher temperature for more creative variation
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


def expand_concept(concept_text, brand_config_path, video_settings, llm_model, output_dir):
    """
    Expand high-level concept to full scene-by-scene narrative.
    
    Args:
        concept_text: User's high-level concept (2-3 sentences)
        brand_config_path: Path to brand config JSON
        video_settings: Dict with num_clips, clip_duration
        llm_model: LLM model to use (format: "provider/model")
        output_dir: Directory to save expanded concept
    
    Returns:
        Path to expanded concept file
    """
    
    print(f"\n{'='*80}")
    print(f"STEP 0a: EXPAND CONCEPT")
    print(f"{'='*80}")
    print(f"LLM Model: {llm_model}")
    print(f"Scenes: {video_settings.get('num_clips', 5)}")
    print(f"Duration per scene: {video_settings.get('clip_duration', 6)}s")
    print(f"{'='*80}\n")
    
    # Load brand config
    brand_config = load_brand_config(brand_config_path)
    brand_name = brand_config.get('BRAND_NAME', 'Unknown')
    
    print(f"Brand: {brand_name}")
    print(f"\nHigh-level concept:")
    print(f"  {concept_text[:150]}{'...' if len(concept_text) > 150 else ''}\n")
    
    # Build prompt
    script_dir = Path(__file__).parent
    template_path = script_dir.parent / "inputs" / "prompt_templates" / "expand_concept_template.md"
    
    print("Building expansion prompt...")
    prompt = build_expand_prompt(concept_text, brand_config, video_settings, template_path)
    
    # Call LLM
    print(f"Calling {llm_model}...")
    expanded_concept = call_llm(prompt, llm_model)
    
    # Create output directory
    timestamp = datetime.now().strftime("%m%d_%H%M")
    batch_dir = Path(output_dir) / f"{brand_name.lower()}_{timestamp}"
    batch_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate concept name from title if present
    concept_name = f"{brand_name.lower()}_expanded_concept"
    if "**CONCEPT TITLE**:" in expanded_concept:
        try:
            title_line = [line for line in expanded_concept.split('\n') if '**CONCEPT TITLE**:' in line][0]
            title = title_line.split('**CONCEPT TITLE**:')[1].strip()
            # Clean title for filename
            concept_name = f"{brand_name.lower()}_{title.lower().replace(' ', '_').replace('-', '_')}"
            concept_name = ''.join(c for c in concept_name if c.isalnum() or c == '_')
        except:
            pass
    
    # Save expanded concept
    output_file = batch_dir / f"{concept_name}_expanded.txt"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(expanded_concept)
    
    # Save metadata
    metadata = {
        "concept_name": concept_name,
        "brand_name": brand_name,
        "timestamp": datetime.now().isoformat(),
        "llm_model": llm_model,
        "video_settings": video_settings,
        "original_concept": concept_text,
        "expanded_file": str(output_file)
    }
    
    metadata_file = batch_dir / f"{concept_name}_metadata.json"
    with open(metadata_file, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"\n{'='*80}")
    print(f"EXPANSION COMPLETE")
    print(f"{'='*80}")
    print(f"Expanded concept: {output_file}")
    print(f"Metadata: {metadata_file}")
    print(f"{'='*80}\n")
    
    return str(output_file), metadata


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python expand_concept.py <concept_text_or_file> [brand_config] [llm_model] [output_dir]")
        print("\nExample:")
        print('  python expand_concept.py "The World Comes Into Focus..." ../../s1_generate_concepts/inputs/configs/sunglasses.json')
        print('  python expand_concept.py inputs/concepts/world_comes_into_focus.txt ../../s1_generate_concepts/inputs/configs/sunglasses.json')
        print('  python expand_concept.py "Accidental Style Icon..." ../../s1_generate_concepts/inputs/configs/sunglasses.json anthropic/claude-sonnet-4-5-20250929')
        print("\nDefault brand config: ../../s1_generate_concepts/inputs/configs/sunglasses.json")
        print("Default LLM model: openai/gpt-5.1")
        print("Default output directory: s0_expand_concept/outputs/")
        sys.exit(1)
    
    concept_input = sys.argv[1]
    brand_config_path = sys.argv[2] if len(sys.argv) > 2 else "../../s1_generate_concepts/inputs/configs/sunglasses.json"
    llm_model = sys.argv[3] if len(sys.argv) > 3 else "openai/gpt-5.1"
    # Default to outputs folder in s0_expand_concept directory
    script_dir = Path(__file__).parent
    default_output_dir = script_dir.parent / "outputs"
    output_dir = sys.argv[4] if len(sys.argv) > 4 else str(default_output_dir)
    
    # Check if input is a file path
    concept_path = Path(concept_input)
    if concept_path.exists() and concept_path.is_file():
        print(f"Reading concept from file: {concept_path}")
        with open(concept_path, 'r', encoding='utf-8') as f:
            concept_text = f.read().strip()
    else:
        # Treat as concept text directly
        concept_text = concept_input
    
    # Default video settings (can be overridden by config)
    video_settings = {
        "num_clips": 5,
        "clip_duration": 6
    }
    
    if not os.path.exists(brand_config_path):
        print(f"Error: Brand config not found: {brand_config_path}")
        sys.exit(1)
    
    expand_concept(concept_text, brand_config_path, video_settings, llm_model, output_dir)

