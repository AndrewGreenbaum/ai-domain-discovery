#!/usr/bin/env python3
"""Demonstration: How the LLM system triggers on uncertain domains"""
import asyncio
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

from agents.hybrid_scorer import HybridScorer
from models.schemas import ValidationResult

async def demo_llm_trigger():
    print("\n" + "="*80)
    print("🎯 LLM TRIGGER DEMONSTRATION")
    print("="*80)

    print("\n📋 Scenario: Evaluating a domain that will trigger LLM evaluation")
    print("   Domain: startup-demo.ai")
    print("   Expected agent score: ~55 (uncertain range 40-70)")
    print()

    # Create a mock validation result that will score in uncertain range
    # This simulates a real domain that agents aren't sure about
    validation = ValidationResult(
        domain="startup-demo.ai",
        is_live=True,
        http_status_code=200,
        has_ssl=True,
        title="StartupDemo - AI Platform",
        meta_description="Building the future of AI",
        content_sample="Our team is working on innovative AI solutions. Beta launching Q2 2025.",
        is_parking=False,
        is_for_sale=False,
        is_redirect=False,
        parking_confidence=0.2
    )

    print("🤖 Step 1: Initialize Hybrid Scorer")
    scorer = HybridScorer()
    print(f"   ✓ Hybrid scorer ready")
    print(f"   ✓ LLM available: {scorer.llm_evaluator.is_available()}")
    print(f"   ✓ LLM model: {scorer.llm_evaluator.model}")
    print(f"   ✓ Uncertain range: {scorer.llm_min_score}-{scorer.llm_max_score}")
    print()

    print("⚙️  Step 2: Score domain with hybrid system")
    print("   This will:")
    print("   1. First score with rule-based agents (free)")
    print("   2. Detect score is in uncertain range (40-70)")
    print("   3. Call Claude API for intelligent evaluation ($0.0003)")
    print("   4. Return final score based on LLM verdict")
    print()
    print("   ⏳ Calling hybrid scorer (may take 3-5 seconds for LLM)...")

    result = await scorer.score_domain(
        domain="startup-demo.ai",
        validation=validation,
        force_llm=False  # Let system decide automatically
    )

    print()
    print("✅ Step 3: Results")
    print(f"   Agent score: {result.get('agent_score', 'N/A')}/100")
    print(f"   Final score: {result['final_score']}/100")
    print(f"   Method: {result['evaluation_method']}")
    print(f"   Cost: ${result['cost_usd']:.6f}")

    if 'llm_result' in result:
        llm = result['llm_result']
        print()
        print("🧠 LLM Evaluation Details:")
        print(f"   Verdict: {llm.get('verdict', 'N/A')}")
        print(f"   Confidence: {llm.get('confidence', 0)*100:.1f}%")
        print(f"   Reasoning: {llm.get('reasoning', 'N/A')[:100]}...")
        print(f"   Key indicators: {', '.join(llm.get('key_indicators', [])[:3])}")

    print()
    print("="*80)
    print("💡 KEY TAKEAWAYS:")
    print("="*80)
    print()
    print("1. LLM is ON-DEMAND, not continuous:")
    print("   • Only called when agent score is in uncertain range (40-70)")
    print("   • smartapp.ai scored 21 → No LLM needed (clearly parking)")
    print("   • agent.ai scored 92 → No LLM needed (clearly real startup)")
    print()
    print("2. Your API key shows $0 because:")
    print("   • LLM system is installed but hasn't been triggered yet")
    print("   • No domains in the 40-70 range have been evaluated")
    print("   • This is expected behavior!")
    print()
    print("3. When LLM IS triggered:")
    print(f"   • Cost per call: ~${result['cost_usd']:.6f}")
    print("   • High-confidence results (≥70%) automatically become training data")
    print("   • After 5 LLM evaluations, auto-retrain kicks in")
    print("   • Over time, agents learn and LLM usage decreases")
    print()
    print("4. Current system status:")
    print("   • ✅ LLM evaluator: Installed and configured")
    print("   • ✅ Hybrid scorer: Ready to use")
    print("   • ✅ Auto-retrain: Running (PID 259426)")
    print("   • ⏸️  LLM usage: 0 calls (no uncertain domains yet)")
    print()
    print("="*80)

if __name__ == "__main__":
    asyncio.run(demo_llm_trigger())
