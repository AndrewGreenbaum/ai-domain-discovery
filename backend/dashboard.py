#!/usr/bin/env python3
"""
Real-time Terminal Dashboard for AI Domain Discovery
Shows agents working and startups discovered with all enrichment data
"""
import sqlite3
import time
import os
from datetime import datetime, timedelta
from collections import defaultdict

# ANSI color codes
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'

def clear_screen():
    """Clear terminal screen"""
    os.system('clear' if os.name != 'nt' else 'cls')

def get_db_stats():
    """Get overall database statistics"""
    conn = sqlite3.connect('aidomains.db')
    cursor = conn.cursor()

    stats = {}

    # Total domains
    cursor.execute("SELECT COUNT(*) FROM domains")
    stats['total_domains'] = cursor.fetchone()[0]

    # Live domains
    cursor.execute("SELECT COUNT(*) FROM domains WHERE is_live = 1")
    stats['live_domains'] = cursor.fetchone()[0]

    # Discovered today
    today = datetime.now().date()
    cursor.execute("SELECT COUNT(*) FROM domains WHERE DATE(discovered_at) = ?", (today,))
    stats['discovered_today'] = cursor.fetchone()[0]

    # Discovered last hour
    hour_ago = datetime.now() - timedelta(hours=1)
    cursor.execute("SELECT COUNT(*) FROM domains WHERE discovered_at >= ?", (hour_ago,))
    stats['discovered_last_hour'] = cursor.fetchone()[0]

    # Quality scores
    cursor.execute("""
        SELECT
            AVG(quality_score) as avg_quality,
            MAX(quality_score) as max_quality
        FROM domains
        WHERE quality_score IS NOT NULL
    """)
    quality = cursor.fetchone()
    stats['avg_quality'] = quality[0] or 0
    stats['max_quality'] = quality[1] or 0

    # Parking vs real
    cursor.execute("SELECT COUNT(*) FROM domains WHERE is_parking = 1")
    stats['parking'] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM domains WHERE is_parking = 0 AND is_live = 1")
    stats['real_startups'] = cursor.fetchone()[0]

    conn.close()
    return stats

def get_recent_domains(limit=10):
    """Get most recently discovered domains with full info"""
    conn = sqlite3.connect('aidomains.db')
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            domain,
            discovered_at,
            is_live,
            quality_score,
            category,
            title,
            meta_description,
            is_parking,
            http_status_code,
            registrar,
            created_date,
            ssl_issuer,
            domain_quality_score,
            launch_readiness_score,
            content_originality_score
        FROM domains
        ORDER BY discovered_at DESC
        LIMIT ?
    """, (limit,))

    domains = []
    for row in cursor.fetchall():
        domains.append({
            'domain': row[0],
            'discovered_at': row[1],
            'is_live': row[2],
            'quality_score': row[3],
            'category': row[4],
            'title': row[5],
            'meta_description': row[6],
            'is_parking': row[7],
            'http_status_code': row[8],
            'registrar': row[9],
            'created_date': row[10],
            'ssl_issuer': row[11],
            'domain_quality_score': row[12],
            'launch_readiness_score': row[13],
            'content_originality_score': row[14]
        })

    conn.close()
    return domains

def get_agent_activity():
    """Get agent activity metrics from discovery runs"""
    conn = sqlite3.connect('aidomains.db')
    cursor = conn.cursor()

    # Check if discovery_runs table exists
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='discovery_runs'
    """)

    if not cursor.fetchone():
        conn.close()
        return None

    cursor.execute("""
        SELECT
            run_at,
            domains_found,
            domains_new,
            domains_updated,
            status,
            duration_seconds
        FROM discovery_runs
        ORDER BY run_at DESC
        LIMIT 5
    """)

    runs = []
    for row in cursor.fetchall():
        runs.append({
            'started_at': row[0],
            'domains_found': row[1],
            'domains_validated': row[2],
            'domains_enriched': row[3],
            'status': row[4],
            'duration': row[5]
        })

    conn.close()
    return runs

def truncate(text, length=50):
    """Truncate text to specified length"""
    if not text:
        return "N/A"
    return text[:length] + "..." if len(text) > length else text

def format_time_ago(timestamp_str):
    """Format timestamp as time ago"""
    if not timestamp_str:
        return "Unknown"

    try:
        timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        now = datetime.now(timestamp.tzinfo) if timestamp.tzinfo else datetime.now()
        delta = now - timestamp

        if delta.total_seconds() < 60:
            return f"{int(delta.total_seconds())}s ago"
        elif delta.total_seconds() < 3600:
            return f"{int(delta.total_seconds() / 60)}m ago"
        elif delta.total_seconds() < 86400:
            return f"{int(delta.total_seconds() / 3600)}h ago"
        else:
            return f"{int(delta.total_seconds() / 86400)}d ago"
    except:
        return "Unknown"

