#!/usr/bin/env python3
"""
OpenRouter API Test Script
Calls Claude Sonnet 4.5 via OpenRouter
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

def call_openrouter(prompt, model="anthropic/claude-sonnet-4.5", system_prompt=None):
    """
    Call OpenRouter API
    
    Args:
        prompt: User prompt
        model: Model name (default: anthropic/claude-sonnet-4.5:beta)
        system_prompt: Optional system prompt
    
    Returns:
        Response text from the model
    """
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY not found in .env file")
    
    url = "https://openrouter.ai/api/v1/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:3000",  # Optional, for rankings
        "X-Title": "Video Gen Script"  # Optional, shows in rankings
    }
    
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    
    data = {
        "model": model,
        "messages": messages,
        "temperature": 0.75,
        "max_tokens": 2000
    }
    
    response = requests.post(url, headers=headers, json=data)
    
    if response.status_code != 200:
        error_detail = response.text
        try:
            error_json = response.json()
            error_detail = error_json.get("error", {}).get("message", error_detail)
        except:
            pass
        raise Exception(f"API Error ({response.status_code}): {error_detail}")
    
    result = response.json()
    return result["choices"][0]["message"]["content"]


if __name__ == "__main__":
    # Test call
    test_prompt = "Write a short creative ad concept for a luxury watch brand in 3 sentences."
    
    print("Calling OpenRouter API with Claude Sonnet 4.5...\n")
    
    try:
        response = call_openrouter(test_prompt)
        print("Response:")
        print("-" * 50)
        print(response)
        print("-" * 50)
        print("\n✓ Success!")
    except Exception as e:
        print(f"✗ Error: {e}")

