#!/usr/bin/env python3
"""
Universe and Characters Generator
Generates detailed descriptions for characters, props, and locations that need consistency across scenes.
"""

import os
import sys
import json
from pathlib import Path

# Add path for imports
BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR / "s1_generate_concepts" / "scripts"))

# Load environment variables
try:
    from dotenv import load_dotenv
    # Load .env from project root
    env_path = BASE_DIR / ".env"
    load_dotenv(env_path)
except ImportError:
    pass

from execute_llm import call_openai, call_anthropic


def call_anthropic_with_caching(prompt, model, api_key, thinking=None, max_tokens=None):
    """
    Call Anthropic API with prompt caching for repeated schema/instructions.
    Caches the schema and instructions to reduce costs and latency on repeated calls.
    """
    try:
        from anthropic import Anthropic
    except ImportError:
        raise ImportError("Anthropic package not installed. Run: pip install anthropic")
    
    client = Anthropic(api_key=api_key)
    
    # Split prompt into cacheable (schema/instructions) and dynamic (content) parts
    # Find where the actual concept content starts
    if "**5-SCENE CONCEPT:**" in prompt:
        parts = prompt.split("**5-SCENE CONCEPT:**")
        cacheable_part = parts[0] + "**5-SCENE CONCEPT:**"
        dynamic_part = parts[1]
    else:
        # Fallback: cache everything up to the concept
        cacheable_part = prompt[:len(prompt)//2]
        dynamic_part = prompt[len(prompt)//2:]
    
    # Build system messages with cache control
    system = [
        {
            "type": "text",
            "text": cacheable_part.strip(),
            "cache_control": {"type": "ephemeral"}  # Cache this part
        }
    ]
    
    # Build request parameters
    params = {
        "model": model,
        "system": system,
        "messages": [
            {"role": "user", "content": dynamic_part.strip()}
        ]
    }
    
    # Add thinking parameter for extended thinking mode
    if thinking is not None:
        if isinstance(thinking, dict):
            params["thinking"] = thinking
            budget_tokens = thinking.get("budget_tokens", 10000)
        elif thinking is True:
            budget_tokens = 10000
            params["thinking"] = {"type": "enabled", "budget_tokens": budget_tokens}
        elif isinstance(thinking, int):
            budget_tokens = thinking
            params["thinking"] = {"type": "enabled", "budget_tokens": budget_tokens}
        
        # max_tokens must be greater than budget_tokens
        if max_tokens is None:
            params["max_tokens"] = budget_tokens + 4000  # Buffer for JSON output
        else:
            params["max_tokens"] = max_tokens
        
        params["temperature"] = 1  # Required with thinking
    else:
        params["max_tokens"] = max_tokens if max_tokens else 4000
        params["temperature"] = 0.75
    
    response = client.messages.create(**params)
    
    # Extract content from response
    if not response.content or len(response.content) == 0:
        raise ValueError("Empty response from Anthropic API")
    
    # Handle different content types (text blocks, thinking blocks, etc.)
    content_parts = []
    for block in response.content:
        # Skip thinking blocks - we only want the actual text response
        if hasattr(block, 'type') and block.type == 'thinking':
            continue
        
        if hasattr(block, 'text'):
            content_parts.append(block.text)
        elif hasattr(block, 'content'):
            content_parts.append(block.content)
        else:
            # Fallback: convert to string
            content_parts.append(str(block))
    
    if not content_parts:
        raise ValueError("No text content found in Anthropic API response (only thinking blocks)")
    
    content = '\n'.join(content_parts)
    
    # Print cache usage stats if available
    usage = getattr(response, 'usage', None)
    if usage:
        cache_read = getattr(usage, 'cache_read_input_tokens', 0)
        cache_create = getattr(usage, 'cache_creation_input_tokens', 0)
        if cache_read > 0:
            print(f"  → Cache hit: {cache_read} tokens read from cache (saved cost!)")
        if cache_create > 0:
            print(f"  → Cache created: {cache_create} tokens cached for future use")
    
    return content


def get_api_key(provider):
    """Get API key from environment."""
    if provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
    elif provider == "anthropic":
        api_key = os.getenv("ANTHROPIC_API_KEY")
    else:
        raise ValueError(f"Unknown provider: {provider}")
    
    if not api_key:
        raise ValueError(f"{provider.upper()}_API_KEY not found in environment")
    
    return api_key


def generate_universe_and_characters(revised_script, config, model="anthropic/claude-sonnet-4-5-20250929", thinking=1500):
    """Generate universe (props, locations) and character descriptions for consistency across scenes.
    
    Args:
        revised_script: The revised 5-scene concept
        config: Brand configuration dict
        model: LLM model (format: "provider/model_name")
        thinking: Thinking budget tokens for Claude (default: 1500, minimum: 1024)
    """
    
    # Define JSON schema for structured output (simplified - no versions)
    universe_schema = {
        "type": "object",
        "properties": {
            "universe": {
                "type": "object",
                "properties": {
                    "locations": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "scenes_used": {"type": "array", "items": {"type": "integer"}},
                                "canonical_state": {"type": "string"},
                                "image_generation_prompt": {"type": "string"}
                            },
                            "required": ["name", "scenes_used", "canonical_state", "image_generation_prompt"],
                            "additionalProperties": False
                        }
                    },
                    "props": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "scenes_used": {"type": "array", "items": {"type": "integer"}},
                                "canonical_state": {"type": "string"},
                                "image_generation_prompt": {"type": "string"}
                            },
                            "required": ["name", "scenes_used", "canonical_state", "image_generation_prompt"],
                            "additionalProperties": False
                        }
                    }
                },
                "required": ["locations", "props"],
                "additionalProperties": False
            },
            "characters": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "scenes_used": {"type": "array", "items": {"type": "integer"}},
                        "canonical_state": {"type": "string"},
                        "image_generation_prompt": {"type": "string"}
                    },
                    "required": ["name", "scenes_used", "canonical_state", "image_generation_prompt"],
                    "additionalProperties": False
                }
            }
        },
        "required": ["universe", "characters"],
        "additionalProperties": False
    }
    
    prompt = f"""You are a video production designer. Analyze this 5-scene ad concept and create detailed descriptions for:
1. **UNIVERSE**: All props, locations, and environmental elements that appear across multiple scenes
2. **CHARACTERS**: All characters with detailed descriptions for visual consistency

**BRAND CONTEXT:**
- Brand: {config.get('BRAND_NAME', 'N/A')}
- Product: {config.get('PRODUCT_DESCRIPTION', 'N/A')}
- Creative Direction: {config.get('CREATIVE_DIRECTION', 'N/A')}

**5-SCENE CONCEPT:**
{revised_script}

**INSTRUCTIONS:**
1. Identify ONLY props/objects that appear in MULTIPLE scenes (2 or more) - these need consistency tracking
2. Identify ONLY locations that appear in MULTIPLE scenes (2 or more) - these need consistency tracking
3. Identify ALL characters with detailed physical descriptions (age, appearance, clothing, distinctive features) - characters need consistency even if only in one scene
4. **NEW APPROACH**: For each element, provide ONE canonical description in its BASE/ORIGINAL state
5. **NO VERSIONS**: Do NOT create multiple versions - we'll handle transformations later in scene-specific prompts
6. Each description should be vivid and detailed enough to use directly in AI image generation prompts
7. DO NOT include props or locations that only appear in a single scene - the video generation model will create those fresh each time
8. Focus on elements that need visual consistency ACROSS multiple scenes

**OUTPUT FORMAT (JSON):**
```json
{{
  "universe": {{
    "locations": [
      {{
        "name": "Location Name",
        "scenes_used": [1, 2, 3],
        "canonical_state": "Detailed visual description in its base/original state",
        "image_generation_prompt": "Complete prompt for generating reference image of the canonical state (for nano/banana image generation)"
      }}
    ],
    "props": [
      {{
        "name": "Prop Name",
        "scenes_used": [1, 2, 3],
        "canonical_state": "Detailed visual description in its base/original state",
        "image_generation_prompt": "Complete prompt for generating reference image of the canonical state (for nano/banana image generation)"
      }}
    ]
  }},
  "characters": [
    {{
      "name": "Character Name",
      "scenes_used": [1, 2, 3, 4, 5],
      "canonical_state": "Detailed physical description in base/original appearance (age, clothing, features, etc.)",
      "image_generation_prompt": "Complete prompt for generating reference image of the canonical state (for nano/banana image generation)"
    }}
  ]
}}
```

**IMPORTANT NOTES:**
- Each element has ONE canonical description in its base/original state
- Transformations will be handled later in scene-specific prompts (not here)
- "canonical_state" should describe the element in its most neutral/original form
- "image_generation_prompt" should be a complete, detailed prompt ready to feed into image generation models (nano-banana, etc.)
- **CRITICAL: Image prompts must generate HYPER-REALISTIC, PHOTOREALISTIC images that look like real people/photographs**
- Include these realism keywords in every image_generation_prompt: "hyper-realistic", "photorealistic", "ultra-realistic", "lifelike", "documentary photography style", "real person", "authentic", "natural skin texture", "realistic lighting", "professional portrait photography"
- **CRITICAL FOR GROUPS**: If describing a group with diversity requirements (e.g., "diverse ethnicities"), make diversity the FIRST and MOST PROMINENT part of the prompt. Explicitly describe each person's ethnicity, skin tone, and distinctive features.
- Image prompts should include all visual details: lighting, composition, style, specific features, colors, textures, skin details, hair texture, clothing fabric details, etc.
- Avoid any stylized, artistic, or cartoon-like descriptions - focus on photographic realism"""
    
    provider, model_name = model.split("/", 1) if "/" in model else ("anthropic", model)
    api_key = get_api_key(provider)
    
    print(f"  → Calling {provider}/{model_name} to generate universe/characters...")
    print(f"  → This may take 30-60 seconds with extended thinking...")
    
    if provider == "openai":
        # Use structured outputs for guaranteed valid JSON (GPT-4o and later)
        if "gpt-4o" in model_name or "gpt-5" in model_name:
            print(f"  → Using OpenAI Structured Outputs for guaranteed valid JSON...")
            from openai import OpenAI
            client = OpenAI(api_key=api_key)
            
            completion = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "universe_schema",
                        "strict": True,
                        "schema": universe_schema
                    }
                }
            )
            response = completion.choices[0].message.content
        else:
            # Fallback for older models
            response = call_openai(prompt, model_name, api_key, reasoning_effort="high")
    else:
        # Claude: Add explicit JSON-only instruction + use prompt caching
        # Ensure thinking is at least 1024 (Claude's minimum)
        thinking_budget = max(thinking, 1024)
        json_only_prompt = f"{prompt}\n\n**CRITICAL**: Output ONLY the JSON object. Do not include markdown code blocks, explanations, or any text outside the JSON. Start with {{ and end with }}."
        print(f"  → Using Anthropic Prompt Caching to reduce costs and latency...")
        print(f"  → Thinking budget: {thinking_budget} tokens (~30-60 seconds)")
        response = call_anthropic_with_caching(json_only_prompt, model_name, api_key, thinking=thinking_budget, max_tokens=16000)
    
    print(f"  ✓ LLM response received, parsing JSON...")
    
    # Extract JSON from response (handles markdown code blocks)
    json_text = response.strip()
    
    # Remove markdown code blocks if present
    if "```json" in json_text:
        json_text = json_text.split("```json")[1].split("```")[0].strip()
    elif "```" in json_text:
        json_text = json_text.split("```")[1].split("```")[0].strip()
    
    # Find JSON object boundaries if there's extra text
    if not json_text.startswith("{"):
        # Try to find the first { and last }
        start = json_text.find("{")
        end = json_text.rfind("}") + 1
        if start != -1 and end > start:
            json_text = json_text[start:end]
    
    # Attempt to parse
    try:
        return json.loads(json_text)
    except json.JSONDecodeError as e:
        print(f"  ⚠ JSON parsing failed: {e}")
        print(f"  → Attempting to fix common JSON issues...")
        
        import re
        # Fix common LLM JSON issues:
        # 1. Remove trailing commas before closing brackets/braces
        json_text = re.sub(r',(\s*[}\]])', r'\1', json_text)
        # 2. Add missing commas between fields
        # Pattern: closing quote, newline, whitespace, opening quote (for next key) - missing comma
        json_text = re.sub(r'"\s*\n\s+"([a-zA-Z_])', r'",\n        "\1', json_text)  # After string value, before next key
        json_text = re.sub(r'}\s*\n\s+"([a-zA-Z_])', r'},\n        "\1', json_text)  # After object, before string key
        json_text = re.sub(r']\s*\n\s+"([a-zA-Z_])', r'],\n        "\1', json_text)  # After array, before string key
        json_text = re.sub(r'true\s*\n\s+"([a-zA-Z_])', r'true,\n        "\1', json_text)  # After true, before string key
        json_text = re.sub(r'false\s*\n\s+"([a-zA-Z_])', r'false,\n        "\1', json_text)  # After false, before string key
        json_text = re.sub(r'null\s*\n\s+"([a-zA-Z_])', r'null,\n        "\1', json_text)  # After null, before string key
        json_text = re.sub(r'(\d+)\s*\n\s+"([a-zA-Z_])', r'\1,\n        "\2', json_text)  # After number, before string key
        # 3. Fix unescaped quotes in strings (basic attempt)
        # 4. Remove comments (// or /* */)
        json_text = re.sub(r'//.*?\n', '\n', json_text)
        json_text = re.sub(r'/\*.*?\*/', '', json_text, flags=re.DOTALL)
        
        try:
            return json.loads(json_text)
        except json.JSONDecodeError as e2:
            print(f"  ✗ Still failed after automatic fixes: {e2}")
            print(f"  → Saving raw response for debugging...")
            
            # Save to debug file
            debug_dir = Path("s5_generate_universe/outputs/debug")
            debug_dir.mkdir(parents=True, exist_ok=True)
            debug_file = debug_dir / "failed_response.txt"
            
            with open(debug_file, 'w', encoding='utf-8') as f:
                f.write("=== ORIGINAL RESPONSE ===\n")
                f.write(response)
                f.write("\n\n=== EXTRACTED JSON TEXT ===\n")
                f.write(json_text)
                f.write(f"\n\n=== ERROR ===\n{e2}")
            
            print(f"  → Debug info saved to: {debug_file}")
            print(f"  → Error location: line {e2.lineno}, column {e2.colno}")
            
            # Show context around error
            if hasattr(e2, 'pos') and e2.pos:
                start = max(0, e2.pos - 100)
                end = min(len(json_text), e2.pos + 100)
                print(f"  → Context: ...{json_text[start:end]}...")
            
            raise Exception(f"Failed to parse JSON after fixes. See {debug_file} for details.") from e2