def draw_dashboard():
    """Draw the complete dashboard"""
    clear_screen()

    print(f"{Colors.BOLD}{Colors.CYAN}{'='*120}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}   AI DOMAIN DISCOVERY - LIVE DASHBOARD   {Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*120}{Colors.END}\n")

    # Get data
    stats = get_db_stats()
    domains = get_recent_domains(10)
    agent_runs = get_agent_activity()

    # System Overview
    print(f"{Colors.BOLD}{Colors.HEADER}📊 SYSTEM OVERVIEW{Colors.END}")
    print(f"{'─'*120}")
    print(f"{Colors.BOLD}Total Domains:{Colors.END} {Colors.GREEN}{stats['total_domains']}{Colors.END}  |  ", end="")
    print(f"{Colors.BOLD}Live Startups:{Colors.END} {Colors.GREEN}{stats['live_domains']}{Colors.END}  |  ", end="")
    print(f"{Colors.BOLD}Real Startups:{Colors.END} {Colors.GREEN}{stats['real_startups']}{Colors.END}  |  ", end="")
    print(f"{Colors.BOLD}Parking:{Colors.END} {Colors.RED}{stats['parking']}{Colors.END}")
    print(f"{Colors.BOLD}Today:{Colors.END} {Colors.CYAN}{stats['discovered_today']}{Colors.END}  |  ", end="")
    print(f"{Colors.BOLD}Last Hour:{Colors.END} {Colors.CYAN}{stats['discovered_last_hour']}{Colors.END}  |  ", end="")
    print(f"{Colors.BOLD}Avg Quality:{Colors.END} {Colors.YELLOW}{stats['avg_quality']:.1f}/100{Colors.END}")
    print()

    # Agent Activity
    if agent_runs:
        print(f"{Colors.BOLD}{Colors.HEADER}🤖 AGENT ACTIVITY{Colors.END}")
        print(f"{'─'*120}")
        for i, run in enumerate(agent_runs[:3]):
            status_color = Colors.GREEN if run['status'] == 'completed' else Colors.YELLOW
            print(f"{Colors.BOLD}Run {i+1}:{Colors.END} {status_color}{run['status']}{Colors.END}  |  ", end="")
            print(f"Found: {run['domains_found'] or 0}  |  ", end="")
            print(f"Validated: {run['domains_validated'] or 0}  |  ", end="")
            print(f"Enriched: {run['domains_enriched'] or 0}  |  ", end="")
            print(f"{format_time_ago(run['started_at'])}")
        print()

    # Recent Discoveries
    print(f"{Colors.BOLD}{Colors.HEADER}🚀 RECENT STARTUP DISCOVERIES{Colors.END}")
    print(f"{'─'*120}")

    for i, domain in enumerate(domains, 1):
        # Header line
        domain_color = Colors.GREEN if domain['is_live'] else Colors.RED
        quality_color = Colors.GREEN if (domain['quality_score'] or 0) >= 70 else Colors.YELLOW if (domain['quality_score'] or 0) >= 40 else Colors.RED
        parking_badge = f"{Colors.RED}[PARKING]{Colors.END}" if domain['is_parking'] else f"{Colors.GREEN}[REAL]{Colors.END}"

        print(f"\n{Colors.BOLD}{i}. {domain_color}{domain['domain']}{Colors.END}  ", end="")
        print(f"{parking_badge}  ", end="")
        print(f"Quality: {quality_color}{domain['quality_score'] or 'N/A'}{Colors.END}  |  ", end="")
        print(f"Status: {domain['http_status_code'] or 'N/A'}  |  ", end="")
        print(f"{Colors.CYAN}{format_time_ago(domain['discovered_at'])}{Colors.END}")

        # Title
        if domain['title']:
            print(f"   {Colors.BOLD}Title:{Colors.END} {truncate(domain['title'], 100)}")

        # Category
        if domain['category']:
            print(f"   {Colors.BOLD}Category:{Colors.END} {Colors.YELLOW}{domain['category']}{Colors.END}")

        # Description
        if domain['meta_description']:
            print(f"   {Colors.BOLD}Description:{Colors.END} {truncate(domain['meta_description'], 100)}")

        # Registrar & Registration
        info_parts = []
        if domain['registrar']:
            info_parts.append(f"{Colors.BOLD}Registrar:{Colors.END} {domain['registrar']}")
        if domain['created_date']:
            try:
                created = datetime.fromisoformat(domain['created_date'].replace('Z', '+00:00'))
                info_parts.append(f"{Colors.BOLD}Registered:{Colors.END} {created.strftime('%Y-%m-%d')}")
            except:
                pass
        if info_parts:
            print(f"   {' | '.join(info_parts)}")

        # SSL Info
        if domain['ssl_issuer']:
            print(f"   {Colors.BOLD}SSL:{Colors.END} {domain['ssl_issuer']}")

        # Quality Scores
        scores = []
        if domain['domain_quality_score']:
            scores.append(f"Domain: {domain['domain_quality_score']:.1f}")
        if domain['launch_readiness_score']:
            scores.append(f"Launch: {domain['launch_readiness_score']:.1f}")
        if domain['content_originality_score']:
            scores.append(f"Originality: {domain['content_originality_score']:.1f}")
        if scores:
            print(f"   {Colors.BOLD}Scores:{Colors.END} {' | '.join(scores)}")

    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*120}{Colors.END}")
    print(f"{Colors.CYAN}Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Refreshing every 5 seconds...{Colors.END}")
    print(f"{Colors.CYAN}Press Ctrl+C to exit{Colors.END}\n")

def main():
    """Main dashboard loop"""
    print(f"{Colors.BOLD}{Colors.GREEN}Starting AI Domain Discovery Dashboard...{Colors.END}\n")
    time.sleep(1)

    try:
        while True:
            draw_dashboard()
            time.sleep(5)  # Refresh every 5 seconds
    except KeyboardInterrupt:
        clear_screen()
        print(f"\n{Colors.BOLD}{Colors.GREEN}Dashboard stopped. Goodbye!{Colors.END}\n")
    except Exception as e:
        print(f"{Colors.RED}Error: {e}{Colors.END}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
