#!/usr/bin/env python3
"""
Auto-Retrain Script - Self-Improving Agent Training Based on LLM Feedback

This script:
1. Monitors LLM feedback accumulation
2. Analyzes patterns in agent vs LLM disagreements
3. Identifies systematic errors and auto-adjusts scoring weights
4. Exports LLM decisions to training dataset
5. Runs training tests to validate improvements
6. Tracks improvement metrics over time

Usage:
    # Check if retraining needed
    python3 auto_retrain.py --check

    # Force retrain now
    python3 auto_retrain.py --force

    # Run self-improvement analysis
    python3 auto_retrain.py --analyze

    # Run continuous monitoring (checks every hour)
    python3 auto_retrain.py --monitor --interval 3600
"""
import asyncio
import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List
from feedback_system import FeedbackSystem
from agent_trainer import AgentTrainer
from utils.logger import logger


class AutoRetrainer:
    """Automatic retraining system based on LLM feedback"""

    def __init__(self):
        self.feedback_system = FeedbackSystem()
        self.trainer = AgentTrainer()

        # Retraining thresholds
        self.min_new_examples = 5  # Minimum new LLM feedback before retraining
        self.min_confidence = 0.7  # Only use high-confidence LLM feedback
        self.max_days_since_training = 7  # Force retrain after 7 days

    async def check_retrain_needed(self) -> Dict:
        """
        Check if retraining is needed based on LLM feedback

        Returns:
            {
                "retrain_needed": bool,
                "reason": str,
                "new_examples_count": int,
                "days_since_last_training": int,
                "recommendation": str
            }
        """
        # Get LLM feedback stats
        llm_stats = self.feedback_system.get_llm_statistics(days=30)
        new_examples = llm_stats.get("auto_training_ready", 0)

        # Get last training run
        history = self.feedback_system.get_performance_trends(days=30)
        days_since_training = self._calculate_days_since_last_training()

        # Determine if retraining needed
        retrain_needed = False
        reason = ""

        if new_examples >= self.min_new_examples:
            retrain_needed = True
            reason = f"{new_examples} new high-confidence LLM examples available"
        elif days_since_training >= self.max_days_since_training and new_examples > 0:
            retrain_needed = True
            reason = f"{days_since_training} days since last training, {new_examples} new examples"
        else:
            reason = f"Only {new_examples} new examples (need {self.min_new_examples})"

        result = {
            "retrain_needed": retrain_needed,
            "reason": reason,
            "new_examples_count": new_examples,
            "days_since_last_training": days_since_training,
            "llm_stats": llm_stats,
            "recommendation": self._get_recommendation(retrain_needed, new_examples, days_since_training)
        }

        logger.info(
            "retrain_check_completed",
            retrain_needed=retrain_needed,
            new_examples=new_examples,
            days_since_training=days_since_training
        )

        return result

    async def execute_retrain(self, dry_run: bool = False) -> Dict:
        """
        Execute automatic retraining

        Args:
            dry_run: If True, only simulate (don't actually update agents)

        Returns:
            Training results dict
        """
        print("\n" + "="*100)
        print(" 🤖 AUTO-RETRAIN: Automatic Agent Training from LLM Feedback")
        print("="*100 + "\n")

        # Step 1: Export LLM feedback to training data
        print("Step 1: Exporting LLM feedback to training dataset...")
        training_file = self.feedback_system.export_to_training_data(
            output_path="./training_data_expanded.json"
        )

        # Load expanded training data
        with open(training_file, 'r') as f:
            expanded_data = json.load(f)

        print(f"  ✓ Total training examples: {len(expanded_data['training_examples'])}")
        print(f"  ✓ Training file: {training_file}\n")

        # Step 2: Run training tests with expanded dataset
        print("Step 2: Running training tests with expanded dataset...")
        # Create new trainer with expanded training file
        self.trainer = AgentTrainer(training_data_path=training_file)
        results = await self.trainer.run_training_tests()

        print(f"\n  ✓ Training completed")
        print(f"  ✓ Accuracy: {results['accuracy']*100:.1f}%")
        print(f"  ✓ Correct predictions: {results['correct_predictions']}/{results['total_examples']}")

        # Step 3: Compare with previous performance
        print("\nStep 3: Comparing with previous performance...")
        improvement = self._calculate_improvement(results)

        if improvement["is_better"]:
            print(f"  ✅ IMPROVEMENT: +{improvement['accuracy_gain']*100:.1f}% accuracy")
        else:
            print(f"  ⚠️  NO IMPROVEMENT: {improvement['accuracy_gain']*100:+.1f}% accuracy")

        # Step 4: Record training run
        print("\nStep 4: Recording training run...")
        self.feedback_system.record_training_run(results)
        print("  ✓ Training history updated")

        # Step 5: Update agents if improved (unless dry run)
        if not dry_run:
            if improvement["is_better"]:
                print("\nStep 5: Agents automatically use new training data on next run ✓")
            else:
                print("\nStep 5: No agent update needed (no improvement)")
        else:
            print("\nStep 5: DRY RUN - No changes made")

        # Step 6: Analyze feedback loop effectiveness
        print("\nStep 6: Analyzing feedback loop effectiveness...")
        effectiveness = self.feedback_system.analyze_feedback_loop_effectiveness()
        print(f"  ✓ Feedback loop status: {effectiveness['recommendation']}")

        print("\n" + "="*100)
        print(" ✅ AUTO-RETRAIN COMPLETE")
        print("="*100 + "\n")

        return {
            "success": True,
            "training_results": results,
            "improvement": improvement,
            "effectiveness": effectiveness,
            "dry_run": dry_run
        }

    def _calculate_days_since_last_training(self) -> int:
        """Calculate days since last training run"""
        trends = self.feedback_system.get_performance_trends(days=30)
        if trends["dates"]:
            last_training = trends["dates"][0]
            last_dt = datetime.fromisoformat(last_training)
            days = (datetime.now() - last_dt).days
            return days
        return 999  # No training history

    def _calculate_improvement(self, current_results: Dict) -> Dict:
        """Compare current results with previous training run"""
        trends = self.feedback_system.get_performance_trends(days=30)

        if not trends["accuracy"] or len(trends["accuracy"]) < 2:
            return {
                "is_better": True,
                "accuracy_gain": 0.0,
                "reason": "First training run - no comparison"
            }

        previous_accuracy = trends["accuracy"][0]
        current_accuracy = current_results["accuracy"]
        gain = current_accuracy - previous_accuracy

        return {
            "is_better": gain >= 0,
            "accuracy_gain": gain,
            "previous_accuracy": previous_accuracy,
            "current_accuracy": current_accuracy,
            "reason": "Improved" if gain > 0 else "No improvement"
        }

    def _get_recommendation(self, retrain_needed: bool, new_examples: int, days: int) -> str:
        """Get recommendation based on current state"""
        if retrain_needed and new_examples >= self.min_new_examples * 2:
            return f"IMMEDIATE RETRAIN - {new_examples} high-quality LLM examples ready"
        elif retrain_needed:
            return "RETRAIN RECOMMENDED - Enough new examples available"
        elif new_examples > 0:
            return f"WAIT - Only {new_examples}/{self.min_new_examples} examples, continue collecting"
        else:
            return "OK - No LLM feedback yet, agents running normally"

    async def continuous_monitor(self, interval_seconds: int = 3600):
        """
        Run continuous monitoring loop

        Args:
            interval_seconds: Check interval (default 1 hour)
        """
        print(f"\n🔄 Starting continuous auto-retrain monitoring (interval: {interval_seconds}s)")

        while True:
            try:
                # Check if retraining needed
                check_result = await self.check_retrain_needed()

                print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Retrain check:")
                print(f"  - New examples: {check_result['new_examples_count']}")
                print(f"  - Retrain needed: {check_result['retrain_needed']}")
                print(f"  - Reason: {check_result['reason']}")

                # Execute retrain if needed
                if check_result["retrain_needed"]:
                    print("\n🤖 Triggering automatic retraining...")
                    await self.execute_retrain(dry_run=False)

                # Wait for next check
                await asyncio.sleep(interval_seconds)

            except KeyboardInterrupt:
                print("\n\n⏹️  Monitoring stopped by user")
                break
            except Exception as e:
                logger.error("auto_retrain_monitor_error", error=str(e))
                print(f"\n❌ Error in monitor loop: {str(e)}")
                await asyncio.sleep(interval_seconds)


