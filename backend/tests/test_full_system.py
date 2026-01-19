#!/usr/bin/env python3
"""
Full system test - Test Phase 1 & 2 detection on key domains
"""
import asyncio
from agents.validation import ValidationAgent
from agents.scoring import ScoringAgent

async def test_domain(domain: str, description: str):
    """Test a single domain through the full pipeline"""
    print("\n" + "="*80)
    print(f" 🧪 TESTING: {domain}")
    print(f" Description: {description}")
    print("="*80)

    validator = ValidationAgent()
    scorer = ScoringAgent()

    # Validate
    print("\n1️⃣  Running validation...")
    validation = await validator.validate_domain(domain)

    print(f"   ✓ is_live: {validation.is_live}")
    print(f"   ✓ is_redirect: {validation.is_redirect}")
    if validation.is_redirect:
        print(f"   ✓ redirects_to: {validation.final_domain}")
    print(f"   ✓ is_parking: {validation.is_parking}")
    print(f"   ✓ title: {validation.title or 'N/A'}")

    # Score
    print("\n2️⃣  Running scoring...")
    score_result = await scorer.calculate_scores(domain, validation)

    print(f"   ✓ quality_score: {score_result.quality_score}/100")

    # Check for penalties
    print("\n3️⃣  Checking detections...")

    if validation.is_redirect:
        print(f"   🚨 PHASE 1 PENALTY: Redirect detected to {validation.final_domain}")

    if validation.is_live and not validation.is_redirect:
        page_content = validation.content_sample or ""
        title = validation.title or ""

        parent_company = scorer.investigator.extract_parent_company(page_content, title)
        founding_year = scorer.investigator.extract_founding_year(page_content)
        company_age = scorer.investigator.calculate_company_age(founded_year=founding_year)
        is_established, signals = scorer.investigator.detect_established_signals(page_content)

        if parent_company:
            print(f"   🚨 PHASE 2 PENALTY: Parent company '{parent_company}' detected")
        if company_age and company_age > 3:
            print(f"   🚨 PHASE 2 PENALTY: Company age {company_age} years (> 3 years)")
        if is_established:
            print(f"   🚨 PHASE 2 PENALTY: Established signals: {', '.join(signals)}")

    # Verdict
    print("\n4️⃣  VERDICT:")
    if score_result.quality_score <= 20:
        print(f"   ❌ REJECTED - Score: {score_result.quality_score}/100 (Established company)")
    elif score_result.quality_score >= 70:
        print(f"   ✅ HIGH QUALITY - Score: {score_result.quality_score}/100 (Legitimate startup)")
    else:
        print(f"   ⚠️  MEDIUM - Score: {score_result.quality_score}/100")

    print()

async def main():
    """Test multiple domains"""

    print("\n" + "="*80)
    print(" 🔬 FULL SYSTEM TEST - Phase 1 & 2 Detection")
    print("="*80)

    test_cases = [
        # Known issues (should be penalized)
        ("autoai.ai", "KNOWN ISSUE: Redirects to h2o.ai (established 2012)"),
        ("gen.ai", "KNOWN ISSUE: Owned by Picsart (founded 2011)"),

        # Other test cases
        ("chatbot.ai", "Should be high quality if not redirect"),
        ("agent.ai", "Should be high quality if not redirect"),
        ("smart.ai", "May redirect to smart.com"),
    ]

    for domain, description in test_cases:
        await test_domain(domain, description)

    print("="*80)
    print(" ✅ TESTING COMPLETE")
    print("="*80 + "\n")

if __name__ == "__main__":
    asyncio.run(main())
