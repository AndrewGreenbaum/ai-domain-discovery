#!/usr/bin/env python3
"""
LLM Training Data Generator

Automatically generates training data by having the LLM evaluate existing domains
in the database. This bootstraps the training dataset without manual labeling.

Usage:
    python generate_training_data.py [--limit 50] [--min-confidence 0.7]

Cost: ~$0.0002/domain = ~$0.02 for 100 domains
"""
import asyncio
import argparse
import json
from datetime import datetime
from pathlib import Path

# Setup path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import select
from services.database import get_db_session, init_db
from services.llm_evaluator import LLMEvaluator
from agents.validation import ValidationAgent
from models.domain import Domain
from feedback_system import FeedbackSystem
from utils.logger import logger


class TrainingDataGenerator:
    """Generate training data using LLM evaluation of existing domains"""

    def __init__(self, min_confidence: float = 0.7):
        self.llm_evaluator = LLMEvaluator()
        self.validation_agent = ValidationAgent()
        self.feedback_system = FeedbackSystem()
        self.min_confidence = min_confidence

        # Statistics
        self.stats = {
            "total_processed": 0,
            "llm_evaluated": 0,
            "high_confidence": 0,
            "training_saved": 0,
            "total_cost": 0.0,
            "errors": 0
        }

    async def generate_from_database(self, limit: int = 50, skip_evaluated: bool = True):
        """
        Generate training data from existing domains in database

        Args:
            limit: Maximum domains to process
            skip_evaluated: Skip domains that already have LLM evaluations
        """
        logger.info("training_data_generation_started",
                   limit=limit,
                   min_confidence=self.min_confidence,
                   skip_evaluated=skip_evaluated)

        if not self.llm_evaluator.is_available():
            logger.error("llm_not_available", message="Set ANTHROPIC_API_KEY in .env")
            return

        async with get_db_session() as db:
            # Get domains to evaluate
            query = select(Domain).where(Domain.is_live == True)

            if skip_evaluated:
                query = query.where(Domain.llm_evaluated_at == None)

            query = query.order_by(Domain.discovered_at.desc()).limit(limit)

            result = await db.execute(query)
            domains = list(result.scalars())

            logger.info("domains_to_process", count=len(domains))

            if not domains:
                logger.info("no_domains_to_process")
                return

            # Process each domain
            for i, domain in enumerate(domains):
                try:
                    logger.info("processing_domain",
                              index=i+1,
                              total=len(domains),
                              domain=domain.domain)

                    await self._process_domain(db, domain)
                    self.stats["total_processed"] += 1

                    # Rate limiting
                    await asyncio.sleep(0.5)

                except Exception as e:
                    logger.error("domain_processing_failed",
                               domain=domain.domain,
                               error=str(e))
                    self.stats["errors"] += 1
                    continue

            # Save final commit
            await db.commit()

        # Print summary
        self._print_summary()

    async def _process_domain(self, db, domain: Domain):
        """Process a single domain - validate, evaluate with LLM, save training data"""

        # Re-validate to get fresh data
        validation = await self.validation_agent.validate_domain(domain.domain)

        if not validation.is_live:
            logger.debug("skipping_non_live_domain", domain=domain.domain)
            return

        # Call LLM for evaluation
        llm_result = await self.llm_evaluator.evaluate_domain(
            domain=domain.domain,
            validation=validation,
            agent_score=domain.quality_score or 50
        )

        self.stats["llm_evaluated"] += 1
        self.stats["total_cost"] += llm_result.get("cost_usd", 0.0)

        # Check confidence
        confidence = llm_result.get("confidence", 0)
        if confidence < self.min_confidence:
            logger.debug("low_confidence_skipped",
                       domain=domain.domain,
                       confidence=confidence,
                       min_required=self.min_confidence)
            return

        self.stats["high_confidence"] += 1

        # Save to database
        domain.llm_evaluated_at = datetime.utcnow()
        domain.llm_category = llm_result.get("category")
        domain.llm_subcategory = llm_result.get("subcategory")
        domain.llm_business_model = llm_result.get("business_model")
        domain.llm_target_audience = llm_result.get("target_audience")
        domain.llm_product_description = llm_result.get("product_description")
        domain.llm_quality_assessment = llm_result.get("quality_assessment")
        domain.llm_is_legitimate = llm_result.get("is_legitimate_startup")
        domain.llm_confidence = confidence
        domain.llm_suggested_score = llm_result.get("suggested_score")
        domain.llm_red_flags = llm_result.get("red_flags", [])
        domain.llm_positive_signals = llm_result.get("positive_signals", [])
        domain.llm_raw_response = llm_result

        # Save to feedback system for training
        feedback_saved = await self._save_to_feedback_system(domain, validation, llm_result)
        if feedback_saved:
            self.stats["training_saved"] += 1

        logger.info("domain_evaluated",
                   domain=domain.domain,
                   verdict=llm_result.get("verdict"),
                   confidence=confidence,
                   suggested_score=llm_result.get("suggested_score"),
                   cost_usd=llm_result.get("cost_usd", 0))

    async def _save_to_feedback_system(self, domain: Domain, validation, llm_result: dict) -> bool:
        """Save LLM evaluation to feedback system for training"""
        try:
            # Prepare feedback entry
            feedback = {
                "domain": domain.domain,
                "timestamp": datetime.utcnow().isoformat(),
                "source": "llm_auto_generation",

                # Agent scores
                "agent_score": domain.quality_score,
                "agent_category": domain.category,

                # LLM evaluation
                "llm_verdict": llm_result.get("verdict"),
                "llm_confidence": llm_result.get("confidence"),
                "llm_suggested_score": llm_result.get("suggested_score"),
                "llm_reasoning": llm_result.get("reasoning"),
                "llm_key_indicators": llm_result.get("key_indicators", []),

                # Validation data
                "is_live": validation.is_live,
                "is_parking": validation.is_parking,
                "is_for_sale": validation.is_for_sale,
                "is_redirect": validation.is_redirect,
                "has_content": bool(validation.content_sample),
                "title": validation.title,

                # Final label (from LLM)
                "final_label": llm_result.get("verdict"),
                "final_score": llm_result.get("suggested_score"),
            }

            # Add to feedback system
            self.feedback_system.add_feedback(feedback)

            return True

        except Exception as e:
            logger.error("feedback_save_failed", domain=domain.domain, error=str(e))
            return False

    def _print_summary(self):
        """Print generation summary"""
        print("\n" + "="*60)
        print("TRAINING DATA GENERATION COMPLETE")
        print("="*60)
        print(f"Total processed:     {self.stats['total_processed']}")
        print(f"LLM evaluated:       {self.stats['llm_evaluated']}")
        print(f"High confidence:     {self.stats['high_confidence']}")
        print(f"Training data saved: {self.stats['training_saved']}")
        print(f"Errors:              {self.stats['errors']}")
        print(f"Total cost:          ${self.stats['total_cost']:.4f}")
        print(f"Cost per domain:     ${self.stats['total_cost']/max(1, self.stats['llm_evaluated']):.4f}")
        print("="*60)

        # Get feedback system stats
        fb_stats = self.feedback_system.get_stats()
        print(f"\nFeedback System Stats:")
        print(f"  Total entries:     {fb_stats.get('total_entries', 0)}")
        print(f"  Training ready:    {fb_stats.get('training_ready', 0)}")
        print("="*60)


async def main():
    parser = argparse.ArgumentParser(description="Generate training data using LLM")
    parser.add_argument("--limit", type=int, default=50,
                       help="Maximum domains to process (default: 50)")
    parser.add_argument("--min-confidence", type=float, default=0.7,
                       help="Minimum confidence to save training data (default: 0.7)")
    parser.add_argument("--include-evaluated", action="store_true",
                       help="Re-evaluate domains that already have LLM results")

    args = parser.parse_args()

    print(f"\nLLM Training Data Generator")
    print(f"===========================")
    print(f"Limit: {args.limit} domains")
    print(f"Min confidence: {args.min_confidence}")
    print(f"Skip evaluated: {not args.include_evaluated}")
    print(f"Estimated cost: ~${args.limit * 0.0002:.2f}")
    print()

    # Confirm
    confirm = input("Continue? [y/N]: ")
    if confirm.lower() != 'y':
        print("Cancelled.")
        return

    # Initialize database
    await init_db()

    # Generate training data
    generator = TrainingDataGenerator(min_confidence=args.min_confidence)
    await generator.generate_from_database(
        limit=args.limit,
        skip_evaluated=not args.include_evaluated
    )


if __name__ == "__main__":
    asyncio.run(main())
