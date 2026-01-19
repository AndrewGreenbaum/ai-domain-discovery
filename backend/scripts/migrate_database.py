#!/usr/bin/env python3
"""
Add missing columns to aidomains.db for Phase 1 & 2 detection
"""
import sqlite3

DATABASE_PATH = "./aidomains.db"

def migrate_database():
    """Add new columns to existing database"""
    print("\n" + "="*80)
    print(" 🔧 DATABASE MIGRATION - Adding Phase 1 & 2 Columns")
    print("="*80 + "\n")

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # List of columns to add
    migrations = [
        # Phase 1: Redirect detection
        ("is_redirect", "INTEGER DEFAULT 0"),
        ("final_url", "TEXT"),
        ("redirect_target", "TEXT"),

        # Phase 2: Parent company & age detection
        ("parent_company", "TEXT"),
        ("company_founded_year", "INTEGER"),
        ("company_age_years", "INTEGER"),
        ("is_established_company", "INTEGER DEFAULT 0"),
        ("is_subdomain_product", "INTEGER DEFAULT 0"),
    ]

    for column_name, column_type in migrations:
        try:
            cursor.execute(f"ALTER TABLE domains ADD COLUMN {column_name} {column_type}")
            print(f"✅ Added column: {column_name}")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                print(f"⏭️  Column already exists: {column_name}")
            else:
                print(f"❌ Error adding {column_name}: {e}")

    conn.commit()
    conn.close()

    print("\n" + "="*80)
    print(" ✅ MIGRATION COMPLETE")
    print("="*80 + "\n")

if __name__ == "__main__":
    migrate_database()
