#!/usr/bin/env python3
"""
Feedback System - Continuous Learning and Improvement
Allows users to label domains and improve agent accuracy over time
"""
import sqlite3
import json
from datetime import datetime, timezone
from typing import Optional, Dict, List
from contextlib import contextmanager


class FeedbackSystem:
    """System for collecting feedback and improving agent performance"""

    def __init__(self, db_path: str = "./aidomains.db"):
        self.db_path = db_path
        self._ensure_feedback_tables()

    @contextmanager
    def _get_connection(self):
        """Context manager for safe database connections - prevents leaks"""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # Enable dict-like access
            yield conn
        finally:
            if conn:
                conn.close()

    def _ensure_feedback_tables(self):
        """Create feedback tables if they don't exist"""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Feedback table for user corrections
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS domain_feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    domain_id INTEGER,
                    domain TEXT NOT NULL,
                    ground_truth_label TEXT,
                    reason TEXT,
                    submitted_by TEXT DEFAULT 'manual',
                    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_validated BOOLEAN DEFAULT 0,
                    FOREIGN KEY (domain_id) REFERENCES domains(id)
                )
            """)

            # Training history table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS training_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    total_examples INTEGER,
                    accuracy FLOAT,
                    precision FLOAT,
                    recall FLOAT,
                    training_results JSON,
                    improvements_applied JSON
                )
            """)

            # Performance metrics over time
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS performance_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    measured_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metric_type TEXT,
                    metric_value FLOAT,
                    details JSON
                )
            """)

            conn.commit()

    def add_feedback(
        self,
        domain: str,
        ground_truth: str,
        reason: Optional[str] = None,
        submitted_by: str = "manual"
    ) -> int:
        """
        Add user feedback for a domain

        Args:
            domain: Domain name
            ground_truth: Correct label (REAL_STARTUP, FOR_SALE, PARKING, etc.)
            reason: Why this classification is correct
            submitted_by: Who submitted this feedback

        Returns:
            Feedback ID
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Get domain_id if exists
            cursor.execute("SELECT id FROM domains WHERE domain = ?", (domain,))
            result = cursor.fetchone()
            domain_id = result[0] if result else None

            cursor.execute("""
                INSERT INTO domain_feedback (domain_id, domain, ground_truth_label, reason, submitted_by)
                VALUES (?, ?, ?, ?, ?)
            """, (domain_id, domain, ground_truth, reason, submitted_by))

            feedback_id = cursor.lastrowid
            conn.commit()

        print(f"✅ Feedback added: {domain} → {ground_truth}")
        return feedback_id

    def add_llm_feedback(
        self,
        domain: str,
        llm_result: Dict,
        agent_score: int,
        auto_validate: bool = True
    ) -> int:
        """
        Add LLM evaluation as feedback for automatic training

        This creates the auto-feedback loop:
        LLM evaluates uncertain domain → Saved as feedback → Used in next training run

        Args:
            domain: Domain name
            llm_result: LLM evaluation result dict with verdict, reasoning, confidence
            agent_score: Original agent score (for comparison)
            auto_validate: Whether to auto-validate this feedback (default True)

        Returns:
            Feedback ID
        """
        verdict = llm_result.get("verdict", "PARKING")
        reasoning = llm_result.get("reasoning", "LLM evaluation")
        confidence = llm_result.get("confidence", 0.0)
        llm_score = llm_result.get("suggested_score", agent_score)

        # Only add LLM feedback if high confidence
        if confidence < 0.7:
            print(f"⚠️  Skipping LLM feedback for {domain} - confidence too low ({confidence:.2f})")
            return -1

        # Build detailed reason including LLM insights
        key_indicators = llm_result.get("key_indicators", [])
        reason = f"LLM Evaluation (confidence: {confidence:.2f})\n"
        reason += f"Agent score: {agent_score}, LLM score: {llm_score}\n"
        reason += f"Reasoning: {reasoning}\n"
        if key_indicators:
            reason += f"Key indicators: {', '.join(key_indicators)}"

        # Add feedback
        feedback_id = self.add_feedback(
            domain=domain,
            ground_truth=verdict,
            reason=reason,
            submitted_by="llm_evaluator"
        )

        # Auto-validate if requested (LLM decisions are trusted)
        if auto_validate and feedback_id > 0:
            self.validate_feedback(feedback_id)
            print(f"  ✓ Auto-validated (LLM confidence: {confidence:.2f})")

        # Track LLM usage stats
        self._track_llm_usage(domain, llm_result, agent_score)

        return feedback_id

    def _track_llm_usage(self, domain: str, llm_result: Dict, agent_score: int):
        """Track LLM evaluation usage for analysis"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Store in performance_metrics table
        metrics = {
            "domain": domain,
            "agent_score": agent_score,
            "llm_score": llm_result.get("suggested_score"),
            "llm_verdict": llm_result.get("verdict"),
            "confidence": llm_result.get("confidence"),
            "cost_usd": llm_result.get("cost_usd", 0.0)
        }

        cursor.execute("""
            INSERT INTO performance_metrics (metric_type, metric_value, details)
            VALUES (?, ?, ?)
        """, ("llm_evaluation", llm_result.get("confidence", 0.0), json.dumps(metrics)))

        conn.commit()
        conn.close()

    def get_labeled_examples(self) -> List[Dict]:
        """Get all labeled examples from feedback"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT domain, ground_truth_label, reason, submitted_at
            FROM domain_feedback
            WHERE is_validated = 1
            ORDER BY submitted_at DESC
        """)

        examples = []
        for row in cursor.fetchall():
            examples.append({
                "domain": row[0],
                "ground_truth": row[1],
                "reason": row[2],
                "labeled_at": row[3]
            })

        conn.close()
        return examples

    def export_to_training_data(self, output_path: str = "./training_data_expanded.json"):
        """
        Export all validated feedback to expanded training dataset

        This creates a new training file with both original + user feedback
        """
        # Load original training data
        with open("./training_data.json", 'r') as f:
            training_data = json.load(f)

        # Get user feedback
        labeled_examples = self.get_labeled_examples()

        # Add feedback to training examples
        for feedback in labeled_examples:
            # Convert to training format
            training_example = {
                "domain": feedback["domain"],
                "ground_truth": feedback["ground_truth"],
                "description": feedback.get("reason", "User labeled example"),
                "expected_validation": self._infer_expected_validation(feedback["ground_truth"]),
                "expected_score_range": self._infer_score_range(feedback["ground_truth"]),
                "notes": f"Added from user feedback on {feedback['labeled_at']}",
                "source": "user_feedback"
            }

            # Add if not duplicate
            if not any(e["domain"] == feedback["domain"] for e in training_data["training_examples"]):
                training_data["training_examples"].append(training_example)

        # Update metadata
        training_data["last_updated"] = datetime.now(timezone.utc).isoformat()
        training_data["total_examples"] = len(training_data["training_examples"])

        # Save expanded dataset
        with open(output_path, 'w') as f:
            json.dump(training_data, f, indent=2)

        print(f"✅ Exported {len(training_data['training_examples'])} examples to {output_path}")
        return output_path

    def _infer_expected_validation(self, ground_truth: str) -> Dict:
        """Infer expected validation flags from ground truth label"""
        mapping = {
            "REAL_STARTUP": {"is_live": True, "is_parking": False, "is_for_sale": False, "is_redirect": False},
            "FOR_SALE": {"is_live": True, "is_parking": False, "is_for_sale": True, "is_redirect": False},
            "PARKING": {"is_live": True, "is_parking": True, "is_for_sale": False, "is_redirect": False},
            "REDIRECT": {"is_live": True, "is_parking": False, "is_for_sale": False, "is_redirect": True},
            "ESTABLISHED_COMPANY": {"is_live": True, "is_parking": False, "is_for_sale": False, "is_redirect": False},
            "COMING_SOON": {"is_live": True, "is_parking": False, "is_for_sale": False, "is_redirect": False}
        }
        return mapping.get(ground_truth, {})

    def _infer_score_range(self, ground_truth: str) -> List[int]:
        """Infer expected score range from ground truth label"""
        mapping = {
            "REAL_STARTUP": [80, 100],
            "FOR_SALE": [0, 35],
            "PARKING": [0, 35],
            "REDIRECT": [0, 20],
            "ESTABLISHED_COMPANY": [0, 20],
            "COMING_SOON": [50, 80]
        }
        return mapping.get(ground_truth, [0, 100])

    def record_training_run(self, results: Dict):
        """Record training run results for historical tracking"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO training_history (
                total_examples,
                accuracy,
                precision,
                recall,
                training_results,
                improvements_applied
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            results.get("total_examples", 0),
            results.get("accuracy", 0.0),
            results.get("precision", 0.0),
            results.get("recall", 0.0),
            json.dumps(results),
            json.dumps(results.get("suggested_improvements", []))
        ))

        conn.commit()
        conn.close()

    def get_performance_trends(self, days: int = 30) -> Dict:
        """Get performance trends over time"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT run_at, accuracy, total_examples
            FROM training_history
            WHERE run_at >= datetime('now', '-' || ? || ' days')
            ORDER BY run_at ASC
        """, (days,))

        trends = {
            "dates": [],
            "accuracy": [],
            "total_examples": []
        }

        for row in cursor.fetchall():
            trends["dates"].append(row[0])
            trends["accuracy"].append(row[1])
            trends["total_examples"].append(row[2])

        conn.close()
        return trends

    def validate_feedback(self, feedback_id: int):
        """Mark feedback as validated and ready for training"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE domain_feedback
            SET is_validated = 1
            WHERE id = ?
        """, (feedback_id,))

        conn.commit()
        conn.close()

    def get_pending_feedback(self) -> List[Dict]:
        """Get feedback that hasn't been validated yet"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, domain, ground_truth_label, reason, submitted_at
            FROM domain_feedback
            WHERE is_validated = 0
            ORDER BY submitted_at DESC
        """)

        feedback = []
        for row in cursor.fetchall():
            feedback.append({
                "id": row[0],
                "domain": row[1],
                "ground_truth": row[2],
                "reason": row[3],
                "submitted_at": row[4]
            })

        conn.close()
        return feedback

    def suggest_domains_for_labeling(self, limit: int = 10) -> List[Dict]:
        """
        Suggest domains that would benefit from manual labeling

        Prioritizes:
        - Domains with mid-range scores (40-60) - uncertain
        - Recently discovered domains
        - Domains with no feedback yet
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT d.id, d.domain, d.quality_score, d.is_for_sale, d.is_parking, d.discovered_at
            FROM domains d
            LEFT JOIN domain_feedback f ON d.domain = f.domain
            WHERE f.id IS NULL
              AND d.quality_score BETWEEN 40 AND 60
            ORDER BY d.discovered_at DESC
            LIMIT ?
        """, (limit,))

        suggestions = []
        for row in cursor.fetchall():
            suggestions.append({
                "id": row[0],
                "domain": row[1],
                "current_score": row[2],
                "is_for_sale": bool(row[3]),
                "is_parking": bool(row[4]),
                "discovered_at": row[5]
            })

        conn.close()
        return suggestions

    def get_llm_statistics(self, days: int = 30) -> Dict:
        """
        Get LLM evaluation statistics

        Returns metrics about LLM usage, accuracy, and cost
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get all LLM evaluations in time period
        cursor.execute("""
            SELECT details
            FROM performance_metrics
            WHERE metric_type = 'llm_evaluation'
              AND measured_at >= datetime('now', '-' || ? || ' days')
        """, (days,))

        evaluations = []
        total_cost = 0.0

        for row in cursor.fetchall():
            details = json.loads(row[0])
            evaluations.append(details)
            total_cost += details.get("cost_usd", 0.0)

        # Count feedback by source
        cursor.execute("""
            SELECT submitted_by, COUNT(*) as count
            FROM domain_feedback
            WHERE submitted_at >= datetime('now', '-' || ? || ' days')
            GROUP BY submitted_by
        """, (days,))

        feedback_sources = {}
        for row in cursor.fetchall():
            feedback_sources[row[0]] = row[1]

        conn.close()

        # Calculate stats
        llm_count = len(evaluations)
        avg_confidence = sum(e.get("confidence", 0) for e in evaluations) / llm_count if llm_count > 0 else 0

        # Verdict distribution
        verdict_counts = {}
        for eval in evaluations:
            verdict = eval.get("llm_verdict", "UNKNOWN")
            verdict_counts[verdict] = verdict_counts.get(verdict, 0) + 1

        return {
            "time_period_days": days,
            "llm_evaluations_count": llm_count,
            "total_cost_usd": round(total_cost, 4),
            "avg_cost_per_evaluation": round(total_cost / llm_count, 4) if llm_count > 0 else 0,
            "avg_confidence": round(avg_confidence, 3),
            "verdict_distribution": verdict_counts,
            "feedback_sources": feedback_sources,
            "auto_training_ready": feedback_sources.get("llm_evaluator", 0)
        }

    def analyze_feedback_loop_effectiveness(self) -> Dict:
        """
        Analyze how effective the LLM feedback loop is

        Compares:
        - Agent-only accuracy vs Agent+LLM accuracy
        - LLM agreement with training data
        - Training data growth rate
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get training history
        cursor.execute("""
            SELECT run_at, total_examples, accuracy
            FROM training_history
            ORDER BY run_at DESC
            LIMIT 10
        """)

        history = []
        for row in cursor.fetchall():
            history.append({
                "run_at": row[0],
                "total_examples": row[1],
                "accuracy": row[2]
            })

        # Get LLM feedback count over time
        cursor.execute("""
            SELECT DATE(submitted_at) as date, COUNT(*) as count
            FROM domain_feedback
            WHERE submitted_by = 'llm_evaluator'
              AND submitted_at >= datetime('now', '-30 days')
            GROUP BY DATE(submitted_at)
            ORDER BY date DESC
        """)

        llm_feedback_timeline = {}
        for row in cursor.fetchall():
            llm_feedback_timeline[row[0]] = row[1]

        conn.close()

        # Calculate trends
        if len(history) >= 2:
            accuracy_trend = history[0]["accuracy"] - history[-1]["accuracy"]
            examples_growth = history[0]["total_examples"] - history[-1]["total_examples"]
        else:
            accuracy_trend = 0
            examples_growth = 0

        return {
            "training_runs": len(history),
            "latest_accuracy": history[0]["accuracy"] if history else 0,
            "accuracy_trend": round(accuracy_trend, 3),
            "total_examples": history[0]["total_examples"] if history else 0,
            "examples_growth": examples_growth,
            "llm_feedback_count": sum(llm_feedback_timeline.values()),
            "llm_feedback_per_day": llm_feedback_timeline,
            "is_improving": accuracy_trend > 0,
            "recommendation": self._get_feedback_loop_recommendation(accuracy_trend, examples_growth)
        }

    def _get_feedback_loop_recommendation(self, accuracy_trend: float, examples_growth: int) -> str:
        """Get recommendation based on feedback loop analysis"""
        if accuracy_trend > 0.05:
            return "Excellent - LLM feedback is significantly improving accuracy"
        elif accuracy_trend > 0:
            return "Good - LLM feedback is helping, continue current approach"
        elif examples_growth > 10:
            return "Building dataset - Need more time to see impact"
        else:
            return "Review LLM confidence threshold - May need adjustment"


