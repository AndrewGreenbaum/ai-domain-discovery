#!/usr/bin/env python3
"""
Agent Training and Testing Framework
Validates agent performance against labeled ground truth data
"""
import asyncio
import json
from typing import Dict, List, Tuple
from datetime import datetime
from agents.validation import ValidationAgent
from agents.scoring import ScoringAgent
from utils.logger import logger


class AgentTrainer:
    """Train and evaluate agents using labeled training data"""

    def __init__(self, training_data_path: str = "./training_data.json"):
        self.validator = ValidationAgent()
        self.scorer = ScoringAgent()
        self.training_data = self._load_training_data(training_data_path)
        self.results = {
            "test_run_at": None,
            "total_examples": 0,
            "correct_predictions": 0,
            "accuracy": 0.0,
            "confusion_matrix": {},
            "failures": [],
            "performance_metrics": {},
            "suggested_improvements": []
        }

    def _load_training_data(self, path: str) -> dict:
        """Load labeled training data"""
        with open(path, 'r') as f:
            return json.load(f)

    async def run_training_tests(self) -> Dict:
        """
        Run all training examples and evaluate agent performance

        Returns:
            Comprehensive test results with metrics
        """
        print("\n" + "="*100)
        print(" 🎓 AGENT TRAINING & EVALUATION")
        print("="*100 + "\n")

        self.results["test_run_at"] = datetime.utcnow().isoformat()
        examples = self.training_data["training_examples"]
        self.results["total_examples"] = len(examples)

        print(f"Testing {len(examples)} labeled examples...\n")

        # Test each example
        for i, example in enumerate(examples, 1):
            print(f"[{i}/{len(examples)}] Testing {example['domain']}...")
            await self._test_example(example)

        # Calculate overall metrics
        self._calculate_metrics()

        # Generate improvement suggestions
        self._generate_suggestions()

        # Print results
        self._print_results()

        # Save results to file
        self._save_results()

        return self.results

    async def _test_example(self, example: dict):
        """Test a single training example"""
        domain = example["domain"]
        ground_truth = example["ground_truth"]
        expected_validation = example.get("expected_validation", {})
        expected_score_range = example.get("expected_score_range", [0, 100])

        try:
            # Run validation
            validation = await self.validator.validate_domain(domain)

            # Run scoring
            scoring = await self.scorer.calculate_scores(domain, validation)

            # Compare to ground truth
            prediction_correct = self._evaluate_prediction(
                example, validation, scoring
            )

            if prediction_correct:
                self.results["correct_predictions"] += 1
                status = "✅ PASS"
            else:
                status = "❌ FAIL"
                # Record failure for analysis
                self.results["failures"].append({
                    "domain": domain,
                    "ground_truth": ground_truth,
                    "prediction": self._classify_domain(validation, scoring),
                    "validation": {
                        "is_live": validation.is_live,
                        "is_parking": validation.is_parking,
                        "is_for_sale": validation.is_for_sale,
                        "is_redirect": validation.is_redirect
                    },
                    "score": scoring.quality_score,
                    "expected_score_range": expected_score_range,
                    "notes": example.get("notes", "")
                })

            print(f"   {status} | Ground Truth: {ground_truth} | Score: {scoring.quality_score}/100")

        except Exception as e:
            logger.error("training_test_failed", domain=domain, error=str(e))
            print(f"   ❌ ERROR: {str(e)}")
            self.results["failures"].append({
                "domain": domain,
                "ground_truth": ground_truth,
                "error": str(e)
            })

    def _evaluate_prediction(self, example: dict, validation, scoring) -> bool:
        """
        Evaluate if agent prediction matches ground truth

        Returns:
            True if prediction is correct
        """
        ground_truth = example["ground_truth"]
        expected_validation = example.get("expected_validation", {})
        expected_score_range = example.get("expected_score_range", [0, 100])

        # Check validation flags
        validation_correct = True

        if "is_parking" in expected_validation:
            if validation.is_parking != expected_validation["is_parking"]:
                validation_correct = False

        if "is_for_sale" in expected_validation:
            if validation.is_for_sale != expected_validation["is_for_sale"]:
                validation_correct = False

        if "is_redirect" in expected_validation:
            if validation.is_redirect != expected_validation["is_redirect"]:
                validation_correct = False

        # Check score range
        score_correct = (
            expected_score_range[0] <= scoring.quality_score <= expected_score_range[1]
        )

        # Both must be correct
        return validation_correct and score_correct

    def _classify_domain(self, validation, scoring) -> str:
        """Classify domain based on validation and scoring results"""
        if validation.is_for_sale:
            return "FOR_SALE"
        if validation.is_parking:
            return "PARKING"
        if validation.is_redirect:
            return "REDIRECT"
        if scoring.quality_score >= 80:
            return "REAL_STARTUP"
        if scoring.quality_score <= 20:
            return "ESTABLISHED_COMPANY"
        return "UNCERTAIN"

    def _calculate_metrics(self):
        """Calculate performance metrics"""
        total = self.results["total_examples"]
        correct = self.results["correct_predictions"]

        # Overall accuracy
        self.results["accuracy"] = correct / total if total > 0 else 0.0

        # Category-specific metrics
        test_scenarios = self.training_data.get("test_scenarios", {})

        for scenario_name, scenario in test_scenarios.items():
            if scenario_name in ["parking_detection", "for_sale_detection", "redirect_detection"]:
                self._calculate_detection_metrics(scenario_name, scenario)

    def _calculate_detection_metrics(self, name: str, scenario: dict):
        """Calculate precision, recall, F1 for a detection scenario"""
        true_positives = scenario.get("true_positives", [])
        true_negatives = scenario.get("true_negatives", [])

        # Count correct detections
        tp_correct = 0
        tn_correct = 0

        for failure in self.results["failures"]:
            domain = failure["domain"]

            # Check if this failure affects this scenario
            if name == "parking_detection":
                if domain in true_positives and not failure["validation"]["is_parking"]:
                    pass  # False negative
                elif domain in true_negatives and failure["validation"]["is_parking"]:
                    pass  # False positive
                else:
                    # Correct
                    if domain in true_positives:
                        tp_correct += 1
                    if domain in true_negatives:
                        tn_correct += 1

            # Similar for for_sale and redirect

        # Calculate metrics
        total_positives = len(true_positives)
        total_negatives = len(true_negatives)

        precision = tp_correct / total_positives if total_positives > 0 else 0.0
        recall = tp_correct / total_positives if total_positives > 0 else 0.0

        self.results["performance_metrics"][name] = {
            "precision": precision,
            "recall": recall,
            "f1_score": 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        }

    def _generate_suggestions(self):
        """Generate improvement suggestions based on failures"""
        suggestions = []

        # Analyze failure patterns
        for failure in self.results["failures"]:
            ground_truth = failure.get("ground_truth")
            domain = failure.get("domain")

            if ground_truth == "FOR_SALE" and not failure["validation"].get("is_for_sale"):
                suggestions.append({
                    "type": "for_sale_detection",
                    "domain": domain,
                    "suggestion": f"Add detection patterns from {domain} - missed for-sale indicators"
                })

            if ground_truth == "PARKING" and not failure["validation"].get("is_parking"):
                suggestions.append({
                    "type": "parking_detection",
                    "domain": domain,
                    "suggestion": f"Add parking patterns from {domain}"
                })

            if ground_truth == "REDIRECT" and not failure["validation"].get("is_redirect"):
                suggestions.append({
                    "type": "redirect_detection",
                    "domain": domain,
                    "suggestion": f"Check redirect detection for {domain}"
                })

            # Score range issues
            expected_range = failure.get("expected_score_range", [0, 100])
            actual_score = failure.get("score", 0)

            if actual_score < expected_range[0]:
                suggestions.append({
                    "type": "scoring_adjustment",
                    "domain": domain,
                    "suggestion": f"Score too low ({actual_score}) - adjust weights for {ground_truth}"
                })

            if actual_score > expected_range[1]:
                suggestions.append({
                    "type": "scoring_adjustment",
                    "domain": domain,
                    "suggestion": f"Score too high ({actual_score}) - increase penalties for {ground_truth}"
                })

        self.results["suggested_improvements"] = suggestions

    def _print_results(self):
        """Print comprehensive test results"""
        print("\n" + "="*100)
        print(" 📊 TEST RESULTS")
        print("="*100 + "\n")

        # Overall accuracy
        total = self.results["total_examples"]
        correct = self.results["correct_predictions"]
        accuracy = self.results["accuracy"] * 100

        print(f"Total Examples: {total}")
        print(f"Correct Predictions: {correct}")
        print(f"Failed Predictions: {total - correct}")
        print(f"Overall Accuracy: {accuracy:.1f}%")

        # Target accuracy
        target = self.training_data["performance_benchmarks"]["target_accuracy"]["overall_classification"] * 100
        status = "✅ PASSING" if accuracy >= target else "❌ BELOW TARGET"
        print(f"Target Accuracy: {target:.1f}% | Status: {status}")

        # Failures
        if self.results["failures"]:
            print("\n" + "="*100)
            print(" ❌ FAILED PREDICTIONS")
            print("="*100 + "\n")

            for i, failure in enumerate(self.results["failures"], 1):
                print(f"{i}. {failure['domain']}")
                print(f"   Ground Truth: {failure['ground_truth']}")
                if 'prediction' in failure:
                    print(f"   Predicted: {failure['prediction']}")
                    print(f"   Score: {failure['score']}/100 (expected: {failure['expected_score_range']})")
                    print(f"   Validation: parking={failure['validation']['is_parking']}, "
                          f"for_sale={failure['validation']['is_for_sale']}, "
                          f"redirect={failure['validation']['is_redirect']}")
                if 'error' in failure:
                    print(f"   Error: {failure['error']}")
                print(f"   Notes: {failure.get('notes', 'N/A')}")
                print()

        # Suggestions
        if self.results["suggested_improvements"]:
            print("="*100)
            print(" 💡 IMPROVEMENT SUGGESTIONS")
            print("="*100 + "\n")

            for i, suggestion in enumerate(self.results["suggested_improvements"], 1):
                print(f"{i}. [{suggestion['type']}] {suggestion['suggestion']}")

        print("\n" + "="*100)
        print(" ✅ TRAINING COMPLETE")
        print("="*100 + "\n")

    def _save_results(self):
        """Save results to file"""
        filename = f"training_results_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"

        with open(filename, 'w') as f:
            json.dump(self.results, f, indent=2, default=str)

        print(f"Results saved to: {filename}\n")


async def main():
    """Run agent training"""
    trainer = AgentTrainer()
    results = await trainer.run_training_tests()

    # Return exit code based on accuracy
    target_accuracy = trainer.training_data["performance_benchmarks"]["target_accuracy"]["overall_classification"]

    if results["accuracy"] >= target_accuracy:
        print("🎉 AGENTS MEET ACCURACY TARGETS!")
        return 0
    else:
        print(f"⚠️  AGENTS BELOW TARGET - Accuracy: {results['accuracy']*100:.1f}% vs Target: {target_accuracy*100:.1f}%")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
