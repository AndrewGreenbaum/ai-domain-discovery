#!/usr/bin/env python3
import sqlite3

conn = sqlite3.connect('aidomains.db')
cursor = conn.cursor()

# Get tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [row[0] for row in cursor.fetchall()]
print("📊 Database Tables:", tables)

# Check discovery runs
cursor.execute('SELECT * FROM discovery_runs')
print("\n🔍 Discovery Runs:")
for row in cursor.fetchall():
    print(f"  Run #{row[0]}: {row[1]} - Found {row[3]} domains, Duration: {row[6]}s")

# Check domains
cursor.execute('SELECT COUNT(*) FROM domains')
domain_count = cursor.fetchone()[0]
print(f"\n📋 Total Domains: {domain_count}")

conn.close()
