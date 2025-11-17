#!/usr/bin/env python3
"""
Helper function to generate a single concept (prompt + LLM call).
Used by batch_run_all_styles.py
"""

import sys
import os
from pathlib import Path

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from generate_prompt import generate_prompt, slugify, clean_model_name
from execute_llm import execute_llm


def run_pipeline(template_path, config_path, provider, model, 
                 prompts_dir, concepts_dir,
                 reasoning_effort=None, thinking=None,
                 brand_name=None, ad_style=None, template_name=None):
    """
    Generate prompt and execute LLM call for a single concept.
    
    Returns:
        (prompt_path, concept_path)
    """
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
    
    return prompt_path, concept_path

