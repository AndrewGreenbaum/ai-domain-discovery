#!/usr/bin/env python3
"""Comprehensive system status check"""
import sqlite3
from datetime import datetime, timezone, timedelta

conn = sqlite3.connect('aidomains.db')
cursor = conn.cursor()

print("="*70)
print("AI DOMAIN DISCOVERY SYSTEM - STATUS REPORT")
print("="*70)
print(f"Generated: {datetime.now(timezone.utc).isoformat()}")
print()

# 1. Scheduler status (check if planner is configured)
print("1️⃣  SCHEDULER STATUS")
print("-" * 70)
try:
    with open('.env', 'r') as f:
        env_content = f.read()
        if 'DISCOVERY_SCHEDULE' in env_content:
            schedule = [line.split('=')[1] for line in env_content.split('\n') if 'DISCOVERY_SCHEDULE' in line][0]
            print(f"   ✅ Scheduler configured: {schedule}")
            print(f"   📅 Schedule: 9 AM, 2 PM, 8 PM UTC (3x daily)")
        else:
            print(f"   ⚠️  No schedule configured in .env")
except Exception as e:
    print(f"   ⚠️  Could not read .env file: {e}")
print()

# 2. Domains discovered in last 24h
print("2️⃣  DOMAINS DISCOVERED (Last 24 Hours)")
print("-" * 70)
yesterday = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
cursor.execute(f"""
    SELECT COUNT(*) FROM domains
    WHERE discovered_at >= '{yesterday}'
""")
count_24h = cursor.fetchone()[0]
print(f"   📊 Domains found: {count_24h}")

# Total domains
cursor.execute("SELECT COUNT(*) FROM domains")
total = cursor.fetchone()[0]
print(f"   📊 Total domains in DB: {total}")
print()

# 3. Validation percentage
print("3️⃣  VALIDATION STATUS")
print("-" * 70)
cursor.execute("SELECT COUNT(*) FROM domains WHERE last_checked IS NOT NULL")
validated = cursor.fetchone()[0]
validation_pct = (validated / total * 100) if total > 0 else 0
print(f"   ✅ Validated: {validated}/{total} ({validation_pct:.1f}%)")

cursor.execute("SELECT COUNT(*) FROM domains WHERE status = 'pending'")
pending = cursor.fetchone()[0]
print(f"   ⏳ Pending: {pending}")

cursor.execute("SELECT COUNT(*) FROM domains WHERE is_live = 1")
live = cursor.fetchone()[0]
print(f"   🟢 Live: {live}")

cursor.execute("SELECT COUNT(*) FROM domains WHERE is_parking = 1")
parking = cursor.fetchone()[0]
print(f"   🅿️  Parking: {parking}")
print()

# 4. Quality score percentage
print("4️⃣  QUALITY SCORING STATUS")
print("-" * 70)
cursor.execute("SELECT COUNT(*) FROM domains WHERE quality_score IS NOT NULL")
scored = cursor.fetchone()[0]
scoring_pct = (scored / total * 100) if total > 0 else 0
print(f"   ✅ Scored: {scored}/{total} ({scoring_pct:.1f}%)")

if scored > 0:
    cursor.execute("SELECT AVG(quality_score) FROM domains WHERE quality_score IS NOT NULL")
    avg_score = cursor.fetchone()[0]
    print(f"   📊 Average score: {avg_score:.1f}")

    cursor.execute("SELECT COUNT(*) FROM domains WHERE quality_score >= 80")
    high_quality = cursor.fetchone()[0]
    print(f"   ⭐ High quality (>80): {high_quality}")

    cursor.execute("SELECT COUNT(*) FROM domains WHERE quality_score >= 60 AND quality_score < 80")
    medium_quality = cursor.fetchone()[0]
    print(f"   📈 Medium quality (60-79): {medium_quality}")
print()

# 5. Last 5 discovery runs
print("5️⃣  RECENT DISCOVERY RUNS")
print("-" * 70)
cursor.execute("""
    SELECT id, run_at, status, domains_found, domains_new, domains_updated, duration_seconds
    FROM discovery_runs
    ORDER BY run_at DESC
    LIMIT 5
""")
runs = cursor.fetchall()
if runs:
    for run in runs:
        run_id, run_at, status, found, new, updated, duration = run
        print(f"   Run #{run_id} - {run_at}")
        print(f"      Status: {status}")
        print(f"      Found: {found}, New: {new}, Updated: {updated}")
        print(f"      Duration: {duration:.2f}s")
        print()
else:
    print("   No discovery runs found")
print()

# 6. Error detection
print("6️⃣  ERROR ANALYSIS")
print("-" * 70)
cursor.execute("SELECT COUNT(*) FROM discovery_runs WHERE status = 'failed'")
failed_runs = cursor.fetchone()[0]
print(f"   ❌ Failed runs: {failed_runs}")

cursor.execute("SELECT COUNT(*) FROM discovery_runs WHERE errors > 0")
runs_with_errors = cursor.fetchone()[0]
print(f"   ⚠️  Runs with errors: {runs_with_errors}")

cursor.execute("SELECT COUNT(*) FROM domains WHERE validation_errors IS NOT NULL")
validation_errors = cursor.fetchone()[0]
print(f"   ⚠️  Domains with validation errors: {validation_errors}")
print()

# 7. Metrics status
print("7️⃣  METRICS SYSTEM STATUS")
print("-" * 70)
cursor.execute("SELECT COUNT(*) FROM discovery_metrics")
discovery_metrics_count = cursor.fetchone()[0]
print(f"   📊 Discovery metrics records: {discovery_metrics_count}")

cursor.execute("SELECT COUNT(*) FROM quality_metrics")
quality_metrics_count = cursor.fetchone()[0]
print(f"   📈 Quality metrics records: {quality_metrics_count}")

cursor.execute("SELECT COUNT(*) FROM system_metrics")
system_metrics_count = cursor.fetchone()[0]
print(f"   ⚙️  System metrics records: {system_metrics_count}")

cursor.execute("SELECT COUNT(*) FROM metric_alerts WHERE resolved_at IS NULL")
active_alerts = cursor.fetchone()[0]
print(f"   🚨 Active alerts: {active_alerts}")

if active_alerts > 0:
    cursor.execute("""
        SELECT severity, alert_key, message
        FROM metric_alerts
        WHERE resolved_at IS NULL
        ORDER BY timestamp DESC
        LIMIT 3
    """)
    alerts = cursor.fetchall()
    print("\n   Recent alerts:")
    for severity, key, msg in alerts:
        print(f"      [{severity}] {msg}")
print()

print("="*70)
print("STATUS CHECK COMPLETE")
print("="*70)

conn.close()
