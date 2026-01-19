#!/usr/bin/env python3
"""Check metrics tables and data"""
import sqlite3

conn = sqlite3.connect('aidomains.db')
cursor = conn.cursor()

# Get all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = [row[0] for row in cursor.fetchall()]
print("📊 Database Tables:")
for table in tables:
    cursor.execute(f"SELECT COUNT(*) FROM {table}")
    count = cursor.fetchone()[0]
    print(f"   - {table}: {count} rows")

# Check discovery metrics
print("\n🔍 Discovery Metrics:")
cursor.execute("SELECT * FROM discovery_metrics ORDER BY timestamp DESC LIMIT 1")
row = cursor.fetchone()
if row:
    print(f"   Run ID: {row[1]}")
    print(f"   Domains discovered: {row[3]}")
    print(f"   Domains new: {row[4]}")
    print(f"   Duplicate rate: {row[6]}%")
    print(f"   Duration: {row[10]} min")

# Check quality metrics
print("\n📈 Quality Metrics:")
cursor.execute("SELECT * FROM quality_metrics ORDER BY date DESC LIMIT 1")
row = cursor.fetchone()
if row:
    print(f"   Date: {row[1]}")
    print(f"   High quality count: {row[2]}")
    print(f"   Total domains: {row[11]}")
    print(f"   Parking rejected: {row[12]}")

# Check system metrics
print("\n⚙️  System Metrics:")
cursor.execute("SELECT * FROM system_metrics ORDER BY timestamp DESC LIMIT 1")
row = cursor.fetchone()
if row:
    print(f"   Timestamp: {row[1]}")
    print(f"   Total domains: {row[9]}")
    print(f"   Active domains: {row[10]}")
    print(f"   DB size: {row[11]} MB")

# Check alerts
print("\n🚨 Metric Alerts:")
cursor.execute("SELECT * FROM metric_alerts ORDER BY timestamp DESC LIMIT 5")
rows = cursor.fetchall()
for row in rows:
    print(f"   [{row[3]}] {row[5]} - {row[4]}")

conn.close()
