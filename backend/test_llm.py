#!/usr/bin/env python3
"""Quick test of unified LLM service"""
import asyncio
from services.llm_evaluator import LLMEvaluator
from models.schemas import ValidationResult

async def test():
    evaluator = LLMEvaluator()
    print(f"LLM available: {evaluator.is_available()}")
    print(f"Model: {evaluator.model}")
    print(f"Mode: {evaluator.scoring_mode}")

    # Test with a sample domain - create ValidationResult object
    validation = ValidationResult(
        domain='test-example.ai',
        is_live=True,
        title='TestAI - AI Writing Assistant',
        meta_description='Generate better content with AI',
        page_content_sample='AI-powered writing tool for everyone'
    )

    result = await evaluator.evaluate_domain('test-example.ai', validation, agent_score=60)
    print(f"\nEvaluation result:")
    print(f"  Verdict: {result.get('verdict')}")
    print(f"  Score: {result.get('suggested_score')}")
    print(f"  Confidence: {result.get('confidence')}")
    cost = result.get('cost_usd', 0)
    print(f"  Cost: ${cost:.6f}")
    print(f"  Has reasoning: {bool(result.get('reasoning'))}")
    if result.get('reasoning'):
        print(f"  Reasoning: {result.get('reasoning')[:150]}...")
    return result

if __name__ == "__main__":
    asyncio.run(test())
