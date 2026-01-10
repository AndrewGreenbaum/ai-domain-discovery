"""
WHOIS Service - Get domain registration information
Critical for filtering out old domains masquerading as new
"""
import re
import whois
import asyncio
from datetime import datetime
from typing import Optional, Dict
from utils.logger import logger


class WHOISService:
    """Service for querying WHOIS data to determine domain age"""

    # Regex patterns for parsing raw WHOIS text
    CREATION_DATE_PATTERNS = [
        r'Creation Date:\s*(\d{4}-\d{2}-\d{2})',  # ISO format
        r'Created Date:\s*(\d{4}-\d{2}-\d{2})',
        r'Created:\s*(\d{4}-\d{2}-\d{2})',
        r'Registration Date:\s*(\d{4}-\d{2}-\d{2})',
        r'created:\s*(\d{4}-\d{2}-\d{2})',
    ]

    REGISTRAR_PATTERNS = [
        r'Registrar:\s*(.+?)(?:\n|$)',
        r'Registrar Name:\s*(.+?)(?:\n|$)',
    ]

    def __init__(self):
        pass

    def _parse_raw_text(self, text: str) -> tuple:
        """
        Parse creation date and registrar from raw WHOIS text
        Fallback for when python-whois doesn't parse correctly
        """
        created_date = None
        registrar = None

        if not text:
            return None, None

        # Try to find creation date
        for pattern in self.CREATION_DATE_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    date_str = match.group(1)
                    created_date = datetime.strptime(date_str, '%Y-%m-%d')
                    break
                except ValueError:
                    continue

        # Try to find registrar
        for pattern in self.REGISTRAR_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                registrar = match.group(1).strip()
                break

        return created_date, registrar

    async def get_domain_age(self, domain: str) -> Optional[Dict]:
        """
        Get domain registration age from WHOIS

        Returns:
            {
                "created_date": "2017-05-15",
                "age_days": 2750,
                "registrar": "GoDaddy",
                "is_new": False  # True if < 90 days old
            }
        """
        try:
            # Query WHOIS - wrap blocking call in asyncio.to_thread to avoid blocking event loop
            w = await asyncio.to_thread(whois.whois, domain)

            # Extract creation date
            created_date = w.creation_date
            if isinstance(created_date, list):
                created_date = created_date[0]  # Take first if multiple

            # Get registrar
            registrar = w.registrar if hasattr(w, 'registrar') else None

            # If python-whois didn't parse correctly, try raw text parsing
            if not created_date and hasattr(w, 'text') and w.text:
                parsed_date, parsed_registrar = self._parse_raw_text(w.text)
                if parsed_date:
                    created_date = parsed_date
                    logger.debug("whois_fallback_parse_success", domain=domain)
                if not registrar and parsed_registrar:
                    registrar = parsed_registrar

            if not created_date:
                logger.warning("whois_no_creation_date", domain=domain)
                return None

            # Make both datetimes timezone-naive for comparison
            if hasattr(created_date, 'tzinfo') and created_date.tzinfo is not None:
                created_date = created_date.replace(tzinfo=None)

            # Calculate age using UTC for consistency
            age_days = (datetime.utcnow() - created_date).days

            result = {
                "created_date": created_date.strftime("%Y-%m-%d") if created_date else None,
                "age_days": age_days,
                "registrar": registrar,
                "is_new": age_days <= 90  # NEW domains are <= 90 days old
            }

            logger.info(
                "whois_lookup_success",
                domain=domain,
                age_days=age_days,
                is_new=result["is_new"]
            )

            return result

        except Exception as e:
            logger.warning("whois_lookup_failed", domain=domain, error=str(e))
            return None

    def is_domain_too_old(self, age_days: Optional[int], max_age_days: int = 90) -> bool:
        """
        Check if domain is too old to be considered a "new discovery"

        Args:
            age_days: Domain age in days (from WHOIS)
            max_age_days: Maximum age for NEW domains (default 90)

        Returns:
            True if domain is older than threshold
        """
        if age_days is None:
            # If we can't determine age, be conservative and allow it
            # (Better to have false positives than miss real new startups)
            return False

        return age_days > max_age_days
