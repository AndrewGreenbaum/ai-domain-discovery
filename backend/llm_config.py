"""
LLM Configuration - Settings for LLM-trained agent system

This file contains all configuration for:
- LLM evaluation (Claude API)
- Hybrid scoring (when to use LLM vs agents)
- Auto-retraining thresholds
- Cost controls
"""
import os
from typing import Dict
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class LLMConfig:
    """Configuration for LLM evaluation system"""

    # ==================== CLAUDE API SETTINGS ====================

    # Model selection (cost vs performance tradeoff)
    # claude-3-haiku-20240307: Cheapest, fastest (~$0.10/day expected)
    # claude-3-5-sonnet-20241022: Best balance of quality + vision (~$1-3/day expected)
    # claude-3-opus-20240229: Best quality (~$5/day expected)
    LLM_MODEL = os.getenv("LLM_MODEL", "claude-3-5-sonnet-20241022")

    # Generation parameters
    LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.3"))  # Low = more consistent
    LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "500"))  # Response length limit

    # API credentials
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")  # Set in .env file

    # ==================== HYBRID SCORING SETTINGS ====================

    # Score thresholds for LLM evaluation
    # Domains scoring in this range will trigger LLM evaluation
    HYBRID_LLM_MIN_SCORE = int(os.getenv("HYBRID_LLM_MIN_SCORE", "40"))
    HYBRID_LLM_MAX_SCORE = int(os.getenv("HYBRID_LLM_MAX_SCORE", "70"))

    # Edge case handling (scores 36-39 and 71-79)
    # If True, also evaluates these edge cases with LLM
    HYBRID_EVALUATE_EDGES = os.getenv("HYBRID_EVALUATE_EDGES", "true").lower() == "true"

    # Force LLM evaluation for all domains (expensive, for testing only)
    HYBRID_FORCE_LLM_ALL = os.getenv("HYBRID_FORCE_LLM_ALL", "false").lower() == "true"

    # ==================== FEEDBACK & TRAINING SETTINGS ====================

    # Minimum LLM confidence to add as training feedback
    FEEDBACK_MIN_CONFIDENCE = float(os.getenv("FEEDBACK_MIN_CONFIDENCE", "0.7"))

    # Auto-validate LLM feedback (trust LLM decisions)
    FEEDBACK_AUTO_VALIDATE = os.getenv("FEEDBACK_AUTO_VALIDATE", "true").lower() == "true"

    # Minimum new examples before triggering auto-retrain
    RETRAIN_MIN_EXAMPLES = int(os.getenv("RETRAIN_MIN_EXAMPLES", "5"))

    # Maximum days between training runs (force retrain if exceeded)
    RETRAIN_MAX_DAYS = int(os.getenv("RETRAIN_MAX_DAYS", "7"))

    # Auto-retrain monitoring interval (seconds)
    RETRAIN_MONITOR_INTERVAL = int(os.getenv("RETRAIN_MONITOR_INTERVAL", "3600"))  # 1 hour

    # ==================== COST CONTROLS ====================

    # Daily LLM evaluation budget (USD)
    COST_DAILY_BUDGET = float(os.getenv("COST_DAILY_BUDGET", "1.0"))

    # Pause LLM evaluations if daily budget exceeded
    COST_PAUSE_ON_BUDGET_EXCEEDED = os.getenv("COST_PAUSE_ON_BUDGET_EXCEEDED", "true").lower() == "true"

    # Alert when approaching budget (% of daily budget)
    COST_ALERT_THRESHOLD = float(os.getenv("COST_ALERT_THRESHOLD", "0.8"))  # 80%

    # ==================== SYSTEM BEHAVIOR ====================

    # Enable LLM evaluation system (master switch)
    LLM_ENABLED = os.getenv("LLM_ENABLED", "true").lower() == "true"

    # Fallback behavior when LLM unavailable
    # "agent_only": Use agent scores (default)
    # "reject_uncertain": Reject all uncertain domains
    FALLBACK_MODE = os.getenv("FALLBACK_MODE", "agent_only")

    # Log LLM requests/responses for debugging
    LOG_LLM_REQUESTS = os.getenv("LOG_LLM_REQUESTS", "false").lower() == "true"

    @classmethod
    def get_config_dict(cls) -> Dict:
        """Get all config as dictionary"""
        return {
            "llm_api": {
                "model": cls.LLM_MODEL,
                "temperature": cls.LLM_TEMPERATURE,
                "max_tokens": cls.LLM_MAX_TOKENS,
                "enabled": cls.LLM_ENABLED,
                "api_key_set": bool(cls.ANTHROPIC_API_KEY)
            },
            "hybrid_scoring": {
                "min_score": cls.HYBRID_LLM_MIN_SCORE,
                "max_score": cls.HYBRID_LLM_MAX_SCORE,
                "evaluate_edges": cls.HYBRID_EVALUATE_EDGES,
                "force_all": cls.HYBRID_FORCE_LLM_ALL
            },
            "feedback": {
                "min_confidence": cls.FEEDBACK_MIN_CONFIDENCE,
                "auto_validate": cls.FEEDBACK_AUTO_VALIDATE,
                "retrain_min_examples": cls.RETRAIN_MIN_EXAMPLES,
                "retrain_max_days": cls.RETRAIN_MAX_DAYS
            },
            "cost_controls": {
                "daily_budget_usd": cls.COST_DAILY_BUDGET,
                "pause_on_exceeded": cls.COST_PAUSE_ON_BUDGET_EXCEEDED,
                "alert_threshold": cls.COST_ALERT_THRESHOLD
            },
            "system": {
                "fallback_mode": cls.FALLBACK_MODE,
                "log_requests": cls.LOG_LLM_REQUESTS
            }
        }

    @classmethod
    def validate_config(cls) -> Dict:
        """Validate configuration and return status"""
        issues = []
        warnings = []

        # Check API key
        if not cls.ANTHROPIC_API_KEY:
            if cls.LLM_ENABLED:
                issues.append("ANTHROPIC_API_KEY not set but LLM_ENABLED=true")
            else:
                warnings.append("ANTHROPIC_API_KEY not set - LLM features disabled")

        # Check score range
        if cls.HYBRID_LLM_MIN_SCORE >= cls.HYBRID_LLM_MAX_SCORE:
            issues.append(f"HYBRID_LLM_MIN_SCORE ({cls.HYBRID_LLM_MIN_SCORE}) must be < MAX_SCORE ({cls.HYBRID_LLM_MAX_SCORE})")

        # Check confidence threshold
        if not (0 <= cls.FEEDBACK_MIN_CONFIDENCE <= 1):
            issues.append(f"FEEDBACK_MIN_CONFIDENCE ({cls.FEEDBACK_MIN_CONFIDENCE}) must be between 0 and 1")

        # Check budget
        if cls.COST_DAILY_BUDGET <= 0:
            warnings.append(f"COST_DAILY_BUDGET ({cls.COST_DAILY_BUDGET}) is very low - LLM may be underutilized")

        # Check retrain thresholds
        if cls.RETRAIN_MIN_EXAMPLES < 3:
            warnings.append(f"RETRAIN_MIN_EXAMPLES ({cls.RETRAIN_MIN_EXAMPLES}) is low - may retrain too frequently")

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "config": cls.get_config_dict()
        }

    @classmethod
    def print_config(cls):
        """Print configuration in readable format"""
        print("\n" + "="*80)
        print(" 🤖 LLM-TRAINED AGENT SYSTEM CONFIGURATION")
        print("="*80 + "\n")

        validation = cls.validate_config()

        config = validation["config"]

        print("LLM API:")
        print(f"  Model: {config['llm_api']['model']}")
        print(f"  Temperature: {config['llm_api']['temperature']}")
        print(f"  Max tokens: {config['llm_api']['max_tokens']}")
        print(f"  Enabled: {config['llm_api']['enabled']}")
        print(f"  API key configured: {config['llm_api']['api_key_set']}")

        print("\nHybrid Scoring:")
        print(f"  LLM evaluation range: {config['hybrid_scoring']['min_score']}-{config['hybrid_scoring']['max_score']}")
        print(f"  Evaluate edge cases: {config['hybrid_scoring']['evaluate_edges']}")
        print(f"  Force LLM for all: {config['hybrid_scoring']['force_all']}")

        print("\nFeedback & Training:")
        print(f"  Min confidence for feedback: {config['feedback']['min_confidence']}")
        print(f"  Auto-validate LLM feedback: {config['feedback']['auto_validate']}")
        print(f"  Auto-retrain after {config['feedback']['retrain_min_examples']} examples")
        print(f"  Force retrain after {config['feedback']['retrain_max_days']} days")

        print("\nCost Controls:")
        print(f"  Daily budget: ${config['cost_controls']['daily_budget_usd']}")
        print(f"  Pause on exceeded: {config['cost_controls']['pause_on_exceeded']}")
        print(f"  Alert at: {int(config['cost_controls']['alert_threshold']*100)}% of budget")

        print("\nSystem:")
        print(f"  Fallback mode: {config['system']['fallback_mode']}")
        print(f"  Log LLM requests: {config['system']['log_requests']}")

        # Show issues/warnings
        if validation["issues"]:
            print("\n❌ CONFIGURATION ISSUES:")
            for issue in validation["issues"]:
                print(f"  - {issue}")

        if validation["warnings"]:
            print("\n⚠️  WARNINGS:")
            for warning in validation["warnings"]:
                print(f"  - {warning}")

        if validation["valid"]:
            print("\n✅ Configuration is valid")
        else:
            print("\n❌ Configuration has errors - please fix before running")

        print("\n" + "="*80 + "\n")


# Create singleton instance
config = LLMConfig()


if __name__ == "__main__":
    # Print and validate configuration
    LLMConfig.print_config()
