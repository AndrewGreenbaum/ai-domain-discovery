"""Utility helper functions"""
from datetime import datetime, timedelta, timezone
import re
from typing import Optional


def utc_now() -> datetime:
    """Get current UTC time as timezone-aware datetime.

    Replaces deprecated datetime.utcnow() which is removed in Python 3.12+
    """
    return datetime.now(timezone.utc)


def clean_domain(domain: str) -> str:
    """Clean and normalize domain name"""
    # Remove wildcard prefix
    domain = domain.replace('*.', '')
    # Remove protocol if present
    domain = re.sub(r'https?://', '', domain)
    # Remove path if present
    domain = domain.split('/')[0]
    # Remove port if present
    domain = domain.split(':')[0]
    # Remove www prefix
    domain = domain.replace('www.', '')
    # Convert to lowercase
    domain = domain.lower().strip()
    return domain


def is_valid_domain(domain: str) -> bool:
    """Check if domain string is valid"""
    if not domain or len(domain) < 4:
        return False

    # Must end with .ai
    if not domain.endswith('.ai'):
        return False

    # Must have valid characters
    if not re.match(r'^[a-z0-9\-\.]+\.ai$', domain):
        return False

    # Must not contain invalid patterns
    invalid_patterns = ['*', '@', ' ', '\n', 'localhost']
    if any(pattern in domain for pattern in invalid_patterns):
        return False

    return True


def calculate_hours_ago(dt: datetime) -> float:
    """Calculate hours between now and given datetime"""
    if not dt:
        return 0.0
    now = utc_now()
    # Handle both timezone-aware and naive datetimes
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    delta = now - dt
    return delta.total_seconds() / 3600


def get_recheck_interval(status: str) -> timedelta:
    """Get recheck interval based on domain status"""
    intervals = {
        "not_live_yet": timedelta(hours=6),
        "coming_soon": timedelta(hours=24),
        "under_construction": timedelta(hours=48),
        "soft_launch": timedelta(hours=24),
        "pending": timedelta(hours=12),
    }
    return intervals.get(status, timedelta(hours=24))


def extract_keywords(text: str, max_keywords: int = 10) -> list[str]:
    """Extract keywords from text (simple implementation)"""
    if not text:
        return []

    # Convert to lowercase and split into words
    words = re.findall(r'\b\w+\b', text.lower())

    # Filter out common stop words
    stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
    keywords = [w for w in words if w not in stop_words and len(w) > 3]

    # Return unique keywords
    return list(set(keywords))[:max_keywords]
