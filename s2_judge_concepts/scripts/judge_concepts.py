#!/usr/bin/env python3
"""
LLM Judge Script
Evaluates ad concepts from batch runs, scoring them based on style criteria and success likelihood.
"""

import os
import sys
import json
import csv
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def load_batch_summary(summary_path):
    """Load batch run summary JSON."""
    with open(summary_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_concept_file(file_path):
    """Load concept content from file. Handles both absolute and relative paths."""
    # If path doesn't exist, try resolving relative to project root
    if not os.path.exists(file_path):
        # Try resolving from project root (go up 2 levels from scripts/ to project root)
        script_dir = Path(__file__).parent
        project_root = script_dir.parent.parent
        resolved_path = project_root / file_path
        if resolved_path.exists():
            file_path = str(resolved_path)
        else:
            return None
    
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read()


def get_ad_style_description(ad_style):
    """Get high-level description of ad style WITHOUT revealing structure requirements."""
    descriptions = {
        "Humor - Hilarious": "Over-the-top funny, designed to make people laugh out loud. Should be relatable and genuinely funny.",
        "Humor - Playful": "Light, whimsical, charming humor that makes you smile.",
        "Humor - Sarcastic/Witty": "Dry, clever, deadpan humor with wit.",
        "Sentiment - Heartwarming": "Gentle, touching moments that make you smile with warmth.",
        "Sentiment - Tear-jerking": "Intensely emotional, designed to move viewers to tears (happy tears).",
        "Sentiment - Nostalgic": "Wistful, reflective, bittersweet emotions about the past.",
        "Achievement - Inspirational": "Uplifting, motivating narrative about overcoming challenges and achieving goals.",
        "Achievement - Empowering": "Fierce, bold, confident narrative about breaking barriers and showing strength.",
        "Achievement - Understated": "Quiet determination and subtle resilience leading to triumph.",
        "Adventure - Thrilling": "High-energy, exciting, fast-paced journey with escalating thrills.",
        "Adventure - Wonder-filled": "Awe-inspiring, discovery-focused journey that creates wonder.",
        "Adventure - Epic": "Grand scale, cinematic, larger-than-life adventure.",
        "Reversal - Thought-provoking": "Makes you think differently, challenges assumptions with insight.",
        "Reversal - Mind-blowing": "Shocking twist that completely recontextualizes everything.",
        "Reversal - Clever": "Witty, intellectually satisfying twist that makes you say 'ahh, nice!'"
    }
    return descriptions.get(ad_style, "We need to create compelling advertising that resonates with viewers.")


def create_single_judge_prompt(ad_style, brand_name, concept_content, model_name, template_name):
    """Create evaluation prompt for a SINGLE concept (no comparison, no structure hints)."""
    style_description = get_ad_style_description(ad_style)
    
    prompt = f"""You are an expert advertising judge evaluating a single ad concept.

**BRAND**: {brand_name}
**AD STYLE**: {ad_style}
**STYLE DESCRIPTION**: {style_description}

**AI VIDEO GENERATION CONTEXT**:
This concept will be produced using advanced AI video generation (Sora 2, Veo 3).
- These models can generate visuals impossible with traditional filming.
- "Impossible" visuals, transformations, and reality-bending effects are ENCOURAGED if they serve the story.
- Do not penalize creative visual concepts as "unrealistic" - they are likely achievable with AI.
- Reward concepts that leverage this potential for higher Memorability and Visual Impact.

**CONCEPT TO EVALUATE**:

{concept_content}

---

**EVALUATION CRITERIA**:

1. **Narrative Quality** (20 points)
   - Does it tell a compelling story?
   - Clear beginning, middle, and end?
   - Are the 5 scenes coherent and connected?

2. **Emotional Impact** (20 points)
   - Does it make you FEEL something strong?
   - Does the emotion match the intended style ({ad_style})?
   - Would most people have this emotional reaction?

3. **Brand Integration** (15 points)
   - Does the brand fit naturally into the story?
   - Is it forced or organic?
   - Does the brand feel necessary, not just added?

4. **Memorability** (15 points)
   - Will people remember this concept?
   - Is there a unique element or hook?
   - Does it stand out?
   - **BONUS**: Does it use AI capabilities for a unique visual hook?

5. **Visual Clarity** (15 points)
   - Can you clearly picture each of the 5 scenes?
   - Would this work as a 30-60 second video?
   - Are scenes visually distinct and clear?

6. **Success Likelihood** (15 points)
   - Would this concept work in the real world?
   - Would the target audience respond positively?
   - Does it feel fresh or cliché?

**TOTAL**: 100 points

---

**INSTRUCTIONS**:
1. Evaluate this concept honestly based ONLY on the criteria above
2. Provide a score (0-100)
3. List 3-5 specific strengths
4. List 3-5 specific weaknesses
5. Give a brief 2-3 sentence explanation of the score

**OUTPUT FORMAT** (JSON only, no other text):
```json
{{
  "score": 85,
  "explanation": "2-3 sentence explanation",
  "strengths": ["strength 1", "strength 2", "strength 3"],
  "weaknesses": ["weakness 1", "weakness 2"]
}}
```
"""
    return prompt


def call_judge_llm(prompt, judge_model="anthropic/claude-sonnet-4-5-20250929"):
    """Send evaluation prompt to LLM judge."""
    if "/" in judge_model:
        provider, model = judge_model.split("/", 1)
    else:
        # Default to anthropic if no provider specified
        provider = "anthropic"
        model = judge_model
    
    if provider == "openai":
        return call_openai_judge(prompt, model)
    elif provider == "anthropic":
        return call_anthropic_judge(prompt, model)
    else:
        raise ValueError(f"Unsupported provider: {provider}")


def call_openai_judge(prompt, model):
    """Call OpenAI for judging."""
    try:
        from openai import OpenAI
    except ImportError:
        raise ImportError("OpenAI package not installed. Run: pip install openai")
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not found in environment")
    
    client = OpenAI(api_key=api_key)
    
    # GPT-5.1 requires max_completion_tokens instead of max_tokens and temperature=1
    params = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are an expert advertising judge. Respond only with valid JSON."},
            {"role": "user", "content": prompt}
        ],
    }
    
    if "gpt-5" in model or "o1" in model or "o3" in model:
        params["max_completion_tokens"] = 2000
        params["temperature"] = 1
    else:
        params["max_tokens"] = 2000
        params["temperature"] = 0.3
    
    response = client.chat.completions.create(**params)
    
    return response.choices[0].message.content


