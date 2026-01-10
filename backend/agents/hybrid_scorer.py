"""
HYBRID_SCORER - Intelligent routing between rule-based agents and LLM evaluation

This scorer:
1. Uses fast/free rule-based agents for clear cases (80% of domains)
2. Calls LLM only for uncertain cases (scores 40-70) - OR ALL live domains in aggressive mode
3. Auto-feeds LLM decisions back to training data
4. Enables agents to learn from LLM over time, reducing LLM dependency

MODES:
- CONSERVATIVE: LLM only for uncertain cases (40-70 score) - ~$0.30/month
- MODERATE: LLM for expanded range (35-75 score) - ~$1.50/month
- AGGRESSIVE: LLM for ALL live domains - ~$3-5/month
"""
from typing import Dict, Optional
import os
from models.schemas import ValidationResult, ScoringResult
from agents.scoring import ScoringAgent
from services.llm_evaluator import LLMEvaluator
from feedback_system import FeedbackSystem
from utils.logger import logger


class HybridScorer:
    """Hybrid scorer that combines rule-based agents with LLM evaluation"""

    # Scoring modes - EXPANDED RANGES for better coverage
    MODE_CONSERVATIVE = "conservative"  # Expanded from 40-70 to 35-85
    MODE_MODERATE = "moderate"  # Expanded range (30-90) + enrichment
    MODE_AGGRESSIVE = "aggressive"  # ALL live domains

    def __init__(self, mode: str = None):
        self.agent_scorer = ScoringAgent()
        self.llm_evaluator = LLMEvaluator()
        self.feedback_system = FeedbackSystem()  # For continuous training data collection

        # Get mode from settings or use default
        if mode is None:
            try:
                from config.settings import settings
                mode = settings.llm_scoring_mode or self.MODE_AGGRESSIVE
            except:
                mode = os.getenv("LLM_SCORING_MODE", self.MODE_AGGRESSIVE)
        self.mode = mode.lower()

        # Set thresholds based on mode - EXPANDED RANGES
        # We expanded all ranges because established companies were slipping through
        # at high scores (like botchat.ai at 80) without LLM evaluation
        if self.mode == self.MODE_CONSERVATIVE:
            self.llm_min_score = 35  # Was 40 - catch more edge cases
            self.llm_max_score = 85  # Was 70 - catch suspicious high scores
        elif self.mode == self.MODE_MODERATE:
            self.llm_min_score = 30  # Was 35
            self.llm_max_score = 90  # Was 75
        else:  # AGGRESSIVE
            self.llm_min_score = 0
            self.llm_max_score = 100

        logger.info("hybrid_scorer_initialized",
                   mode=self.mode,
                   llm_min_score=self.llm_min_score,
                   llm_max_score=self.llm_max_score)

        # Statistics
        self.stats = {
            "total_scored": 0,
            "agent_only": 0,
            "llm_evaluated": 0,
            "llm_cost_total": 0.0
        }

        # Store last LLM evaluation for implementer to access
        self.last_llm_evaluation = None

    async def score_domain(
        self,
        domain: str,
        validation: ValidationResult,
        force_llm: bool = False
    ) -> Dict:
        """
        Score domain using hybrid approach

        Args:
            domain: Domain name
            validation: Validation result
            force_llm: Force LLM evaluation even for clear cases (for testing)

        Returns:
            {
                "scoring": ScoringResult,
                "final_score": int,
                "final_category": str,
                "evaluation_method": "AGENT_ONLY" | "AGENT_WITH_LLM",
                "llm_result": Dict or None,
                "cost_usd": float
            }
        """
        self.stats["total_scored"] += 1

        # Step 1: Always get agent score first (free & fast)
        agent_result = await self.agent_scorer.calculate_scores(domain, validation)
        agent_score = agent_result.quality_score
        agent_category = self.agent_scorer.categorize_domain(agent_score, validation)

        logger.info(
            "hybrid_scoring_started",
            domain=domain,
            agent_score=agent_score,
            agent_category=agent_category
        )

        # Step 2: Check if we need LLM evaluation
        needs_llm = force_llm or self._should_use_llm(agent_score, validation)

        if not needs_llm:
            # Clear case - trust agents
            self.stats["agent_only"] += 1
            logger.info(
                "agent_decision_confident",
                domain=domain,
                score=agent_score,
                category=agent_category,
                reason="Score outside uncertain range"
            )

            return {
                "scoring": agent_result,
                "final_score": agent_score,
                "final_category": agent_category,
                "evaluation_method": "AGENT_ONLY",
                "llm_result": None,
                "cost_usd": 0.0,
                "reasoning": "Agent score is confident (outside 40-70 range)"
            }

        # Step 3: Uncertain case - use LLM
        if not self.llm_evaluator.is_available():
            logger.warning(
                "llm_unavailable_fallback_to_agent",
                domain=domain,
                agent_score=agent_score
            )
            self.stats["agent_only"] += 1

            return {
                "scoring": agent_result,
                "final_score": agent_score,
                "final_category": agent_category,
                "evaluation_method": "AGENT_ONLY",
                "llm_result": None,
                "cost_usd": 0.0,
                "reasoning": "LLM unavailable - using agent score"
            }

        # Call LLM for intelligent evaluation
        self.stats["llm_evaluated"] += 1
        logger.info(
            "llm_evaluation_triggered",
            domain=domain,
            agent_score=agent_score,
            reason="Score in uncertain range (40-70)"
        )

        llm_result = await self.llm_evaluator.evaluate_domain(
            domain=domain,
            validation=validation,
            agent_score=agent_score
        )

        # Track cost
        llm_cost = llm_result.get("cost_usd", 0.0)
        self.stats["llm_cost_total"] += llm_cost

        # Step 4: Decide final score (LLM overrides agent in uncertain cases)
        final_score = llm_result.get("suggested_score", agent_score)
        final_category = self._map_llm_verdict_to_category(
            llm_result.get("verdict", "PARKING")
        )

        logger.info(
            "hybrid_scoring_completed",
            domain=domain,
            agent_score=agent_score,
            llm_score=final_score,
            final_category=final_category,
            llm_confidence=llm_result.get("confidence", 0),
            cost_usd=llm_cost
        )

        # CONTINUOUS TRAINING DATA COLLECTION
        # Automatically save high-confidence LLM evaluations as training data
        try:
            self.feedback_system.add_llm_feedback(
                domain=domain,
                llm_result=llm_result,
                agent_score=agent_score,
                auto_validate=True  # High confidence LLM results are auto-validated
            )
            self.stats["training_data_collected"] = self.stats.get("training_data_collected", 0) + 1
            logger.info("training_data_saved", domain=domain, verdict=llm_result.get("verdict"))
        except Exception as e:
            logger.warning("training_data_save_failed", domain=domain, error=str(e))

        return {
            "scoring": agent_result,
            "final_score": final_score,
            "final_category": final_category,
            "evaluation_method": "AGENT_WITH_LLM",
            "llm_result": llm_result,
            "cost_usd": llm_cost,
            "reasoning": llm_result.get("reasoning", "LLM evaluation"),
            "key_indicators": llm_result.get("key_indicators", [])
        }

    def _should_use_llm(self, agent_score: int, validation: ValidationResult) -> bool:
        """
        Determine if LLM evaluation is needed based on current mode

        MODES:
        - CONSERVATIVE: LLM only for uncertain cases (40-70)
        - MODERATE: LLM for expanded range (35-75)
        - AGGRESSIVE: LLM for ALL live domains (builds training data fast)
        """
        # In AGGRESSIVE mode: evaluate ALL live domains
        if self.mode == self.MODE_AGGRESSIVE:
            if validation.is_live:
                logger.debug("aggressive_mode_llm_triggered",
                           domain="unknown",
                           agent_score=agent_score,
                           reason="Live domain in aggressive mode")
                return True
            # Even for non-live, evaluate if there's some content
            if validation.content_sample and len(validation.content_sample) > 100:
                return True
            # Skip dead domains with no content
            return False

        # In MODERATE mode: expanded range (35-75) + live domains with content
        if self.mode == self.MODE_MODERATE:
            if self.llm_min_score <= agent_score <= self.llm_max_score:
                return True
            if validation.is_live and validation.content_sample:
                return True
            return False

        # CONSERVATIVE mode (default): strict range (40-70)
        # Clear reject cases (≤35) - trust agent
        if agent_score <= 35:
            return False

        # Clear accept cases (≥80) - trust agent
        if agent_score >= 80:
            return False

        # Uncertain range (40-70) - use LLM
        if self.llm_min_score <= agent_score <= self.llm_max_score:
            return True

        # Edge cases: 36-39 and 71-79
        # Use LLM if domain is live and has content (worth evaluating)
        if validation.is_live and validation.content_sample:
            return True

        # Default: trust agent
        return False

    def _map_llm_verdict_to_category(self, verdict: str) -> str:
        """Map LLM verdict to our internal category system"""
        mapping = {
            "REAL_STARTUP": "LAUNCHING_NOW",
            "COMING_SOON": "COMING_SOON",
            "FOR_SALE": "INSTANT_REJECT",
            "PARKING": "INSTANT_REJECT",
            "ESTABLISHED": "ESTABLISHED_COMPANY",
            "REDIRECT": "REDIRECT_ESTABLISHED"
        }
        return mapping.get(verdict, "JUST_REGISTERED")

    def get_statistics(self) -> Dict:
        """Get scoring statistics"""
        total = self.stats["total_scored"]
        if total == 0:
            return {
                "total_scored": 0,
                "agent_only_pct": 0,
                "llm_evaluated_pct": 0,
                "avg_cost_per_domain": 0,
                "total_cost": 0,
                "training_data_collected": 0
            }

        return {
            "total_scored": total,
            "agent_only": self.stats["agent_only"],
            "agent_only_pct": round((self.stats["agent_only"] / total) * 100, 1),
            "llm_evaluated": self.stats["llm_evaluated"],
            "llm_evaluated_pct": round((self.stats["llm_evaluated"] / total) * 100, 1),
            "total_cost_usd": round(self.stats["llm_cost_total"], 4),
            "avg_cost_per_domain": round(self.stats["llm_cost_total"] / total, 4),
            "avg_cost_per_llm_call": round(
                self.stats["llm_cost_total"] / self.stats["llm_evaluated"], 4
            ) if self.stats["llm_evaluated"] > 0 else 0,
            "training_data_collected": self.stats.get("training_data_collected", 0),
            "mode": self.mode
        }

    def reset_statistics(self):
        """Reset statistics counters"""
        self.stats = {
            "total_scored": 0,
            "agent_only": 0,
            "llm_evaluated": 0,
            "llm_cost_total": 0.0
        }
