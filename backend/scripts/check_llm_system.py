#!/usr/bin/env python3
"""
LLM Training System Status Check
Comprehensive diagnostic of all LLM components
"""
import os
import sys
from pathlib import Path

print("\n" + "="*80)
print("🔍 LLM TRAINING SYSTEM STATUS CHECK")
print("="*80)

# Check 1: Core files exist
print("\n1️⃣  Checking core files...")
files_to_check = [
    "services/llm_evaluator.py",
    "agents/hybrid_scorer.py",
    "feedback_system.py",
    "auto_retrain.py",
    "llm_config.py"
]

all_exist = True
for file in files_to_check:
    path = Path(file)
    if path.exists():
        print(f"   ✅ {file}")
    else:
        print(f"   ❌ {file} NOT FOUND")
        all_exist = False

# Check 2: API Key configured
print("\n2️⃣  Checking API key configuration...")
api_key = os.getenv("ANTHROPIC_API_KEY")
if api_key:
    print(f"   ✅ ANTHROPIC_API_KEY set ({api_key[:20]}...)")
else:
    print("   ❌ ANTHROPIC_API_KEY not set")
    # Try loading from .env
    from dotenv import load_dotenv
    load_dotenv()
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if api_key:
        print(f"   ✅ Found in .env ({api_key[:20]}...)")
    else:
        print("   ❌ Not found in .env either")

# Check 3: Can import and initialize components
print("\n3️⃣  Testing component imports...")
try:
    from services.llm_evaluator import LLMEvaluator
    evaluator = LLMEvaluator()
    available = evaluator.is_available()
    print(f"   ✅ LLMEvaluator imported")
    print(f"   {'✅' if available else '❌'} LLM available: {available}")
    if available:
        print(f"   ✅ Model: {evaluator.model}")
except Exception as e:
    print(f"   ❌ LLMEvaluator import failed: {e}")

try:
    from agents.hybrid_scorer import HybridScorer
    scorer = HybridScorer()
    print(f"   ✅ HybridScorer imported")
    print(f"   ✅ Uncertain range: {scorer.llm_min_score}-{scorer.llm_max_score}")
except Exception as e:
    print(f"   ❌ HybridScorer import failed: {e}")

try:
    from feedback_system import FeedbackSystem
    fs = FeedbackSystem()
    print(f"   ✅ FeedbackSystem imported")
except Exception as e:
    print(f"   ❌ FeedbackSystem import failed: {e}")

# Check 4: LLM usage statistics
print("\n4️⃣  Checking LLM usage statistics...")
try:
    from feedback_system import FeedbackSystem
    fs = FeedbackSystem()
    stats = fs.get_llm_statistics(days=30)
    print(f"   📊 LLM evaluations (30d): {stats.get('llm_evaluations_count', 0)}")
    print(f"   💰 Total cost (30d): ${stats.get('total_cost_usd', 0):.6f}")
    print(f"   📈 Avg confidence: {stats.get('avg_confidence', 0)*100:.1f}%")
    print(f"   🎓 Ready for training: {stats.get('auto_training_ready', 0)} examples")
except Exception as e:
    print(f"   ⚠️  Could not get stats: {e}")

# Check 5: Auto-retrain process
print("\n5️⃣  Checking auto-retrain process...")
import subprocess
result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
auto_retrain_lines = [line for line in result.stdout.split('\n')
                     if 'auto_retrain.py' in line and 'grep' not in line]
if auto_retrain_lines:
    print(f"   ✅ Auto-retrain process running:")
    for line in auto_retrain_lines:
        parts = line.split()
        if len(parts) >= 2:
            print(f"      PID: {parts[1]}, Status: {parts[7]}")
else:
    print("   ❌ Auto-retrain process NOT running")

# Check 6: Training data directory
print("\n6️⃣  Checking training data...")
training_files = [
    "training_data.json",
    "training_data_expanded.json"
]
for file in training_files:
    path = Path(file)
    if path.exists():
        print(f"   ✅ {file} exists ({path.stat().st_size} bytes)")
    else:
        print(f"   ℹ️  {file} not found (will be created when LLM data collected)")

# Check 7: Recent log activity
print("\n7️⃣  Checking recent logs...")
log_file = Path("logs/auto_retrain.log")
if log_file.exists():
    print(f"   ✅ Auto-retrain log exists")
    # Get last 3 lines
    with open(log_file, 'r') as f:
        lines = f.readlines()
        if lines:
            print("   📝 Last log entries:")
            for line in lines[-3:]:
                print(f"      {line.strip()}")
else:
    print("   ℹ️  Auto-retrain log not found yet")

# Summary
print("\n" + "="*80)
print("📋 SYSTEM STATUS SUMMARY")
print("="*80)

components = {
    "Core files": all_exist,
    "API key": api_key is not None,
    "LLM evaluator": evaluator.is_available() if 'evaluator' in locals() else False,
    "Hybrid scorer": 'scorer' in locals(),
    "Feedback system": 'fs' in locals(),
    "Auto-retrain": len(auto_retrain_lines) > 0 if 'auto_retrain_lines' in locals() else False
}

all_working = all(components.values())

for name, status in components.items():
    icon = "✅" if status else "❌"
    print(f"{icon} {name}: {'WORKING' if status else 'NOT WORKING'}")

print("\n" + "="*80)
if all_working:
    print("✅ ALL SYSTEMS OPERATIONAL")
    print("\nYour LLM training system is fully functional and ready.")
    print("It will automatically evaluate uncertain domains (40-70 score)")
    print("and train your agents to improve over time.")
else:
    print("⚠️  SOME ISSUES DETECTED")
    print("\nSome components need attention. Review the details above.")
print("="*80 + "\n")
