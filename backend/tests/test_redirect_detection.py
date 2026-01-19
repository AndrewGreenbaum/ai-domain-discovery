#!/usr/bin/env python3
"""
Quick test to verify redirect detection is working
Tests autoai.ai specifically
"""
import asyncio
from services.domain_check import DomainCheckService
from agents.validation import ValidationAgent
from agents.scoring import ScoringAgent

async def test_redirect_detection():
    """Test that autoai.ai redirect is detected and penalized"""

    print("\n" + "="*80)
    print(" 🧪 TESTING REDIRECT DETECTION - autoai.ai")
    print("="*80 + "\n")

    # Step 1: Domain Check
    print("1️⃣  Running domain check...")
    checker = DomainCheckService()
    check_result = await checker.check_domain("autoai.ai")

    print(f"   ✓ is_live: {check_result['is_live']}")
    print(f"   ✓ is_redirect: {check_result.get('is_redirect', False)}")
    print(f"   ✓ final_domain: {check_result.get('final_domain', 'N/A')}")
    print(f"   ✓ title: {check_result.get('title', 'N/A')[:60]}...")

    # Step 2: Validation
    print("\n2️⃣  Running validation agent...")
    validator = ValidationAgent()
    validation = await validator.validate_domain("autoai.ai")

    print(f"   ✓ is_redirect: {validation.is_redirect}")
    print(f"   ✓ final_url: {validation.final_url}")
    print(f"   ✓ final_domain: {validation.final_domain}")

    # Step 3: Scoring
    print("\n3️⃣  Running scoring agent...")
    scorer = ScoringAgent()
    score_result = await scorer.calculate_scores("autoai.ai", validation)

    print(f"   ✓ quality_score: {score_result.quality_score}/100")
    print(f"   ✓ domain_quality_score: {score_result.domain_quality_score}")
    print(f"   ✓ launch_readiness_score: {score_result.launch_readiness_score}")

    # Step 4: Verify
    print("\n4️⃣  VERIFICATION:")

    if validation.is_redirect:
        print(f"   ✅ REDIRECT DETECTED: {validation.domain} → {validation.final_domain}")
    else:
        print(f"   ❌ REDIRECT NOT DETECTED (BUG!)")

    if score_result.quality_score <= 20:
        print(f"   ✅ PENALTY APPLIED: Score capped at {score_result.quality_score}/100")
    else:
        print(f"   ❌ PENALTY NOT APPLIED: Score still {score_result.quality_score}/100 (BUG!)")

    print("\n" + "="*80)
    print(" 📊 RESULTS SUMMARY")
    print("="*80)
    print(f" Domain: autoai.ai")
    print(f" Redirects to: {validation.final_domain}")
    print(f" OLD Score (before fix): 93/100")
    print(f" NEW Score (after fix): {score_result.quality_score}/100")
    print(f" Expected: ≤20/100")
    print(f" Status: {'✅ PASS' if score_result.quality_score <= 20 else '❌ FAIL'}")
    print("="*80 + "\n")

if __name__ == "__main__":
    asyncio.run(test_redirect_detection())
