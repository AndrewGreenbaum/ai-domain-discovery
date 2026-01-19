#!/usr/bin/env python3
"""
AI Domain Discovery Dashboard - Static Snapshot
Shows a one-time snapshot without auto-refresh
"""
import sqlite3
import os
import sys
from datetime import datetime, timedelta
import requests

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
    GRAY = '\033[90m'
    MAGENTA = '\033[35m'
    WHITE = '\033[97m'

def get_db_connection():
    """Get database connection"""
    db_path = os.path.join(os.path.dirname(__file__), 'aidomains.db')
    return sqlite3.connect(db_path)

def get_comprehensive_stats():
    """Get comprehensive system statistics"""
    conn = get_db_connection()
    cursor = conn.cursor()
    stats = {}

    try:
        # Total domains
        cursor.execute("SELECT COUNT(*) FROM domains")
        stats['total_domains'] = cursor.fetchone()[0]

        # Live domains
        cursor.execute("SELECT COUNT(*) FROM domains WHERE is_live = 1")
        stats['live_domains'] = cursor.fetchone()[0]

        # Real startups (live and not parking)
        cursor.execute("SELECT COUNT(*) FROM domains WHERE is_live = 1 AND is_parking = 0")
        stats['real_startups'] = cursor.fetchone()[0]

        # Parking pages
        cursor.execute("SELECT COUNT(*) FROM domains WHERE is_parking = 1")
        stats['parking'] = cursor.fetchone()[0]

        # High quality (score >= 70)
        cursor.execute("SELECT COUNT(*) FROM domains WHERE quality_score >= 70")
        stats['high_quality'] = cursor.fetchone()[0]

        # Medium quality (score 50-69)
        cursor.execute("SELECT COUNT(*) FROM domains WHERE quality_score >= 50 AND quality_score < 70")
        stats['medium_quality'] = cursor.fetchone()[0]

        # Low quality (score < 50)
        cursor.execute("SELECT COUNT(*) FROM domains WHERE quality_score < 50 AND quality_score IS NOT NULL")
        stats['low_quality'] = cursor.fetchone()[0]

        # Today's discoveries
        today = datetime.now().date()
        cursor.execute("SELECT COUNT(*) FROM domains WHERE DATE(discovered_at) = ?", (today,))
        stats['discovered_today'] = cursor.fetchone()[0]

        # Quality scores
        cursor.execute("""
            SELECT
                AVG(quality_score) as avg_quality,
                MAX(quality_score) as max_quality,
                MIN(quality_score) as min_quality
            FROM domains
            WHERE quality_score IS NOT NULL
        """)
        quality = cursor.fetchone()
        stats['avg_quality'] = quality[0] or 0
        stats['max_quality'] = quality[1] or 0
        stats['min_quality'] = quality[2] or 0

        # Redirects detected (Phase 1)
        cursor.execute("SELECT COUNT(*) FROM domains WHERE is_redirect = 1")
        stats['redirects'] = cursor.fetchone()[0] or 0

    except Exception as e:
        print(f"{Colors.RED}Error getting stats: {e}{Colors.END}")
    finally:
        conn.close()

    return stats

def get_agent_activity():
    """Get detailed agent activity metrics"""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT
                run_at,
                domains_found,
                domains_new,
                domains_updated,
                status,
                duration_seconds,
                errors,
                notes
            FROM discovery_runs
            ORDER BY run_at DESC
            LIMIT 10
        """)

        runs = []
        for row in cursor.fetchall():
            runs.append({
                'started_at': row[0],
                'domains_found': row[1] or 0,
                'domains_new': row[2] or 0,
                'domains_updated': row[3] or 0,
                'status': row[4] or 'unknown',
                'duration': row[5] or 0,
                'errors': row[6] or 0,
                'notes': row[7]
            })

        return runs

    except Exception as e:
        print(f"{Colors.RED}Error getting agent activity: {e}{Colors.END}")
        return []
    finally:
        conn.close()

def get_all_domains():
    """Get all domains with full details"""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
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
                is_redirect,
                redirect_target,
                http_status_code,
                registrar,
                ssl_issuer,
                domain_quality_score,
                launch_readiness_score,
                content_originality_score,
                professional_setup_score
            FROM domains
            ORDER BY discovered_at DESC
        """)

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
                'is_redirect': row[8],
                'redirect_target': row[9],
                'http_status_code': row[10],
                'registrar': row[11],
                'ssl_issuer': row[12],
                'domain_quality_score': row[13],
                'launch_readiness_score': row[14],
                'content_originality_score': row[15],
                'professional_setup_score': row[16]
            })

        return domains

    except Exception as e:
        print(f"{Colors.RED}Error getting domains: {e}{Colors.END}")
        return []
    finally:
        conn.close()

