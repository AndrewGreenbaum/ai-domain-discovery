#!/usr/bin/env python3
"""Sync SQLite scores to PostgreSQL on EC2"""
import sqlite3
import sys

def export_scores():
    """Export all domain scores from SQLite"""
    conn = sqlite3.connect('aidomains.db')
    cursor = conn.cursor()

    cursor.execute('''
        SELECT domain, quality_score, is_parking, is_redirect,
               domain_quality_score, launch_readiness_score,
               content_originality_score, professional_setup_score,
               early_signals_score, category, final_url, redirect_target
        FROM domains
    ''')

    rows = cursor.fetchall()
    conn.close()

    # Generate SQL UPDATE statements
    sql_updates = []
    for row in rows:
        domain, quality_score, is_parking, is_redirect, \
        domain_quality, launch_readiness, content_orig, prof_setup, early_signals, category, \
        final_url, redirect_target = row

        # Convert Python bool to SQL bool
        is_parking_sql = 'true' if is_parking else 'false'
        is_redirect_sql = 'true' if is_redirect else 'false'

        # Escape single quotes in category and URLs
        category_safe = (category or 'UNKNOWN').replace("'", "''")
        final_url_safe = (final_url or '').replace("'", "''") if final_url else ''
        redirect_target_safe = (redirect_target or '').replace("'", "''") if redirect_target else ''

        sql = f"""UPDATE domains SET
quality_score = {quality_score or 0},
is_parking = {is_parking_sql},
is_redirect = {is_redirect_sql},
domain_quality_score = {domain_quality or 0.0},
launch_readiness_score = {launch_readiness or 0.0},
content_originality_score = {content_orig or 0.0},
professional_setup_score = {prof_setup or 0.0},
early_signals_score = {early_signals or 0.0},
category = '{category_safe}',
final_url = {f"'{final_url_safe}'" if final_url_safe else 'NULL'},
redirect_target = {f"'{redirect_target_safe}'" if redirect_target_safe else 'NULL'}
WHERE domain = '{domain}';"""

        sql_updates.append(sql)

    return sql_updates

if __name__ == '__main__':
    updates = export_scores()

    # Write to file
    with open('/tmp/postgres_updates.sql', 'w') as f:
        f.write("-- Sync SQLite scores to PostgreSQL\n")
        f.write("BEGIN;\n\n")
        for update in updates:
            f.write(update + "\n\n")
        f.write("COMMIT;\n")

    print(f"✅ Generated {len(updates)} UPDATE statements")
    print("📝 Saved to /tmp/postgres_updates.sql")
    print("\nTo apply on EC2:")
    print("cat /tmp/postgres_updates.sql | docker exec -i docker_db_1 psql -U postgres -d aidomains")
