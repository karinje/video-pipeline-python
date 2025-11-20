#!/usr/bin/env python3
"""
LLM Execution Script
Takes a generated prompt file, sends it to OpenAI or Anthropic LLM,
and saves the concept result to concepts/ directory.
"""

import os
import sys
from pathlib import Path
from datetime import datetime

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # dotenv not installed, will use system environment variables
    pass


# Model options (as of Nov 15, 2025)
OPENAI_MODELS = [
    "gpt-5.1",
    "gpt-5.1-instant",
    "gpt-5.1-thinking",
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-4-turbo",
    "gpt-4"
]

ANTHROPIC_MODELS = [
    "claude-sonnet-4-5-20250929",  # Sonnet 4.5 (Sept 2025) - Latest
    "claude-opus-4-1-20250514",  # Opus 4.1 (Aug 2025)
    "claude-haiku-4-5-20251015",  # Haiku 4.5 (Oct 2025)
    "claude-sonnet-4-20250514",  # Sonnet 4
    "claude-opus-4-20250514",  # Opus 4
]


def load_prompt(prompt_path):
    """Load generated prompt from file."""
    with open(prompt_path, 'r', encoding='utf-8') as f:
        return f.read()


def call_openai(prompt, model, api_key, reasoning_effort=None):
    """Call OpenAI API.
    
    Args:
        prompt: System prompt
        model: Model name (e.g., 'gpt-5.1')
        api_key: API key
        reasoning_effort: For GPT-5.1, set to 'high', 'medium', 'low', or 'none' for thinking mode
    """
    try:
        from openai import OpenAI
    except ImportError:
        raise ImportError("OpenAI package not installed. Run: pip install openai")
    
    client = OpenAI(api_key=api_key)
    
    # Build request parameters
    params = {
        "model": model,
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": "Generate an ad concept based on the inputs provided."}
        ]
    }
    
    # For GPT-5.1, use max_completion_tokens and temperature=1 (only supported value)
    if model.startswith("gpt-5"):
        # Increase tokens for longer prompts (advanced template is ~22KB)
        params["max_completion_tokens"] = 4000  # Increased from 2000
        params["temperature"] = 1  # GPT-5.1 only supports temperature=1 (default)
        # Add reasoning_effort for GPT-5.1 thinking mode
        if reasoning_effort:
            params["reasoning_effort"] = reasoning_effort
    else:
        params["max_tokens"] = 2000
        params["temperature"] = 0.75  # Optimized for creative ad concept generation (balances creativity with coherence)
    
    response = client.chat.completions.create(**params)
    
    # Handle response - GPT-5.1 might return content differently
    if not response.choices or len(response.choices) == 0:
        raise ValueError("No choices in API response")
    
    message = response.choices[0].message
    
    # Check if content exists
    if not hasattr(message, 'content') or message.content is None:
        # Try alternative response formats
        if hasattr(message, 'text'):
            return message.text
        elif hasattr(response, 'content'):
            return response.content
        else:
            # Debug: print what we got
            print(f"DEBUG: Response type: {type(response)}")
            print(f"DEBUG: Message type: {type(message)}")
            print(f"DEBUG: Message attributes: {dir(message)}")
            raise ValueError(f"Unexpected response format: {type(response)}, message: {message}")
    
    content = message.content
    
    # Check if content is empty string
    if not content or len(content.strip()) == 0:
        print(f"WARNING: Empty content returned from API. Response: {response}")
        raise ValueError("API returned empty content")
    
    return content


def call_anthropic(prompt, model, api_key, thinking=None, max_tokens=None, temperature=None):
    """Call Anthropic API.
    
    Args:
        prompt: System prompt
        model: Model name (e.g., 'claude-sonnet-4.5')
        api_key: API key
        thinking: For extended thinking, set to dict with 'type': 'enabled' or max_tokens
        max_tokens: Maximum output tokens (overrides default if provided)
        temperature: Temperature for generation (0.0-1.0). If None, uses defaults based on thinking mode.
    """
    try:
        from anthropic import Anthropic
    except ImportError:
        raise ImportError("Anthropic package not installed. Run: pip install anthropic")
    
    client = Anthropic(api_key=api_key)
    
    # Build request parameters
    params = {
        "model": model,
        "system": prompt,
        "messages": [
            {"role": "user", "content": "Generate the 5-sentence ad concept now using all the inputs provided in the system prompt. Do not ask questions - all required information is already provided. Output the concept in the exact format specified."}
        ]
    }
    
    # Add thinking parameter for extended thinking mode
    if thinking is not None:
        if isinstance(thinking, dict):
            params["thinking"] = thinking
            budget_tokens = thinking.get("budget_tokens", 10000)
        elif thinking is True:
            # Enable extended thinking with default budget
            budget_tokens = 10000
            params["thinking"] = {"type": "enabled", "budget_tokens": budget_tokens}
        elif isinstance(thinking, int):
            # Set max thinking tokens with budget_tokens
            budget_tokens = thinking
            params["thinking"] = {"type": "enabled", "budget_tokens": budget_tokens}
        
        # max_tokens must be greater than budget_tokens
        if max_tokens is None:
            params["max_tokens"] = budget_tokens + 2000  # Add buffer for actual response
        else:
            params["max_tokens"] = max_tokens
        
        # Claude requires temperature=1 when thinking is enabled (unless explicitly overridden)
        params["temperature"] = temperature if temperature is not None else 1
    else:
        # No thinking mode - use optimized temperature
        if max_tokens is None:
            params["max_tokens"] = 2000  # Default for short responses
        else:
            params["max_tokens"] = max_tokens
        params["temperature"] = temperature if temperature is not None else 0.75  # Optimized for creative ad concept generation (balances creativity with coherence)
    
    response = client.messages.create(**params)
    
    # Check if response was truncated
    stop_reason = getattr(response, 'stop_reason', None)
    if stop_reason == 'max_tokens':
        raise ValueError(f"Response was truncated at max_tokens={params.get('max_tokens')}. Increase max_tokens parameter to get full response.")
    
    # Handle Claude response - may have thinking blocks when thinking mode is enabled
    if hasattr(response, 'content') and len(response.content) > 0:
        # Iterate through all content blocks to find text block
        for block in response.content:
            # Check if it's a TextBlock (has 'text' attribute)
            if hasattr(block, 'text'):
                return block.text
            # Check if it's a block with type='text'
            elif hasattr(block, 'type'):
                if block.type == 'text' and hasattr(block, 'text'):
                    return block.text
        
        # If no text block found, try to get string representation
        # This handles edge cases where structure is different
        first_block = response.content[0]
        if hasattr(first_block, '__dict__'):
            # Try to extract any text-like content
            for attr in ['text', 'content', 'body']:
                if hasattr(first_block, attr):
                    val = getattr(first_block, attr)
                    if isinstance(val, str):
                        return val
        
        # Last resort: convert to string
        raise ValueError(f"Could not extract text from Claude response. Content blocks: {[type(b).__name__ for b in response.content]}")
    else:
        raise ValueError("No content in Claude response")


