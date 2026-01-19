#!/usr/bin/env python3
"""Check actual database schema"""
import sqlite3

conn = sqlite3.connect("./aidomains.db")
cursor = conn.cursor()

# Get table schema
cursor.execute("PRAGMA table_info(domains)")
columns = cursor.fetchall()

print("\n" + "="*80)
print(" 📋 DATABASE SCHEMA - domains table")
print("="*80 + "\n")

for col in columns:
    print(f"  {col[1]:<30} {col[2]:<15} {'NOT NULL' if col[3] else ''}")

print("\n" + "="*80)
print(f" Total columns: {len(columns)}")
print("="*80 + "\n")

conn.close()