class SelfImprovingLoop:
    """
    Self-improving agent loop that learns from LLM feedback.

    Analyzes where agents disagree with LLM, identifies patterns,
    and suggests/applies parameter adjustments.
    """

    def __init__(self, db_path: str = "./aidomains.db"):
        self.db_path = db_path
        self.feedback_system = FeedbackSystem(db_path)
        self.weight_tuner = AgentWeightTuner()

        # Thresholds
        self.min_samples = 10
        self.significant_diff_threshold = 15  # Points difference

    async def analyze_patterns(self) -> Dict:
        """Analyze LLM feedback to find agent error patterns"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get recent LLM evaluations
        cursor.execute("""
            SELECT details
            FROM performance_metrics
            WHERE metric_type = 'llm_evaluation'
              AND measured_at >= datetime('now', '-7 days')
        """)

        evaluations = []
        for row in cursor.fetchall():
            try:
                details = json.loads(row[0])
                evaluations.append(details)
            except:
                continue

        conn.close()

        if len(evaluations) < self.min_samples:
            return {"status": "insufficient_data", "count": len(evaluations)}

        # Analyze score differences
        score_diffs = []
        by_verdict = {}

        for eval in evaluations:
            agent = eval.get("agent_score", 50)
            llm = eval.get("llm_score", 50)
            verdict = eval.get("llm_verdict", "UNKNOWN")
            confidence = eval.get("confidence", 0)

            if confidence >= 0.7:  # Only high-confidence
                diff = llm - agent
                score_diffs.append(diff)

                if verdict not in by_verdict:
                    by_verdict[verdict] = []
                by_verdict[verdict].append(diff)

        # Calculate stats
        avg_diff = sum(score_diffs) / len(score_diffs) if score_diffs else 0
        issues = []

        # Overall bias
        if abs(avg_diff) > self.significant_diff_threshold:
            direction = "under" if avg_diff > 0 else "over"
            issues.append({
                "type": f"agent_{direction}_scoring",
                "avg_diff": round(avg_diff, 1),
                "action": f"Adjust base score by {int(avg_diff // 2)}"
            })

        # Category-specific bias
        for verdict, diffs in by_verdict.items():
            if len(diffs) >= 5:
                cat_avg = sum(diffs) / len(diffs)
                if abs(cat_avg) > 20:
                    issues.append({
                        "type": f"category_bias_{verdict}",
                        "avg_diff": round(cat_avg, 1),
                        "samples": len(diffs),
                        "action": f"Adjust {verdict} scoring by {int(cat_avg // 2)}"
                    })

        return {
            "status": "analyzed",
            "total_evaluations": len(evaluations),
            "high_confidence_count": len(score_diffs),
            "avg_score_diff": round(avg_diff, 2),
            "verdict_distribution": {k: len(v) for k, v in by_verdict.items()},
            "issues_found": issues
        }

    async def run_improvement_cycle(self) -> Dict:
        """Run one self-improvement cycle"""
        logger.info("self_improvement_cycle_started")

        analysis = await self.analyze_patterns()

        if analysis["status"] == "insufficient_data":
            return {
                "status": "skipped",
                "reason": f"Only {analysis['count']} samples (need {self.min_samples})"
            }

        improvements = []
        for issue in analysis.get("issues_found", []):
            if issue["type"] == "agent_under_scoring":
                adj = min(10, abs(int(issue["avg_diff"] // 2)))
                self.weight_tuner.adjust_base_score(adj)
                improvements.append(f"Increased base score by {adj}")

            elif issue["type"] == "agent_over_scoring":
                adj = min(10, abs(int(issue["avg_diff"] // 2)))
                self.weight_tuner.adjust_base_score(-adj)
                improvements.append(f"Decreased base score by {adj}")

            elif "category_bias" in issue["type"]:
                category = issue["type"].split("_")[-1]
                adj = int(issue["avg_diff"] // 2)
                self.weight_tuner.adjust_category(category, adj)
                improvements.append(f"Adjusted {category} scoring by {adj}")

        # Save analysis
        self._save_analysis(analysis, improvements)

        logger.info("self_improvement_cycle_completed",
                   improvements_count=len(improvements))

        return {
            "status": "completed",
            "analysis": analysis,
            "improvements_applied": improvements
        }

    def _save_analysis(self, analysis: Dict, improvements: List[str]):
        """Save analysis to file"""
        filepath = Path("./improvement_logs")
        filepath.mkdir(exist_ok=True)

        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "analysis": analysis,
            "improvements": improvements
        }

        filename = f"improvement_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
        with open(filepath / filename, 'w') as f:
            json.dump(record, f, indent=2)


class AgentWeightTuner:
    """Auto-tune scoring weights based on LLM feedback"""

    WEIGHTS_FILE = "./scoring_weights.json"

    DEFAULT_WEIGHTS = {
        "version": 1,
        "updated_at": None,
        "base_score_adjustment": 0,
        "category_adjustments": {
            "REAL_STARTUP": 0,
            "FOR_SALE": 0,
            "PARKING": 0,
            "REDIRECT": 0,
            "ESTABLISHED": 0,
            "COMING_SOON": 0
        }
    }

    def __init__(self):
        self.weights = self._load_weights()

    def _load_weights(self) -> Dict:
        try:
            with open(self.WEIGHTS_FILE, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            self._save_weights(self.DEFAULT_WEIGHTS)
            return self.DEFAULT_WEIGHTS.copy()

    def _save_weights(self, weights: Dict):
        weights["updated_at"] = datetime.now(timezone.utc).isoformat()
        with open(self.WEIGHTS_FILE, 'w') as f:
            json.dump(weights, f, indent=2)
        logger.info("scoring_weights_updated", version=weights.get("version", 1))

    def adjust_base_score(self, adjustment: int):
        self.weights["base_score_adjustment"] += adjustment
        self.weights["version"] = self.weights.get("version", 1) + 1
        self._save_weights(self.weights)
        logger.info("base_score_adjusted", adjustment=adjustment,
                   new_total=self.weights["base_score_adjustment"])

    def adjust_category(self, category: str, adjustment: int):
        if category in self.weights["category_adjustments"]:
            self.weights["category_adjustments"][category] += adjustment
            self.weights["version"] = self.weights.get("version", 1) + 1
            self._save_weights(self.weights)
            logger.info("category_adjusted", category=category, adjustment=adjustment)

    def get_adjustment(self, category: str = None) -> int:
        base = self.weights.get("base_score_adjustment", 0)
        cat_adj = 0
        if category:
            cat_adj = self.weights.get("category_adjustments", {}).get(category, 0)
        return base + cat_adj


async def run_self_improvement():
    """Run self-improvement analysis"""
    print("\n" + "="*60)
    print("  SELF-IMPROVING AGENT ANALYSIS")
    print("="*60)

    loop = SelfImprovingLoop()
    result = await loop.run_improvement_cycle()

    print(f"\nStatus: {result['status']}")

    if result['status'] == 'completed':
        analysis = result['analysis']
        print(f"Evaluations Analyzed: {analysis['total_evaluations']}")
        print(f"High Confidence: {analysis['high_confidence_count']}")
        print(f"Avg Score Difference: {analysis['avg_score_diff']}")

        if analysis.get('issues_found'):
            print(f"\nIssues Found ({len(analysis['issues_found'])}):")
            for issue in analysis['issues_found']:
                print(f"  - {issue['type']}: diff={issue['avg_diff']}")
                print(f"    Action: {issue['action']}")

        if result.get('improvements_applied'):
            print(f"\nImprovements Applied ({len(result['improvements_applied'])}):")
            for imp in result['improvements_applied']:
                print(f"  - {imp}")
    else:
        print(f"Reason: {result.get('reason', 'Unknown')}")

    # Show feedback loop stats
    print("\nFeedback Loop Stats:")
    stats = loop.feedback_system.get_llm_statistics(days=7)
    print(f"  LLM Evaluations (7d): {stats.get('llm_evaluations_count', 0)}")
    print(f"  Total Cost: ${stats.get('total_cost_usd', 0):.4f}")
    print(f"  Training Ready: {stats.get('auto_training_ready', 0)}")

    print("\n" + "="*60 + "\n")
    return result


async def main():
    parser = argparse.ArgumentParser(description="Auto-retrain agents based on LLM feedback")
    parser.add_argument("--check", action="store_true", help="Check if retraining is needed")
    parser.add_argument("--force", action="store_true", help="Force retraining now")
    parser.add_argument("--analyze", action="store_true", help="Run self-improvement analysis")
    parser.add_argument("--monitor", action="store_true", help="Run continuous monitoring")
    parser.add_argument("--interval", type=int, default=3600, help="Monitor interval in seconds (default: 3600)")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without making changes")

    args = parser.parse_args()

    retrainer = AutoRetrainer()

    if args.analyze:
        # Run self-improvement analysis
        await run_self_improvement()

    elif args.monitor:
        # Continuous monitoring mode
        await retrainer.continuous_monitor(interval_seconds=args.interval)

    elif args.check:
        # Check only mode
        result = await retrainer.check_retrain_needed()
        print("\n" + "="*80)
        print(" 🔍 RETRAIN CHECK")
        print("="*80)
        print(f"\nRetrain needed: {result['retrain_needed']}")
        print(f"Reason: {result['reason']}")
        print(f"New examples: {result['new_examples_count']}")
        print(f"Days since training: {result['days_since_last_training']}")
        print(f"\nRecommendation: {result['recommendation']}")
        print("\n" + "="*80 + "\n")

    elif args.force:
        # Force retrain mode
        result = await retrainer.execute_retrain(dry_run=args.dry_run)
        if result["success"]:
            print(f"\n✅ Retrain {'simulated' if args.dry_run else 'completed'} successfully!")
        else:
            print("\n❌ Retrain failed!")

    else:
        # Default: check and retrain if needed
        check_result = await retrainer.check_retrain_needed()

        if check_result["retrain_needed"]:
            print(f"\n✅ Retraining needed: {check_result['reason']}")
            print("\nStarting automatic retraining...")
            await retrainer.execute_retrain(dry_run=args.dry_run)
        else:
            print(f"\nℹ️  No retraining needed")
            print(f"Reason: {check_result['reason']}")
            print(f"Recommendation: {check_result['recommendation']}")


if __name__ == "__main__":
    asyncio.run(main())
