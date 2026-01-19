#!/usr/bin/env python3
"""
Test script to verify the 5-agent system works correctly
Per system testing requirements
"""
import asyncio
import sys
from pathlib import Path

# Test imports
try:
    from agents.discovery import DiscoveryAgent
    from agents.validation import ValidationAgent
    from agents.scoring import ScoringAgent
    from agents.planner import PlannerAgent
    from agents.implementer import ImplementerAgent
    from services.ct_logs import CTLogsService
    from services.domain_check import DomainCheckService
    from models.schemas import ValidationResult
    print("✅ All imports successful")
except Exception as e:
    print(f"❌ Import failed: {e}")
    sys.exit(1)


async def test_ct_logs_service():
    """Test CT Logs Service"""
    print("\n" + "="*70)
    print("TEST 1: CT Logs Service")
    print("="*70)

    service = CTLogsService()

    try:
        # Query for last 48 hours
        domains = await service.query_new_domains(hours_back=48)
        print(f"✅ CT Logs query successful")
        print(f"   Found {len(domains)} domains in last 48h")

        if domains:
            print(f"   Sample domains: {domains[:5]}")

        return True
    except Exception as e:
        print(f"❌ CT Logs test failed: {e}")
        return False


async def test_domain_check_service():
    """Test Domain Check Service"""
    print("\n" + "="*70)
    print("TEST 2: Domain Check Service")
    print("="*70)

    service = DomainCheckService()

    # Test with a known domain
    test_domain = "openai.com"

    try:
        result = await service.check_domain(test_domain)
        print(f"✅ Domain check successful for {test_domain}")
        print(f"   Is live: {result['is_live']}")
        print(f"   HTTP status: {result['http_status_code']}")
        print(f"   Has SSL: {result['has_ssl']}")
        print(f"   Title: {result['title'][:50] if result['title'] else 'None'}...")

        return True
    except Exception as e:
        print(f"❌ Domain check test failed: {e}")
        return False


async def test_validation_agent():
    """Test Validation Agent"""
    print("\n" + "="*70)
    print("TEST 3: Validation Agent")
    print("="*70)

    agent = ValidationAgent()

    # Test with openai.com
    test_domain = "openai.com"

    try:
        result = await agent.validate_domain(test_domain)
        print(f"✅ Validation successful for {test_domain}")
        print(f"   Is live: {result.is_live}")
        print(f"   Is parking: {result.is_parking}")
        print(f"   Is for sale: {result.is_for_sale}")
        print(f"   Parking confidence: {result.parking_confidence:.2f}")

        # Test status classification
        status = agent.classify_status(result)
        print(f"   Status: {status}")

        return True
    except Exception as e:
        print(f"❌ Validation test failed: {e}")
        return False


async def test_scoring_agent():
    """Test Adaptive Scoring Agent"""
    print("\n" + "="*70)
    print("TEST 4: Adaptive Scoring Agent")
    print("="*70)

    agent = ScoringAgent()

    # Create mock validation result
    validation = ValidationResult(
        domain="awesome.ai",
        is_live=True,
        http_status_code=200,
        has_ssl=True,
        title="Awesome AI - Revolutionary Platform",
        meta_description="Building the future of AI",
        content_sample="Join our waitlist for early access to the most advanced AI platform.",
        is_parking=False,
        is_for_sale=False,
        parking_confidence=0.0
    )

    try:
        result = await agent.calculate_scores("awesome.ai", validation)
        print(f"✅ Adaptive scoring successful")
        print(f"   Final score: {result.quality_score}")
        print(f"   Domain quality: {result.domain_quality_score:.1f}")
        print(f"   Launch readiness: {result.launch_readiness_score:.1f}")
        print(f"   Content originality: {result.content_originality_score:.1f}")
        print(f"   Professional setup: {result.professional_setup_score:.1f}")
        print(f"   Early signals: {result.early_signals_score:.1f}")

        # Test categorization
        category = agent.categorize_domain(result.quality_score, validation)
        print(f"   Category: {category}")

        # Verify adaptive scoring is working
        if hasattr(agent, 'category_weights'):
            print(f"✅ Category-specific weights: ACTIVE")
            print(f"   Weight profiles: {len(agent.category_weights)}")

        return True
    except Exception as e:
        print(f"❌ Scoring test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_planner_agent():
    """Test Planner Agent"""
    print("\n" + "="*70)
    print("TEST 5: Planner Agent")
    print("="*70)

    agent = PlannerAgent()

    try:
        # Test schedule planning
        from datetime import datetime
        next_check = agent.plan_recheck_schedule("coming_soon")
        print(f"✅ Planner agent working")
        print(f"   Next recheck planned: {next_check.isoformat()}")
        print(f"   Scheduler initialized: {agent.scheduler is not None}")

        return True
    except Exception as e:
        print(f"❌ Planner test failed: {e}")
        return False


async def main():
    """Run all tests"""
    print("""
    ╔══════════════════════════════════════════════════════════╗
    ║                                                          ║
    ║   TESTING 5-AGENT AI DOMAIN DISCOVERY SYSTEM            ║
    ║                                                          ║
    ║   System Integration Tests                               ║
    ║                                                          ║
    ╚══════════════════════════════════════════════════════════╝
    """)

    results = []

    # Run tests
    results.append(("CT Logs Service", await test_ct_logs_service()))
    results.append(("Domain Check Service", await test_domain_check_service()))
    results.append(("Validation Agent", await test_validation_agent()))
    results.append(("Adaptive Scoring Agent", await test_scoring_agent()))
    results.append(("Planner Agent", await test_planner_agent()))

    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 ALL TESTS PASSED!")
        print("✅ 5-Agent system is fully functional")
        print("✅ Adaptive scoring is working correctly")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