def interactive_labeling_session():
    """Run an interactive labeling session"""
    feedback_system = FeedbackSystem()

    print("\n" + "="*100)
    print(" 🏷️  INTERACTIVE DOMAIN LABELING SESSION")
    print("="*100 + "\n")

    # Get domains to label
    suggestions = feedback_system.suggest_domains_for_labeling(10)

    if not suggestions:
        print("No domains found that need labeling!")
        return

    print(f"Found {len(suggestions)} domains that would benefit from labeling:\n")

    labels = {
        "1": "REAL_STARTUP",
        "2": "FOR_SALE",
        "3": "PARKING",
        "4": "REDIRECT",
        "5": "ESTABLISHED_COMPANY",
        "6": "COMING_SOON",
        "7": "SKIP"
    }

    for suggestion in suggestions:
        print(f"\nDomain: {suggestion['domain']}")
        print(f"Current Score: {suggestion['current_score']}/100")
        print(f"For Sale: {suggestion['is_for_sale']} | Parking: {suggestion['is_parking']}")
        print(f"\nHow would you classify this domain?")
        print("  1. REAL_STARTUP - Legitimate new startup")
        print("  2. FOR_SALE - Domain marketplace listing")
        print("  3. PARKING - Parking page")
        print("  4. REDIRECT - Redirects to established company")
        print("  5. ESTABLISHED_COMPANY - Company >3 years old")
        print("  6. COMING_SOON - Legitimate pre-launch")
        print("  7. SKIP - Skip this domain")

        choice = input("\nYour choice (1-7): ").strip()

        if choice == "7":
            continue

        if choice in labels:
            label = labels[choice]
            reason = input("Reason (optional): ").strip() or None

            feedback_id = feedback_system.add_feedback(
                domain=suggestion['domain'],
                ground_truth=label,
                reason=reason
            )

            # Auto-validate (use the returned feedback_id, not a second add_feedback call)
            feedback_system.validate_feedback(feedback_id)

    print("\n✅ Labeling session complete!")
    print("\nRun 'python3 agent_trainer.py' to re-train with new examples.")


if __name__ == "__main__":
    interactive_labeling_session()