def generate_concept_filename(prompt_path, output_dir):
    """Generate concept filename based on prompt filename."""
    # Simply replace '_prompt.txt' with '.txt'
    prompt_basename = os.path.basename(prompt_path)
    concept_filename = prompt_basename.replace('_prompt.txt', '.txt')
    return os.path.join(output_dir, concept_filename)


def execute_llm(prompt_path, provider, model, output_dir="concepts", api_key=None, 
                reasoning_effort=None, thinking=None):
    """
    Execute LLM call and save concept result.
    
    Args:
        prompt_path: Path to generated prompt file
        provider: 'openai' or 'anthropic'
        model: Model name (e.g., 'gpt-5.1', 'claude-sonnet-4.5')
        output_dir: Directory to save concepts (default: concepts)
        api_key: API key (if None, reads from environment)
        reasoning_effort: For GPT-5.1, set to 'high', 'medium', 'low', or 'none' (default: 'high' for thinking)
        thinking: For Claude, set to True, int (max_tokens), or dict for extended thinking
    
    Returns:
        Path to saved concept file
    """
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    # Load prompt
    prompt = load_prompt(prompt_path)
    
    # Get API key
    if api_key is None:
        if provider == "openai":
            api_key = os.getenv("OPENAI_API_KEY")
        elif provider == "anthropic":
            api_key = os.getenv("ANTHROPIC_API_KEY")
        else:
            raise ValueError(f"Unknown provider: {provider}")
        
        if not api_key:
            raise ValueError(f"{provider.upper()}_API_KEY environment variable not set")
    
    # Validate model
    if provider == "openai":
        if model not in OPENAI_MODELS:
            print(f"Warning: {model} not in known OpenAI models. Proceeding anyway...")
        concept_text = call_openai(prompt, model, api_key, reasoning_effort=reasoning_effort)
    elif provider == "anthropic":
        if model not in ANTHROPIC_MODELS:
            print(f"Warning: {model} not in known Anthropic models. Proceeding anyway...")
        concept_text = call_anthropic(prompt, model, api_key, thinking=thinking)
    else:
        raise ValueError(f"Unknown provider: {provider}. Use 'openai' or 'anthropic'")
    
    # Save concept
    output_path = generate_concept_filename(prompt_path, output_dir)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(concept_text)
    
    # Silent in batch mode (will be called from parallel execution)
    return output_path


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python execute_llm.py <prompt_path> <provider> <model> [output_dir]")
        print("\nProviders: openai, anthropic")
        print("\nOpenAI Models:")
        for m in OPENAI_MODELS:
            print(f"  - {m}")
        print("\nAnthropic Models:")
        for m in ANTHROPIC_MODELS:
            print(f"  - {m}")
        print("\nExample:")
        print("  python execute_llm.py prompts_history/..._prompt.md openai gpt-5.1")
        print("  python execute_llm.py prompts_history/..._prompt.md anthropic claude-sonnet-4.5")
        sys.exit(1)
    
    prompt_path = sys.argv[1]
    provider = sys.argv[2].lower()
    model = sys.argv[3]
    output_dir = sys.argv[4] if len(sys.argv) > 4 else "concepts"
    
    if not os.path.exists(prompt_path):
        print(f"Error: Prompt file not found: {prompt_path}")
        sys.exit(1)
    
    if provider not in ["openai", "anthropic"]:
        print(f"Error: Provider must be 'openai' or 'anthropic', got: {provider}")
        sys.exit(1)
    
    execute_llm(prompt_path, provider, model, output_dir)