def call_anthropic_judge(prompt, model):
    """Call Anthropic for judging."""
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
        max_tokens=2000,
        temperature=1.0,  # Higher temperature for more creative evaluation
        system="You are an expert advertising judge. Respond only with valid JSON.",
        messages=[
            {"role": "user", "content": prompt}
        ]
    )
    
    # Extract text from response
    for block in response.content:
        if hasattr(block, 'text'):
            return block.text
    
    raise ValueError("No text content in Anthropic response")


def evaluate_single_concept(task):
    """Evaluate a single concept (for parallel execution)."""
    ad_style = task["ad_style"]
    brand_name = task["brand_name"]
    content = task["content"]
    model_name = task["model"]
    template = task["template"]
    judge_model = task["judge_model"]
    result_info = task["result_info"]
    
    start_time = time.time()
    
    try:
        # Create judge prompt for this single concept
        judge_prompt = create_single_judge_prompt(ad_style, brand_name, content, model_name, template)
        
        # Call judge LLM
        response = call_judge_llm(judge_prompt, judge_model)
        
        # Parse JSON response
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0]
        elif "```" in response:
            response = response.split("```")[1].split("```")[0]
        
        evaluation = json.loads(response.strip())
        
        # Add metadata
        evaluation["model"] = model_name
        evaluation["template"] = template
        evaluation["file"] = result_info["file"]
        evaluation["provider"] = result_info["provider"]
        
        elapsed = time.time() - start_time
        
        return {
            "success": True,
            "evaluation": evaluation,
            "elapsed": elapsed
        }
        
    except Exception as e:
        elapsed = time.time() - start_time
        return {
            "success": False,
            "error": str(e),
            "model": model_name,
            "template": template,
            "elapsed": elapsed
        }


