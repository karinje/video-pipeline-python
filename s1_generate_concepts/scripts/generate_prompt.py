#!/usr/bin/env python3
"""
Prompt Generation Script
Takes a prompt template and config file, generates the final prompt,
and saves it to prompts_history/ with a descriptive filename.
"""

import os
import json
import re
from pathlib import Path
from datetime import datetime

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # dotenv not installed, will use system environment variables
    pass


def load_template(template_path):
    """Load prompt template from file."""
    with open(template_path, 'r', encoding='utf-8') as f:
        return f.read()


def load_config(config_path):
    """Load configuration from JSON file."""
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def replace_variables(template, config):
    """Replace {{VARIABLE}} placeholders in template with config values."""
    prompt = template
    for key, value in config.items():
        # Handle both {{VAR}} and {VAR} formats
        prompt = prompt.replace(f"{{{{{key}}}}}", str(value))
        prompt = prompt.replace(f"{{{key}}}", str(value))
    return prompt


def slugify(text):
    """Convert text to filename-safe slug, preserving dots in version numbers."""
    if not text:
        return ""
    # Convert to lowercase and replace spaces/special chars with underscores
    text = str(text).lower()
    # Preserve dots and word characters, remove everything else
    text = re.sub(r'[^\w\s.-]', '', text)
    # Replace spaces and hyphens with underscores
    text = re.sub(r'[-\s]+', '_', text)
    # Remove multiple consecutive underscores
    text = re.sub(r'_+', '_', text)
    # Remove leading/trailing underscores
    text = text.strip('_')
    return text


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
    model_slug = re.sub(r'_\d{8}', '', model_slug)  # Remove _20250929
    model_slug = re.sub(r'_\d{4}_\d{2}_\d{2}', '', model_slug)  # Remove _2025_09_29
    return model_slug


def generate_filename(template_path, config_path, output_dir, brand_name=None, ad_style=None, template_name=None, model_name=None):
    """Generate descriptive filename matching results folder format."""
    # If we have all the info for results-style naming, use that
    if brand_name and ad_style and template_name and model_name:
        brand_slug = slugify(brand_name)
        style_slug = slugify(ad_style)
        model_slug = clean_model_name(model_name)
        filename = f"{brand_slug}_{style_slug}_{template_name}_{model_slug}_prompt.txt"
        return os.path.join(output_dir, filename)
    
    # Fallback to old timestamp-based naming
    template_name_old = Path(template_path).stem
    config_name = Path(config_path).stem
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{template_name_old}_{config_name}_{timestamp}.md"
    return os.path.join(output_dir, filename)


def generate_prompt(template_path, config_path, output_dir="prompts_history", 
                   brand_name=None, ad_style=None, template_name=None, model_name=None):
    """
    Main function: Generate prompt from template + config and save to history.
    
    Args:
        template_path: Path to prompt template file
        config_path: Path to JSON config file
        output_dir: Directory to save generated prompts (default: prompts_history)
        brand_name: Brand name for filename (optional, for results-style naming)
        ad_style: Ad style for filename (optional, for results-style naming)
        template_name: Template name for filename (optional, for results-style naming)
        model_name: Model name for filename (optional, for results-style naming)
    
    Returns:
        Path to generated prompt file
    """
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    # Load template and config
    template = load_template(template_path)
    config = load_config(config_path)
    
    # Replace variables
    final_prompt = replace_variables(template, config)
    
    # Generate filename and save
    output_path = generate_filename(template_path, config_path, output_dir,
                                    brand_name, ad_style, template_name, model_name)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(final_prompt)
    
    # Silent in batch mode (will be called from parallel execution)
    return output_path


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python generate_prompt.py <template_path> <config_path> [output_dir]")
        print("\nExample:")
        print("  python generate_prompt.py prompt_templates/advanced_structured.md configs/nike.json")
        print("  python generate_prompt.py prompt_templates/generic_simple.md configs/nike.json")
        sys.exit(1)
    
    template_path = sys.argv[1]
    config_path = sys.argv[2]
    output_dir = sys.argv[3] if len(sys.argv) > 3 else "prompts_history"
    
    if not os.path.exists(template_path):
        print(f"Error: Template file not found: {template_path}")
        sys.exit(1)
    
    if not os.path.exists(config_path):
        print(f"Error: Config file not found: {config_path}")
        sys.exit(1)
    
    generate_prompt(template_path, config_path, output_dir)

