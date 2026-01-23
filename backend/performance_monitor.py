#!/usr/bin/env python3
"""
Performance Monitor - Track agent accuracy over time
Runs automated tests and alerts on performance degradation
"""
import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List
from agent_trainer import AgentTrainer
from feedback_system import FeedbackSystem


class PerformanceMonitor:
    """Monitor agent performance and detect degradation"""

    def __init__(self):
        self.trainer = AgentTrainer()
        self.feedback_system = FeedbackSystem()
        self.alert_threshold = 0.85  # Alert if accuracy drops below 85%

    async def run_automated_test(self) -> Dict:
        """Run automated test suite and return results"""
        print("\n" + "="*100)
        print(f" 🔬 AUTOMATED PERFORMANCE TEST - {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*100 + "\n")

        # Run training tests
        results = await self.trainer.run_training_tests()

        # Record results
        self.feedback_system.record_training_run(results)

        # Check for performance issues
        self._check_performance(results)

        return results

    def _check_performance(self, results: Dict):
        """Check if performance meets targets"""
        accuracy = results.get("accuracy", 0.0)
        target = self.trainer.training_data["performance_benchmarks"]["target_accuracy"]["overall_classification"]

        print("\n" + "="*100)
        print(" 🎯 PERFORMANCE ANALYSIS")
        print("="*100 + "\n")

        print(f"Current Accuracy: {accuracy*100:.1f}%")
        print(f"Target Accuracy: {target*100:.1f}%")
        print(f"Alert Threshold: {self.alert_threshold*100:.1f}%")

        if accuracy < self.alert_threshold:
            print("\n🚨 ALERT: Performance below threshold!")
            print("\nRecommended Actions:")
            print("  1. Review failed predictions")
            print("  2. Add more labeled training examples")
            print("  3. Adjust detection patterns")
            print("  4. Review recent code changes")
        elif accuracy < target:
            print("\n⚠️  WARNING: Below target but above threshold")
            print("  Consider reviewing recent changes")
        else:
            print("\n✅ Performance meets targets!")

    def get_performance_history(self, days: int = 30) -> Dict:
        """Get performance trends"""
        trends = self.feedback_system.get_performance_trends(days)

        if not trends["dates"]:
            print("No performance history available")
            return {}

        print("\n" + "="*100)
        print(f" 📈 PERFORMANCE TRENDS (Last {days} days)")
        print("="*100 + "\n")

        print(f"{'Date':<20} {'Accuracy':<15} {'Examples':<15}")
        print("-"*100)

        for i, date in enumerate(trends["dates"]):
            accuracy = trends["accuracy"][i] * 100
            examples = trends["total_examples"][i]
            print(f"{date:<20} {accuracy:<14.1f}% {examples:<15}")

        # Calculate trend
        if len(trends["accuracy"]) >= 2:
            recent_avg = sum(trends["accuracy"][-3:]) / min(3, len(trends["accuracy"]))
            older_avg = sum(trends["accuracy"][:3]) / min(3, len(trends["accuracy"]))
            change = (recent_avg - older_avg) * 100

            print("\n" + "="*100)
            if change > 0:
                print(f"📈 Trend: IMPROVING (+{change:.1f}%)")
            elif change < -0.05:
                print(f"📉 Trend: DECLINING ({change:.1f}%)")
            else:
                print("📊 Trend: STABLE")

        return trends

    async def run_continuous_monitoring(self, interval_hours: int = 24):
        """
        Run continuous monitoring loop

        Tests agents every N hours and alerts on issues
        """
        print("\n" + "="*100)
        print(f" 🔄 STARTING CONTINUOUS MONITORING (every {interval_hours}h)")
        print("="*100 + "\n")

        while True:
            try:
                # Run test
                await self.run_automated_test()

                # Wait for next run
                print(f"\nNext test in {interval_hours} hours...")
                await asyncio.sleep(interval_hours * 3600)

            except KeyboardInterrupt:
                print("\n\n⏸️  Monitoring stopped by user")
                break
            except Exception as e:
                print(f"\n❌ Error during monitoring: {e}")
                print("Retrying in 1 hour...")
                await asyncio.sleep(3600)

    def generate_weekly_report(self) -> str:
        """Generate weekly performance report"""
        report = []
        report.append("="*100)
        report.append(" 📊 WEEKLY AGENT PERFORMANCE REPORT")
        report.append("="*100)
        report.append("")

        # Get 7-day trends
        trends = self.feedback_system.get_performance_trends(7)

        if trends["dates"]:
            # Calculate metrics
            avg_accuracy = sum(trends["accuracy"]) / len(trends["accuracy"])
            min_accuracy = min(trends["accuracy"])
            max_accuracy = max(trends["accuracy"])

            report.append("SUMMARY:")
            report.append(f"  Average Accuracy: {avg_accuracy*100:.1f}%")
            report.append(f"  Best Performance: {max_accuracy*100:.1f}%")
            report.append(f"  Worst Performance: {min_accuracy*100:.1f}%")
            report.append(f"  Total Tests Run: {len(trends['dates'])}")
            report.append("")

            # Recent performance
            if len(trends["accuracy"]) > 0:
                latest_accuracy = trends["accuracy"][-1]
                status = "✅ GOOD" if latest_accuracy >= 0.90 else "⚠️  NEEDS ATTENTION"
                report.append(f"LATEST PERFORMANCE: {latest_accuracy*100:.1f}% - {status}")
                report.append("")

        # Get pending feedback
        pending = self.feedback_system.get_pending_feedback()
        if pending:
            report.append(f"PENDING FEEDBACK: {len(pending)} domains need review")
            report.append("")

        # Get suggestions
        suggestions = self.feedback_system.suggest_domains_for_labeling(5)
        if suggestions:
            report.append("SUGGESTED DOMAINS TO LABEL:")
            for s in suggestions[:5]:
                report.append(f"  - {s['domain']} (score: {s['current_score']})")
            report.append("")

        report.append("="*100)

        report_text = "\n".join(report)
        print(report_text)

        # Save to file
        filename = f"weekly_report_{datetime.utcnow().strftime('%Y%m%d')}.txt"
        with open(filename, 'w') as f:
            f.write(report_text)

        print(f"\nReport saved to: {filename}")
        return report_text


async def main():
    """Main entry point"""
    import sys

    monitor = PerformanceMonitor()

    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == "test":
            # Run single test
            await monitor.run_automated_test()

        elif command == "trends":
            # Show performance trends
            days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
            monitor.get_performance_history(days)

        elif command == "report":
            # Generate weekly report
            monitor.generate_weekly_report()

        elif command == "monitor":
            # Run continuous monitoring
            interval = int(sys.argv[2]) if len(sys.argv) > 2 else 24
            await monitor.run_continuous_monitoring(interval)

        else:
            print("Unknown command. Available commands:")
            print("  test     - Run single automated test")
            print("  trends   - Show performance trends")
            print("  report   - Generate weekly report")
            print("  monitor  - Run continuous monitoring")
    else:
        # Default: run single test
        await monitor.run_automated_test()


if __name__ == "__main__":
    asyncio.run(main())