def main():
    """Main function for standalone execution."""
    print("=" * 80)
    print("GENERATE UNIVERSE AND CHARACTERS")
    print("=" * 80)
    
    if len(sys.argv) < 4:
        print("Usage: python generate_universe.py <revised_concept_file> <config_file> <output_file> [model]")
        sys.exit(1)
    
    revised_file = sys.argv[1]
    config_file = sys.argv[2]
    output_file = sys.argv[3]
    model = sys.argv[4] if len(sys.argv) > 4 else "anthropic/claude-sonnet-4-5-20250929"
    
    print(f"\nLoading revised concept: {revised_file}")
    with open(revised_file, 'r', encoding='utf-8') as f:
        revised_script = f.read()
    
    print(f"Loading config: {config_file}")
    with open(config_file, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    print(f"Generating universe and characters with {model}...")
    universe_chars = generate_universe_and_characters(revised_script, config, model)
    
    # Save output
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(universe_chars, f, indent=2)
    
    print(f"✓ Saved: {output_file}\n")
    
    # Print summary
    num_chars = len(universe_chars.get("characters", []))
    num_props = len(universe_chars.get("universe", {}).get("props", []))
    num_locs = len(universe_chars.get("universe", {}).get("locations", []))
    
    print(f"Summary:")
    print(f"  - Characters: {num_chars}")
    print(f"  - Props (multi-scene): {num_props}")
    print(f"  - Locations (multi-scene): {num_locs}")
    
    print("\n" + "=" * 80)
    print("SUCCESS")
    print("=" * 80)


if __name__ == "__main__":
    main()