def judge_batch(summary_path, judge_model="anthropic/claude-sonnet-4-5-20250929", output_dir="evaluations"):
    """
    Judge all concepts from a batch run (each evaluated separately in parallel).
    
    Args:
        summary_path: Path to batch summary JSON
        judge_model: Model to use for judging (format: "provider/model_name")
        output_dir: Directory to save evaluation results
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # Load summary
    summary = load_batch_summary(summary_path)
    # Try to extract brand from summary or from first result file name
    brand_name = summary.get("brand_name") or summary.get("brand")
    if not brand_name and summary.get("results"):
        # Extract from filename: rolex_style_template_model.txt
        first_file = summary["results"][0].get("file", "")
        brand_name = first_file.split("/")[-1].split("_")[0].capitalize() if first_file else "Unknown"
    brand_name = brand_name or "Unknown"
    
    print(f"\n{'='*80}")
    print(f"LLM JUDGE: Evaluating concepts for {brand_name}")
    print(f"Judge Model: {judge_model}")
    print(f"Evaluation Method: Each concept judged separately in parallel")
    print(f"{'='*80}\n")
    
    # Group concepts by ad_style
    style_groups = {}
    for result in summary.get("results", []):
        if result["status"] != "SUCCESS":
            continue
        
        ad_style = result["ad_style"]
        if ad_style not in style_groups:
            style_groups[ad_style] = []
        
        style_groups[ad_style].append(result)
    
    # Evaluate all concepts
    all_evaluations = []
    
    for ad_style, results in style_groups.items():
        print(f"\nEvaluating: {ad_style}")
        print(f"  Concepts: {len(results)}")
        
        # Prepare tasks for parallel evaluation
        tasks = []
        for result in results:
            concept_path = result["file"]
            content = load_concept_file(concept_path)
            
            if content:
                tasks.append({
                    "ad_style": ad_style,
                    "brand_name": brand_name,
                    "content": content,
                    "model": result["model"],
                    "template": result["template"],
                    "judge_model": judge_model,
                    "result_info": result
                })
        
        if len(tasks) < 1:
            print(f"  ⚠️  Skipping (no valid concepts)")
            continue
        
        # Evaluate all concepts in parallel
        print(f"  → Evaluating {len(tasks)} concepts in parallel...")
        evaluations_for_style = []
        
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {executor.submit(evaluate_single_concept, task): task for task in tasks}
            
            for future in as_completed(futures):
                result = future.result()
                
                if result["success"]:
                    evaluations_for_style.append(result["evaluation"])
                    model = result["evaluation"]["model"]
                    template = result["evaluation"]["template"]
                    score = result["evaluation"]["score"]
                    print(f"    ✓ {model} - {template}: {score}/100 ({result['elapsed']:.1f}s)")
                else:
                    print(f"    ❌ {result['model']} - {result['template']}: {result['error']}")
        
        # Rank concepts by score
        evaluations_for_style.sort(key=lambda x: x["score"], reverse=True)
        
        # Add style evaluation group
        all_evaluations.append({
            "ad_style": ad_style,
            "brand_name": brand_name,
            "judge_model": judge_model,
            "timestamp": datetime.now().isoformat(),
            "evaluations": evaluations_for_style
        })
    
    # Save results with judge model name in filename
    timestamp = datetime.now().strftime("%m%d_%H%M")
    
    # Create judge short name for filename
    judge_short_name = judge_model.split('/')[-1].replace('claude-sonnet-4-5-20250929', 'claude_4.5').replace('gpt-5.1', 'gpt_5.1')
    
    # Save full JSON
    json_path = os.path.join(output_dir, f"{brand_name.lower()}_evaluation_{judge_short_name}_{timestamp}.json")
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump({
            "summary": {
                "brand": brand_name,
                "judge_model": judge_model,
                "timestamp": datetime.now().isoformat(),
                "total_styles_evaluated": len(all_evaluations)
            },
            "evaluations": all_evaluations
        }, f, indent=2)
    
    # Save CSV report
    csv_path = os.path.join(output_dir, f"{brand_name.lower()}_scores_{judge_short_name}_{timestamp}.csv")
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["Brand", "Ad Style", "Model", "Template", "Score", "Rank", "Strengths", "Weaknesses", "Explanation"])
        
        for eval_group in all_evaluations:
            ad_style = eval_group["ad_style"]
            evaluations = eval_group["evaluations"]
            
            for rank, eval_item in enumerate(evaluations, 1):
                strengths = ", ".join(eval_item.get("strengths", []))
                weaknesses = ", ".join(eval_item.get("weaknesses", []))
                explanation = eval_item.get("explanation", "")
                
                writer.writerow([
                    brand_name,
                    ad_style,
                    eval_item["model"],
                    eval_item["template"],
                    eval_item["score"],
                    rank,
                    strengths,
                    weaknesses,
                    explanation
                ])
    
    print(f"\n{'='*80}")
    print(f"EVALUATION COMPLETE")
    print(f"{'='*80}")
    print(f"Full report: {json_path}")
    print(f"Score table: {csv_path}")
    print(f"{'='*80}\n")
    
    return json_path, csv_path


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python judge_concepts.py <batch_summary.json> [judge_model] [output_dir]")
        print("\nExample:")
        print("  python judge_concepts.py ../../s1_generate_concepts/outputs/rolex_1115_1833/rolex_batch_summary_1115_1833.json")
        print("  python judge_concepts.py ../../s1_generate_concepts/outputs/rolex_1115_1833/rolex_batch_summary_1115_1833.json anthropic/claude-sonnet-4-5-20250929")
        print("  python judge_concepts.py ../../s1_generate_concepts/outputs/rolex_1115_1833/rolex_batch_summary_1115_1833.json anthropic/claude-sonnet-4-5-20250929 ../outputs")
        print("\nDefault judge model: anthropic/claude-sonnet-4-5-20250929")
        print("Default output directory: ../outputs")
        sys.exit(1)
    
    summary_path = sys.argv[1]
    judge_model = sys.argv[2] if len(sys.argv) > 2 else "anthropic/claude-sonnet-4-5-20250929"
    output_dir = sys.argv[3] if len(sys.argv) > 3 else "../outputs"
    
    if not os.path.exists(summary_path):
        print(f"Error: Summary file not found: {summary_path}")
        sys.exit(1)
    
    judge_batch(summary_path, judge_model, output_dir)

