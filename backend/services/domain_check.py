"""Domain validation service - HTTP/DNS/SSL checks and content extraction"""
import httpx
import dns.resolver
import asyncio
from typing import Dict, Optional
from datetime import datetime, timezone
from utils.logger import logger
from config.settings import settings


class DomainCheckService:
    """Service for comprehensive domain validation"""

    def __init__(self):
        self.timeout = settings.domain_timeout
        self.user_agent = "Mozilla/5.0 (AI Domain Discovery Bot)"

    async def check_domain(self, domain: str) -> Dict:
        """
        Perform comprehensive domain check

        Returns dict with:
        - is_live: bool
        - http_status_code: int | None
        - has_ssl: bool
        - title: str | None
        - meta_description: str | None
        - content_sample: str | None
        - dns_resolved: bool
        - is_redirect: bool (NEW)
        - final_url: str | None (NEW)
        - final_domain: str | None (NEW)
        """
        logger.info("domain_check_started", domain=domain)

        result = {
            "domain": domain,
            "is_live": False,
            "http_status_code": None,
            "has_ssl": False,
            "title": None,
            "meta_description": None,
            "content_sample": None,
            "dns_resolved": False,
            "is_redirect": False,
            "final_url": None,
            "final_domain": None,
            "checked_at": datetime.utcnow(),  # Use naive datetime for DB
        }

        # 1. DNS Resolution Check
        dns_resolved = await self._check_dns(domain)
        result["dns_resolved"] = dns_resolved

        if not dns_resolved:
            logger.info("domain_dns_failed", domain=domain)
            return result

        # 2. HTTP/HTTPS Check
        http_result = await self._check_http(domain)
        result.update(http_result)

        logger.info(
            "domain_check_completed",
            domain=domain,
            is_live=result["is_live"],
            status_code=result["http_status_code"]
        )

        return result

    async def _check_dns(self, domain: str) -> bool:
        """Check if domain resolves via DNS"""
        max_retries = 2
        for attempt in range(max_retries):
            try:
                # Wrap blocking DNS call in asyncio.to_thread to avoid blocking event loop
                answers = await asyncio.to_thread(dns.resolver.resolve, domain, 'A')
                return len(answers) > 0
            except dns.resolver.NXDOMAIN:
                # Domain doesn't exist - no retry needed
                return False
            except dns.resolver.NoAnswer:
                # No A record - no retry needed
                return False
            except dns.resolver.Timeout:
                # Timeout - retry
                if attempt < max_retries - 1:
                    await asyncio.sleep(0.5)
                    continue
                return False
            except Exception:
                # Other errors - retry once
                if attempt < max_retries - 1:
                    await asyncio.sleep(0.3)
                    continue
                return False
        return False

    async def _check_http(self, domain: str) -> Dict:
        """Check HTTP/HTTPS connectivity and extract content"""
        result = {
            "is_live": False,
            "http_status_code": None,
            "has_ssl": False,
            "title": None,
            "meta_description": None,
            "content_sample": None,
        }

        # Try HTTPS first (preferred)
        https_result = await self._try_url(f"https://{domain}")
        if https_result["success"]:
            result.update(https_result)
            result["has_ssl"] = True
            result["is_live"] = True
            return result

        # Try HTTP as fallback
        http_result = await self._try_url(f"http://{domain}")
        if http_result["success"]:
            result.update(http_result)
            result["is_live"] = True
            return result

        return result

    async def _try_url(self, url: str) -> Dict:
        """Try to fetch a URL and extract content"""
        result = {"success": False}

        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=True,
                headers={"User-Agent": self.user_agent}
            ) as client:
                response = await client.get(url)

                result["success"] = True
                result["http_status_code"] = response.status_code

                # CRITICAL: Check for redirects by comparing URLs
                requested_domain = self._extract_domain_from_url(url)
                final_url = str(response.url)
                final_domain = self._extract_domain_from_url(final_url)

                # Detect redirect if domains don't match
                if requested_domain != final_domain:
                    result["is_redirect"] = True
                    result["final_url"] = final_url
                    result["final_domain"] = final_domain
                    logger.warning(
                        "redirect_detected",
                        requested_domain=requested_domain,
                        final_domain=final_domain,
                        final_url=final_url
                    )
                else:
                    result["is_redirect"] = False
                    result["final_url"] = final_url
                    result["final_domain"] = final_domain

                # Only process successful responses
                if 200 <= response.status_code < 300:
                    # Extract title
                    content = response.text
                    title = self._extract_title(content)
                    result["title"] = title

                    # Extract meta description
                    meta_desc = self._extract_meta_description(content)
                    result["meta_description"] = meta_desc

                    # Extract content sample (first 200 chars of visible text)
                    content_sample = self._extract_content_sample(content)
                    result["content_sample"] = content_sample

        except httpx.TimeoutException:
            logger.debug("http_timeout", url=url)
        except Exception as e:
            logger.debug("http_error", url=url, error=str(e))

        return result

    def _extract_title(self, html: str) -> Optional[str]:
        """Extract title from HTML"""
        import re
        match = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
        if match:
            title = match.group(1).strip()
            return title[:500] if title else None
        return None

    def _extract_meta_description(self, html: str) -> Optional[str]:
        """Extract meta description from HTML"""
        import re
        match = re.search(
            r'<meta\s+name=["\']description["\']\s+content=["\'](.*?)["\']',
            html,
            re.IGNORECASE | re.DOTALL
        )
        if match:
            return match.group(1).strip()
        return None

    def _extract_content_sample(self, html: str) -> Optional[str]:
        """Extract first 200 chars of visible text"""
        import re
        # Remove script and style tags
        text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', ' ', text)
        # Clean whitespace
        text = ' '.join(text.split())
        # Return first 200 chars
        return text[:200] if text else None

    def _extract_domain_from_url(self, url: str) -> str:
        """
        Extract clean domain from URL

        Examples:
        - https://example.com/path -> example.com
        - http://www.example.com -> www.example.com
        - https://example.com:443 -> example.com
        """
        from urllib.parse import urlparse

        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path.split('/')[0]

        # Remove port if present
        if ':' in domain:
            domain = domain.split(':')[0]

        return domain.lower()
