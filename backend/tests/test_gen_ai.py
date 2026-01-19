#!/usr/bin/env python3
"""
Test gen.ai to understand parent company detection needs
"""
import asyncio
from services.domain_check import DomainCheckService
from agents.validation import ValidationAgent
from agents.scoring import ScoringAgent
from agents.investigator import InvestigatorAgent

async def test_gen_ai():
    """Test gen.ai for parent company detection"""

    print("\n" + "="*80)
    print(" 🧪 TESTING gen.ai - Parent Company Detection")
    print("="*80 + "\n")

    # Step 1: Domain Check
    print("1️⃣  Running domain check...")
    checker = DomainCheckService()
    check_result = await checker.check_domain("gen.ai")

    print(f"   ✓ is_live: {check_result['is_live']}")
    print(f"   ✓ is_redirect: {check_result.get('is_redirect', False)}")
    print(f"   ✓ final_domain: {check_result.get('final_domain', 'N/A')}")
    print(f"   ✓ title: {check_result.get('title', 'N/A')}")
    print(f"   ✓ meta_description: {check_result.get('meta_description', 'N/A')[:80]}...")

    # Step 2: Validation
    print("\n2️⃣  Running validation agent...")
    validator = ValidationAgent()
    validation = await validator.validate_domain("gen.ai")

    print(f"   ✓ is_redirect: {validation.is_redirect}")
    print(f"   ✓ is_parking: {validation.is_parking}")

    # Step 3: Current Scoring (without parent company detection)
    print("\n3️⃣  Running scoring agent (current - no parent company check yet)...")
    scorer = ScoringAgent()
    score_result = await scorer.calculate_scores("gen.ai", validation)

    print(f"   ✓ quality_score: {score_result.quality_score}/100")

    # Step 4: Test parent company detection methods
    print("\n4️⃣  Testing parent company detection methods...")
    investigator = InvestigatorAgent()

    # Fetch page content
    page_content = await investigator._fetch_page_content("https://gen.ai")

    # Test parent company extraction
    parent_company = investigator.extract_parent_company(
        page_content,
        check_result.get('title', '')
    )
    print(f"   ✓ Parent company detected: {parent_company or 'None'}")

    # Test founding year extraction
    founding_year = investigator.extract_founding_year(page_content)
    print(f"   ✓ Founding year detected: {founding_year or 'None'}")

    # Test company age
    company_age = investigator.calculate_company_age(founded_year=founding_year)
    print(f"   ✓ Company age: {company_age or 'Unknown'} years")

    # Test established signals
    is_established, signals = investigator.detect_established_signals(page_content)
    print(f"   ✓ Established company: {is_established}")
    print(f"   ✓ Signals found: {signals}")

    # Test WHOIS lookup
    print("\n5️⃣  Running WHOIS lookup...")
    whois_data = investigator.lookup_whois("gen.ai")
    print(f"   ✓ Creation date: {whois_data.get('creation_date', 'Unknown')}")
    print(f"   ✓ Registrar: {whois_data.get('registrar', 'Unknown')}")
    print(f"   ✓ Organization: {whois_data.get('org', 'Unknown')}")

    # Step 6: Determine if should be penalized
    print("\n6️⃣  ANALYSIS:")
    should_penalize = False
    reasons = []

    if parent_company:
        should_penalize = True
        reasons.append(f"Owned by {parent_company}")

    if company_age and company_age > 3:
        should_penalize = True
        reasons.append(f"Company is {company_age} years old (> 3 years)")

    if is_established:
        should_penalize = True
        reasons.append(f"Established company signals: {', '.join(signals)}")

    print("\n" + "="*80)
    print(" 📊 RESULTS SUMMARY")
    print("="*80)
    print(f" Domain: gen.ai")
    print(f" Title: {check_result.get('title', 'N/A')}")
    print(f" Parent Company: {parent_company or 'Not detected'}")
    print(f" Company Age: {company_age or 'Unknown'} years")
    print(f" Established Signals: {len(signals)}")
    print(f" ")
    print(f" CURRENT Score: {score_result.quality_score}/100")
    print(f" Should Penalize: {'YES' if should_penalize else 'NO'}")
    if should_penalize:
        print(f" Reasons:")
        for reason in reasons:
            print(f"   - {reason}")
    print(f" Expected NEW Score: ≤20/100")
    print("="*80 + "\n")

if __name__ == "__main__":
    asyncio.run(test_gen_ai())
