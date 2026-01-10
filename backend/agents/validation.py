"""VALIDATION_AGENT - Validates domains and detects parking pages"""
from typing import Dict
from datetime import datetime, timezone, timedelta
from services.domain_check import DomainCheckService
from services.whois_service import WHOISService
from models.schemas import ValidationResult
from utils.logger import logger
from utils.helpers import get_recheck_interval
from config.indicators import (
    PARKING_INDICATORS,
    REAL_COMING_SOON_INDICATORS,
    FOR_SALE_INDICATORS
)


class ValidationAgent:
    """Agent responsible for comprehensive domain validation"""

    def __init__(self):
        self.domain_checker = DomainCheckService()
        self.whois_service = WHOISService()  # Phase 3: Domain age filtering

        # Load indicators from config
        self.parking_indicators = PARKING_INDICATORS
        self.real_coming_soon_indicators = REAL_COMING_SOON_INDICATORS
        self.for_sale_indicators = FOR_SALE_INDICATORS

    async def validate_domain(self, domain: str) -> ValidationResult:
        """
        Perform complete validation pipeline for a domain

        Returns:
            ValidationResult with all validation data
        """
        logger.info("validation_started", domain=domain)

        # Step 1: Check domain (HTTP/DNS/SSL)
        check_result = await self.domain_checker.check_domain(domain)

        # Step 2: Detect parking
        is_parking = False
        parking_confidence = 0.0

        if check_result["is_live"]:
            is_parking, parking_confidence = self._detect_parking(
                check_result.get("title", ""),
                check_result.get("meta_description", ""),
                check_result.get("content_sample", "")
            )

        # Step 3: Detect for sale
        is_for_sale = False
        if check_result["is_live"]:
            is_for_sale = self._detect_for_sale(
                check_result.get("title", ""),
                check_result.get("content_sample", "")
            )

        # Step 4: CRITICAL - Get domain age from WHOIS (Phase 3)
        whois_data = await self.whois_service.get_domain_age(domain)
        domain_created_date = None
        domain_age_days = None
        registrar = None

        if whois_data:
            domain_created_date = whois_data.get("created_date")
            domain_age_days = whois_data.get("age_days")
            registrar = whois_data.get("registrar")

        # Build result
        result = ValidationResult(
            domain=domain,
            is_live=check_result["is_live"],
            http_status_code=check_result.get("http_status_code"),
            has_ssl=check_result.get("has_ssl", False),
            title=check_result.get("title"),
            meta_description=check_result.get("meta_description"),
            content_sample=check_result.get("content_sample"),
            is_parking=is_parking,
            is_for_sale=is_for_sale,
            parking_confidence=parking_confidence,
            # NEW - Phase 1: Redirect detection
            is_redirect=check_result.get("is_redirect", False),
            final_url=check_result.get("final_url"),
            final_domain=check_result.get("final_domain"),
            # NEW - Phase 3: Domain age filtering
            domain_created_date=domain_created_date,
            domain_age_days=domain_age_days,
            registrar=registrar,
        )

        logger.info(
            "validation_completed",
            domain=domain,
            is_live=result.is_live,
            is_parking=result.is_parking,
            is_for_sale=result.is_for_sale,
            is_redirect=result.is_redirect,
            final_domain=result.final_domain
        )

        return result

    def _detect_parking(self, title: str, meta_desc: str, content: str) -> tuple[bool, float]:
        """
        Detect if domain is a parking page

        Returns:
            (is_parking, confidence_score)
        """
        if not title and not meta_desc and not content:
            return False, 0.0

        # Combine all text
        text = f"{title} {meta_desc} {content}".lower()

        # Count parking indicators
        matches = sum(1 for indicator in self.parking_indicators if indicator in text)

        # Check for real "coming soon" indicators (reduces parking confidence)
        real_indicators = sum(1 for indicator in self.real_coming_soon_indicators if indicator in text)

        # Calculate confidence
        if matches == 0:
            confidence = 0.0
        elif real_indicators > 0:
            # Has both parking and real indicators - likely legitimate
            confidence = min(0.5, matches * 0.15)
        else:
            # Only parking indicators
            confidence = min(1.0, matches * 0.25)

        is_parking = confidence >= 0.5

        return is_parking, confidence

    def _detect_for_sale(self, title: str, content: str) -> bool:
        """Detect if domain is explicitly for sale - AGGRESSIVE"""
        if not title and not content:
            return False

        text = f"{title} {content}".lower()

        # Check for sale indicators (case insensitive)
        matches = sum(1 for indicator in self.for_sale_indicators if indicator in text)

        # AGGRESSIVE: Even 1 marketplace indicator = for sale
        # Common false positives are rare with these specific terms
        if matches >= 1:
            logger.warning("for_sale_detected",
                          title=title[:100] if title else None,
                          matches=matches)
            return True

        return False

    def classify_status(self, validation: ValidationResult) -> str:
        """
        Classify domain status based on validation result

        Returns:
            Status string: 'live', 'parking', 'for_sale', 'coming_soon', 'pending'
        """
        if validation.is_for_sale:
            return "for_sale"

        if validation.is_parking:
            return "parking"

        if validation.is_live:
            # Check if it's a real "coming soon" page
            text = f"{validation.title} {validation.content_sample}".lower()
            real_indicators = sum(
                1 for indicator in self.real_coming_soon_indicators
                if indicator in text
            )

            if real_indicators >= 2:
                return "coming_soon"

            return "live"

        return "pending"

    def calculate_next_recheck(self, status: str) -> datetime:
        """Calculate when to recheck this domain"""
        interval = get_recheck_interval(status)
        return datetime.utcnow() + interval  # Use naive datetime for DB
