#!/usr/bin/env python3
"""
Quick training status check - see LLM usage and training progress
"""
from feedback_system import FeedbackSystem

fs = FeedbackSystem()
stats = fs.get_llm_statistics(days=30)

ready = stats.get('auto_training_ready', 0)
total_evals = stats.get('llm_evaluations_count', 0)
cost = stats.get('total_cost_usd', 0)
avg_conf = stats.get('avg_confidence', 0)

print("\n" + "="*60)
print("🎓 LLM TRAINING SYSTEM STATUS")
print("="*60)

print(f"\n📊 Training Progress:")
print(f"   Examples collected: {ready}/5")
print(f"   Need {max(0, 5-ready)} more before auto-retrain")

progress_bar = "█" * ready + "░" * (5 - ready)
print(f"   [{progress_bar}] {ready*20}%")

print(f"\n🤖 LLM Usage (last 30 days):")
print(f"   Total evaluations: {total_evals}")
print(f"   High-confidence (≥70%): {ready}")
if total_evals > 0:
    print(f"   Avg confidence: {avg_conf*100:.1f}%")
    print(f"   High-conf rate: {ready/total_evals*100:.1f}%")

print(f"\n💰 Cost:")
print(f"   Total (30d): ${cost:.6f}")
if total_evals > 0:
    print(f"   Avg per eval: ${cost/total_evals:.6f}")

# Verdict distribution
if 'verdict_distribution' in stats and stats['verdict_distribution']:
    print(f"\n📈 Verdict Distribution:")
    for verdict, count in stats['verdict_distribution'].items():
        print(f"   {verdict}: {count}")

# Next steps
print(f"\n🎯 Next Steps:")
if ready == 0:
    print("   • Waiting for uncertain domains (40-70 score)")
    print("   • LLM will evaluate automatically when found")
    print("   • High-confidence results saved as training data")
elif ready < 5:
    print(f"   • Collecting LLM feedback ({ready}/5)")
    print(f"   • Need {5-ready} more high-confidence examples")
    print("   • Auto-retrain will trigger at 5 examples")
else:
    print("   • Ready for retraining! Auto-retrain will trigger soon")
    print("   • Or run manually: python3 auto_retrain.py --retrain")

print("\n" + "="*60)

# Check auto-retrain status
import subprocess
result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
auto_retrain_running = any('auto_retrain.py' in line and 'grep' not in line
                           for line in result.stdout.split('\n'))

if auto_retrain_running:
    print("✅ Auto-retrain process: RUNNING")
else:
    print("⚠️  Auto-retrain process: NOT RUNNING")
    print("   Start with: nohup python3 auto_retrain.py --monitor --interval 3600 > logs/auto_retrain.log 2>&1 &")

print("="*60 + "\n")
