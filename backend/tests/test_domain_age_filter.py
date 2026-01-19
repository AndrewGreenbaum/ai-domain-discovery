#!/usr/bin/env python3
"""
Test Domain Age Filtering - Verify old domains are penalized
Tests the critical fix for agent.ai and similar old domains
"""
import asyncio
from dotenv import load_dotenv
load_dotenv()

from agents.validation import ValidationAgent
from agents.scoring import ScoringAgent

async def test_domain_age_filtering():
    print("\n" + "="*80)
    print("🧪 TESTING DOMAIN AGE FILTERING (Phase 1.5)")
    print("="*80)

    validator = ValidationAgent()
    scorer = ScoringAgent()

    # Test cases: Mix of new and old domains
    test_domains = [
        ("agent.ai", "Expected: OLD (registered 2017) → Score capped at 15/100"),
        ("google.ai", "Expected: OLD → Score capped at 15/100"),
        ("chat.ai", "Expected: Check actual age")
    ]

    for domain, description in test_domains:
        print(f"\n{'─'*80}")
        print(f"Testing: {domain}")
        print(f"Expectation: {description}")
        print(f"{'─'*80}")

        try:
            # Step 1: Validate (includes WHOIS lookup)
            print("  🔍 Step 1: Validation (with WHOIS lookup)...")
            validation = await validator.validate_domain(domain)

            print(f"     ✓ Live: {validation.is_live}")
            print(f"     ✓ Redirect: {validation.is_redirect}")
            if validation.domain_created_date:
                print(f"     ✓ Registration Date: {validation.domain_created_date}")
                print(f"     ✓ Domain Age: {validation.domain_age_days} days")
                print(f"     ✓ Registrar: {validation.registrar}")

                # Check against threshold
                MAX_AGE = 90
                if validation.domain_age_days > MAX_AGE:
                    print(f"     ⚠️  DOMAIN TOO OLD: {validation.domain_age_days} days > {MAX_AGE} threshold")
                else:
                    print(f"     ✅ Domain is NEW: {validation.domain_age_days} days ≤ {MAX_AGE} threshold")
            else:
                print(f"     ⚠️  Could not determine domain age (WHOIS failed)")

            # Step 2: Score (with age penalty)
            print(f"\n  📊 Step 2: Scoring (with Phase 1.5 age penalty)...")
            result = await scorer.calculate_scores(domain, validation)

            print(f"     Final Score: {result.quality_score}/100")
            print(f"     Category: {result.category}")

            # Analyze result
            if validation.domain_age_days and validation.domain_age_days > 90:
                if result.quality_score <= 15:
                    print(f"     ✅ CORRECT: Old domain penalized (score capped at 15)")
                else:
                    print(f"     ❌ BUG: Old domain NOT penalized (score should be ≤15)")
            else:
                print(f"     ℹ️  Domain passed age check or age unknown")

        except Exception as e:
            print(f"     ❌ Error testing {domain}: {e}")

    print("\n" + "="*80)
    print("✅ DOMAIN AGE FILTERING TEST COMPLETE")
    print("="*80)
    print("\nKEY POINTS:")
    print("  • Domains older than 90 days → Capped at 15/100")
    print("  • This prevents old domains from appearing as 'new discoveries'")
    print("  • Catches cases where old domains renew SSL (appearing in CT logs)")
    print("  • agent.ai (2017) should now score ≤15 instead of high score")
    print("="*80 + "\n")

if __name__ == "__main__":
    asyncio.run(test_domain_age_filtering())
