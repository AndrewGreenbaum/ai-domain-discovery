#!/usr/bin/env python3
"""
Test LLM-Trained Agent System - End-to-End Integration Test

Tests the complete flow:
1. Agent scoring (rule-based)
2. Hybrid decision (when to use LLM)
3. LLM evaluation (Claude API)
4. Feedback collection (auto-add to training data)
5. Auto-retrain trigger

Usage:
    # Test with mock LLM (no API key needed)
    python3 test_llm_system.py --mock

    # Test with real Claude API
    python3 test_llm_system.py

    # Test specific domain
    python3 test_llm_system.py --domain example.ai
"""
import asyncio
import argparse
from typing import Dict
from agents.validation import ValidationAgent
from agents.hybrid_scorer import HybridScorer
from feedback_system import FeedbackSystem
from auto_retrain import AutoRetrainer
from llm_config import LLMConfig


class LLMSystemTester:
    """Test the complete LLM-trained agent system"""

    def __init__(self, use_mock: bool = False):
        self.use_mock = use_mock
        self.validator = ValidationAgent()
        self.hybrid_scorer = HybridScorer()
        self.feedback_system = FeedbackSystem()
        self.retrainer = AutoRetrainer()

    async def test_complete_pipeline(self, domain: str) -> Dict:
        """
        Test complete pipeline for a domain

        Returns:
            Test results dictionary
        """
        print("\n" + "="*100)
        print(f" 🧪 TESTING LLM SYSTEM PIPELINE: {domain}")
        print("="*100 + "\n")

        results = {
            "domain": domain,
            "stages": {},
            "success": True,
            "errors": []
        }

        # Stage 1: Validation
        print("Stage 1: Domain Validation")
        print("-" * 80)
        try:
            validation = await self.validator.validate_domain(domain)
            results["stages"]["validation"] = {
                "success": True,
                "is_live": validation.is_live,
                "is_parking": validation.is_parking,
                "is_for_sale": validation.is_for_sale,
                "http_status": validation.http_status_code
            }
            print(f"  ✓ Domain validated")
            print(f"  - Live: {validation.is_live}")
            print(f"  - Parking: {validation.is_parking}")
            print(f"  - For sale: {validation.is_for_sale}")
        except Exception as e:
            results["success"] = False
            results["errors"].append(f"Validation failed: {str(e)}")
            print(f"  ❌ Validation failed: {str(e)}")
            return results

        # Stage 2: Hybrid Scoring
        print("\nStage 2: Hybrid Scoring (Agent + LLM)")
        print("-" * 80)
        try:
            scoring_result = await self.hybrid_scorer.score_domain(
                domain=domain,
                validation=validation,
                force_llm=False  # Let hybrid scorer decide
            )

            results["stages"]["hybrid_scoring"] = {
                "success": True,
                "agent_score": scoring_result["scoring"].quality_score,
                "final_score": scoring_result["final_score"],
                "final_category": scoring_result["final_category"],
                "evaluation_method": scoring_result["evaluation_method"],
                "llm_used": scoring_result["evaluation_method"] == "AGENT_WITH_LLM",
                "cost_usd": scoring_result["cost_usd"]
            }

            print(f"  ✓ Hybrid scoring completed")
            print(f"  - Agent score: {scoring_result['scoring'].quality_score}/100")
            print(f"  - Final score: {scoring_result['final_score']}/100")
            print(f"  - Category: {scoring_result['final_category']}")
            print(f"  - Method: {scoring_result['evaluation_method']}")

            if scoring_result["llm_result"]:
                llm = scoring_result["llm_result"]
                print(f"\n  LLM Evaluation Details:")
                print(f"  - Verdict: {llm.get('verdict', 'N/A')}")
                print(f"  - Confidence: {llm.get('confidence', 0):.2f}")
                print(f"  - Reasoning: {llm.get('reasoning', 'N/A')[:100]}...")
                print(f"  - Cost: ${llm.get('cost_usd', 0):.4f}")

        except Exception as e:
            results["success"] = False
            results["errors"].append(f"Hybrid scoring failed: {str(e)}")
            print(f"  ❌ Hybrid scoring failed: {str(e)}")
            return results

        # Stage 3: Feedback Collection (if LLM was used)
        if scoring_result["llm_result"]:
            print("\nStage 3: Feedback Collection")
            print("-" * 80)
            try:
                feedback_id = self.feedback_system.add_llm_feedback(
                    domain=domain,
                    llm_result=scoring_result["llm_result"],
                    agent_score=scoring_result["scoring"].quality_score,
                    auto_validate=True
                )

                results["stages"]["feedback"] = {
                    "success": feedback_id > 0,
                    "feedback_id": feedback_id,
                    "auto_validated": True
                }

                if feedback_id > 0:
                    print(f"  ✓ LLM feedback added (ID: {feedback_id})")
                    print(f"  - Auto-validated for training")
                else:
                    print(f"  ⚠️  Feedback not added (confidence too low)")

            except Exception as e:
                results["errors"].append(f"Feedback collection failed: {str(e)}")
                print(f"  ❌ Feedback collection failed: {str(e)}")
        else:
            print("\nStage 3: Feedback Collection")
            print("-" * 80)
            print("  ⊘ Skipped (LLM not used for this domain)")
            results["stages"]["feedback"] = {"success": True, "skipped": True}

        # Stage 4: Check if retrain needed
        print("\nStage 4: Auto-Retrain Check")
        print("-" * 80)
        try:
            retrain_check = await self.retrainer.check_retrain_needed()
            results["stages"]["retrain_check"] = {
                "success": True,
                "retrain_needed": retrain_check["retrain_needed"],
                "new_examples": retrain_check["new_examples_count"],
                "reason": retrain_check["reason"]
            }

            print(f"  ✓ Retrain check completed")
            print(f"  - Retrain needed: {retrain_check['retrain_needed']}")
            print(f"  - New examples: {retrain_check['new_examples_count']}")
            print(f"  - Reason: {retrain_check['reason']}")

        except Exception as e:
            results["errors"].append(f"Retrain check failed: {str(e)}")
            print(f"  ❌ Retrain check failed: {str(e)}")

        # Stage 5: System Statistics
        print("\nStage 5: System Statistics")
        print("-" * 80)
        try:
            hybrid_stats = self.hybrid_scorer.get_statistics()
            llm_stats = self.feedback_system.get_llm_statistics(days=30)

            results["stages"]["statistics"] = {
                "success": True,
                "hybrid_stats": hybrid_stats,
                "llm_stats": llm_stats
            }

            print(f"  ✓ Statistics retrieved")
            print(f"\n  Hybrid Scorer:")
            print(f"  - Total scored: {hybrid_stats['total_scored']}")
            print(f"  - Agent only: {hybrid_stats['agent_only']} ({hybrid_stats['agent_only_pct']}%)")
            print(f"  - LLM evaluated: {hybrid_stats['llm_evaluated']} ({hybrid_stats['llm_evaluated_pct']}%)")
            print(f"  - Avg cost/domain: ${hybrid_stats['avg_cost_per_domain']:.4f}")

            print(f"\n  LLM Evaluations (30 days):")
            print(f"  - Total evaluations: {llm_stats['llm_evaluations_count']}")
            print(f"  - Total cost: ${llm_stats['total_cost_usd']}")
            print(f"  - Avg confidence: {llm_stats['avg_confidence']:.2f}")
            print(f"  - Training ready: {llm_stats['auto_training_ready']} examples")

        except Exception as e:
            results["errors"].append(f"Statistics failed: {str(e)}")
            print(f"  ❌ Statistics failed: {str(e)}")

        # Final summary
        print("\n" + "="*100)
        if results["success"]:
            print(" ✅ PIPELINE TEST PASSED")
        else:
            print(" ❌ PIPELINE TEST FAILED")
            print(f"\nErrors ({len(results['errors'])}):")
            for error in results["errors"]:
                print(f"  - {error}")
        print("="*100 + "\n")

        return results

    async def test_batch_domains(self, domains: list) -> Dict:
        """Test multiple domains in batch"""
        print("\n" + "="*100)
        print(f" 🧪 BATCH TESTING: {len(domains)} domains")
        print("="*100 + "\n")

        batch_results = {
            "total_domains": len(domains),
            "successful": 0,
            "failed": 0,
            "llm_used_count": 0,
            "total_cost": 0.0,
            "domain_results": []
        }

        for i, domain in enumerate(domains, 1):
            print(f"\n[{i}/{len(domains)}] Testing {domain}...")
            result = await self.test_complete_pipeline(domain)

            batch_results["domain_results"].append(result)

            if result["success"]:
                batch_results["successful"] += 1
            else:
                batch_results["failed"] += 1

            # Track LLM usage
            if "hybrid_scoring" in result["stages"]:
                if result["stages"]["hybrid_scoring"].get("llm_used"):
                    batch_results["llm_used_count"] += 1
                    batch_results["total_cost"] += result["stages"]["hybrid_scoring"].get("cost_usd", 0)

        # Print batch summary
        print("\n" + "="*100)
        print(" 📊 BATCH TEST SUMMARY")
        print("="*100)
        print(f"\nDomains tested: {batch_results['total_domains']}")
        print(f"Successful: {batch_results['successful']}")
        print(f"Failed: {batch_results['failed']}")
        print(f"\nLLM Usage:")
        print(f"  - Domains evaluated with LLM: {batch_results['llm_used_count']}")
        print(f"  - Agent-only: {batch_results['total_domains'] - batch_results['llm_used_count']}")
        print(f"  - Total cost: ${batch_results['total_cost']:.4f}")
        print(f"  - Avg cost per LLM call: ${batch_results['total_cost'] / max(batch_results['llm_used_count'], 1):.4f}")
        print("="*100 + "\n")

        return batch_results


