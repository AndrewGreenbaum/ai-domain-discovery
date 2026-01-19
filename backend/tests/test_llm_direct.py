#!/usr/bin/env python3
"""Direct test of Claude API"""
import asyncio
from dotenv import load_dotenv
load_dotenv()

from services.llm_evaluator import LLMEvaluator
from models.schemas import ValidationResult

async def test_claude():
    print("\n🧪 Testing Claude API directly...")
    print("="*80)

    evaluator = LLMEvaluator()

    if not evaluator.is_available():
        print("❌ LLM Evaluator not available (API key missing)")
        return

    print(f"✓ LLM Evaluator ready")
    print(f"  Model: {evaluator.model}")
    print(f"  Temperature: {evaluator.temperature}")
    print(f"  Max tokens: {evaluator.max_tokens}\n")

    # Create a mock validation result for an uncertain domain
    validation = ValidationResult(
        domain="example.ai",
        is_live=True,
        http_status_code=200,
        has_ssl=True,
        title="Example AI Platform - Coming Soon",
        meta_description="AI-powered platform launching soon",
        content_sample="We're building an innovative AI platform. Join our waitlist to be notified when we launch!",
        is_parking=False,
        is_for_sale=False,
        is_redirect=False,
        parking_confidence=0.0
    )

    print("📤 Calling Claude API (this may take 2-5 seconds)...")
    result = await evaluator.evaluate_domain("example.ai", validation, agent_score=55)

    print("\n📥 Claude Response:")
    print(f"  Verdict: {result['verdict']}")
    print(f"  Confidence: {result['confidence']}")
    print(f"  Suggested Score: {result['suggested_score']}/100")
    print(f"  Reasoning: {result['reasoning'][:150]}...")
    print(f"  Key indicators: {', '.join(result['key_indicators'][:5])}")
    print(f"  Cost: ${result['cost_usd']:.4f}")

    print("\n✅ Claude API test successful!")
    print("="*80)

if __name__ == "__main__":
    asyncio.run(test_claude())