def get_api_health():
    """Check if backend API is running"""
    try:
        response = requests.get('http://localhost:8000/api/health', timeout=2)
        if response.status_code == 200:
            data = response.json()
            return {'status': 'healthy', 'data': data}
        else:
            return {'status': 'unhealthy', 'code': response.status_code}
    except Exception as e:
        return {'status': 'offline', 'error': str(e)}

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
        return timestamp_str[:19] if timestamp_str else "Unknown"

def get_quality_bar(score, width=20):
    """Generate ASCII bar for quality score"""
    if score is None:
        return f"{Colors.GRAY}{'─' * width} N/A{Colors.END}"

    filled = int((score / 100) * width)
    empty = width - filled

    if score >= 70:
        color = Colors.GREEN
    elif score >= 40:
        color = Colors.YELLOW
    else:
        color = Colors.RED

    bar = f"{color}{'█' * filled}{Colors.GRAY}{'░' * empty}{Colors.END}"
    return f"{bar} {score:.0f}"

def main():
    """Generate static snapshot"""
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'═'*140}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}   🤖 AI DOMAIN DISCOVERY - SNAPSHOT REPORT   {Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}   Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}   {Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'═'*140}{Colors.END}\n")

    # Get data
    stats = get_comprehensive_stats()
    runs = get_agent_activity()
    domains = get_all_domains()
    api_health = get_api_health()

    # System Overview
    print(f"{Colors.BOLD}{Colors.HEADER}📊 SYSTEM OVERVIEW{Colors.END}")
    print(f"{'─'*140}")
    print(f"{Colors.BOLD}Total Domains:{Colors.END} {Colors.CYAN}{stats['total_domains']}{Colors.END}  |  ", end="")
    print(f"{Colors.BOLD}Live:{Colors.END} {Colors.GREEN}{stats['live_domains']}{Colors.END}  |  ", end="")
    print(f"{Colors.BOLD}Real Startups:{Colors.END} {Colors.GREEN}{stats['real_startups']}{Colors.END}  |  ", end="")
    print(f"{Colors.BOLD}Parking:{Colors.END} {Colors.RED}{stats['parking']}{Colors.END}  |  ", end="")
    print(f"{Colors.BOLD}Redirects:{Colors.END} {Colors.YELLOW}{stats['redirects']}{Colors.END}")

    print(f"{Colors.BOLD}Quality Distribution:{Colors.END} ", end="")
    print(f"{Colors.GREEN}High (≥70): {stats['high_quality']}{Colors.END}  |  ", end="")
    print(f"{Colors.YELLOW}Medium (50-69): {stats['medium_quality']}{Colors.END}  |  ", end="")
    print(f"{Colors.RED}Low (<50): {stats['low_quality']}{Colors.END}  |  ", end="")
    print(f"{Colors.BOLD}Avg:{Colors.END} {Colors.CYAN}{stats['avg_quality']:.1f}/100{Colors.END}")
    print()

    # Agent Activity
    print(f"{Colors.BOLD}{Colors.HEADER}🤖 AGENT PIPELINE STATUS{Colors.END}")
    print(f"{'─'*140}")

    if api_health['status'] == 'healthy':
        print(f"{Colors.GREEN}● API Server:{Colors.END} {Colors.BOLD}RUNNING{Colors.END}  |  Service: {api_health['data'].get('service', 'unknown')}")
    else:
        print(f"{Colors.RED}● API Server:{Colors.END} {Colors.BOLD}OFFLINE{Colors.END}")
    print()

    if runs:
        print(f"{Colors.BOLD}Recent Discovery Runs:{Colors.END}")
        print(f"{Colors.GRAY}{'─'*140}{Colors.END}")

        for i, run in enumerate(runs, 1):
            status_color = Colors.GREEN if run['status'] == 'completed' else Colors.YELLOW if run['status'] == 'running' else Colors.RED

            print(f"{Colors.BOLD}Run {i}:{Colors.END} {status_color}{run['status'].upper()}{Colors.END}  |  ", end="")
            print(f"{Colors.BOLD}Found:{Colors.END} {run['domains_found']:3}  |  ", end="")
            print(f"{Colors.BOLD}New:{Colors.END} {Colors.GREEN}{run['domains_new']:3}{Colors.END}  |  ", end="")
            print(f"{Colors.BOLD}Updated:{Colors.END} {run['domains_updated']:3}  |  ", end="")
            print(f"{Colors.BOLD}Duration:{Colors.END} {run['duration']:.1f}s  |  ", end="")

            if run['errors'] > 0:
                print(f"{Colors.RED}Errors: {run['errors']}{Colors.END}  |  ", end="")

            print(f"{Colors.CYAN}{format_time_ago(run['started_at'])}{Colors.END}")

            if run['notes']:
                print(f"    {Colors.YELLOW}Note: {run['notes']}{Colors.END}")
    print()

    # All Domains
    print(f"{Colors.BOLD}{Colors.HEADER}🚀 ALL DISCOVERED DOMAINS ({len(domains)} total){Colors.END}")
    print(f"{'─'*140}\n")

    for i, domain in enumerate(domains, 1):
        # Status badges
        live_badge = f"{Colors.GREEN}●LIVE{Colors.END}" if domain['is_live'] else f"{Colors.RED}●DOWN{Colors.END}"
        parking_badge = f"{Colors.RED}[PARKING]{Colors.END}" if domain['is_parking'] else f"{Colors.GREEN}[REAL]{Colors.END}"
        redirect_badge = f"{Colors.YELLOW}[REDIRECT→{domain['redirect_target']}]{Colors.END}" if domain['is_redirect'] and domain['redirect_target'] else ""

        # Header line
        print(f"{Colors.BOLD}{i:3}. {Colors.CYAN}{domain['domain']}{Colors.END}  ", end="")
        print(f"{live_badge}  {parking_badge}  {redirect_badge}")

        # Quality bar
        score = domain['quality_score']
        print(f"     {Colors.BOLD}Quality:{Colors.END} {get_quality_bar(score, 25)}")

        # Category and status
        if domain['category']:
            cat_color = Colors.GREEN if 'LAUNCHING' in domain['category'] else Colors.YELLOW if 'COMING' in domain['category'] else Colors.CYAN
            print(f"     {Colors.BOLD}Category:{Colors.END} {cat_color}{domain['category']}{Colors.END}  |  ", end="")

        print(f"{Colors.BOLD}HTTP:{Colors.END} {domain['http_status_code'] or 'N/A'}  |  ", end="")
        print(f"{Colors.BOLD}Discovered:{Colors.END} {Colors.GRAY}{format_time_ago(domain['discovered_at'])}{Colors.END}")

        # Title
        if domain['title']:
            print(f"     {Colors.BOLD}Title:{Colors.END} {truncate(domain['title'], 110)}")

        # Description
        if domain['meta_description']:
            print(f"     {Colors.BOLD}Description:{Colors.END} {Colors.GRAY}{truncate(domain['meta_description'], 110)}{Colors.END}")

        # Registrar & SSL
        info_parts = []
        if domain['registrar']:
            info_parts.append(f"{Colors.BOLD}Registrar:{Colors.END} {domain['registrar']}")
        if domain['ssl_issuer']:
            info_parts.append(f"{Colors.BOLD}SSL:{Colors.END} {domain['ssl_issuer']}")

        if info_parts:
            print(f"     {' | '.join(info_parts)}")

        # Component scores
        scores = []
        if domain['domain_quality_score']:
            scores.append(f"Domain: {domain['domain_quality_score']:.0f}")
        if domain['launch_readiness_score']:
            scores.append(f"Launch: {domain['launch_readiness_score']:.0f}")
        if domain['content_originality_score']:
            scores.append(f"Originality: {domain['content_originality_score']:.0f}")
        if domain['professional_setup_score']:
            scores.append(f"Professional: {domain['professional_setup_score']:.0f}")

        if scores:
            print(f"     {Colors.BOLD}Component Scores:{Colors.END} {Colors.GRAY}{' | '.join(scores)}{Colors.END}")

        print()  # Blank line between domains

    print(f"{Colors.BOLD}{Colors.CYAN}{'═'*140}{Colors.END}")
    print(f"{Colors.CYAN}End of Report{Colors.END}\n")

if __name__ == "__main__":
    main()