async def main():
    parser = argparse.ArgumentParser(description="Test LLM-trained agent system")
    parser.add_argument("--domain", type=str, help="Test specific domain")
    parser.add_argument("--batch", action="store_true", help="Test batch of domains from database")
    parser.add_argument("--mock", action="store_true", help="Use mock LLM (no API calls)")
    parser.add_argument("--config", action="store_true", help="Show and validate configuration")

    args = parser.parse_args()

    # Show configuration
    if args.config:
        LLMConfig.print_config()
        return

    # Validate config first
    validation = LLMConfig.validate_config()
    if not validation["valid"]:
        print("\n❌ Configuration invalid:")
        for issue in validation["issues"]:
            print(f"  - {issue}")
        print("\nFix configuration and try again.")
        return

    tester = LLMSystemTester(use_mock=args.mock)

    if args.domain:
        # Test single domain
        await tester.test_complete_pipeline(args.domain)

    elif args.batch:
        # Test batch from database (uncertain domains)
        print("Loading uncertain domains from database...")
        domains = tester.feedback_system.suggest_domains_for_labeling(limit=5)
        domain_names = [d["domain"] for d in domains]

        if not domain_names:
            print("No uncertain domains found. Testing with example domains...")
            domain_names = ["smartapp.ai", "agent.ai", "botbot.ai"]

        await tester.test_batch_domains(domain_names)

    else:
        # Default: test with example domains
        print("Testing with example domains...")
        test_domains = [
            "smartapp.ai",  # Should be rejected (parking)
            "agent.ai",     # Should score high (real startup)
            "botbot.ai"     # Should be rejected (for sale)
        ]
        await tester.test_batch_domains(test_domains)


if __name__ == "__main__":
    asyncio.run(main())
