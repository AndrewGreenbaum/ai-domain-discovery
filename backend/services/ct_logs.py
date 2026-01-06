"""Certificate Transparency Logs Service - Query crt.sh for new .ai domains"""
import httpx
from datetime import datetime, timedelta
from typing import List, Dict, Set
import asyncio
from utils.logger import logger
from utils.helpers import clean_domain, is_valid_domain
from config.settings import settings


class CTLogsService:
    """Service for querying Certificate Transparency logs using pattern-based discovery"""

    # High-value AI-related patterns for new startup discovery
    # Reduced list to avoid rate limiting from crt.sh
    AI_DOMAIN_PATTERNS = [
        # Most common AI startup patterns (prioritized)
        "chat", "bot", "ai", "gpt", "llm", "agent", "auto",
        "code", "write", "build", "gen", "ask",
        "api", "app", "dev", "hub", "lab", "pro",
        "data", "learn", "model", "deep", "neural",
        "voice", "image", "video", "text",
        "flow", "sync", "spark", "nova", "meta",
    ]

    def __init__(self):
        self.api_url = settings.ct_log_api
        self.max_retries = 2  # Fewer retries to avoid hammering API
        self.retry_delay = 5.0  # Longer delay between retries
        self.timeout = 25.0
        self.max_concurrent = 1  # One at a time to avoid rate limiting
        self.request_delay = 3.0  # 3 seconds between requests

    async def query_new_domains(self, hours_back: int = 48) -> List[str]:
        """
        Query CT logs for .ai domains with certificates issued in last N hours
        Uses pattern-based discovery to avoid timeout from querying all .ai domains

        Args:
            hours_back: How many hours back to search (default 48)

        Returns:
            List of discovered .ai domain names
        """
        logger.info("ct_logs_pattern_query_started",
                   hours_back=hours_back,
                   patterns=len(self.AI_DOMAIN_PATTERNS))

        cutoff_time = datetime.utcnow() - timedelta(hours=hours_back)
        all_domains: Set[str] = set()

        # Process patterns in small batches with delays to avoid rate limiting
        batch_size = self.max_concurrent
        patterns_with_results = 0

        for i in range(0, len(self.AI_DOMAIN_PATTERNS), batch_size):
            batch = self.AI_DOMAIN_PATTERNS[i:i + batch_size]

            # Query this batch
            tasks = [self._query_single_pattern(pattern, cutoff_time) for pattern in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Combine results
            for j, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.debug("pattern_query_failed",
                               pattern=batch[j],
                               error=str(result))
                    continue
                if result:
                    patterns_with_results += 1
                    all_domains.update(result)

            # Delay between batches to respect rate limits
            if i + batch_size < len(self.AI_DOMAIN_PATTERNS):
                await asyncio.sleep(self.request_delay)

        unique_domains = list(all_domains)
        logger.info(
            "ct_logs_pattern_query_completed",
            patterns_queried=len(self.AI_DOMAIN_PATTERNS),
            patterns_with_results=patterns_with_results,
            unique_domains=len(unique_domains),
            hours_back=hours_back
        )
        return unique_domains

    async def _query_single_pattern(self, pattern: str, cutoff_time: datetime) -> List[str]:
        """Query for a single pattern (e.g., 'chat' finds chat.ai, chatbot.ai, etc.)"""
        domains = []
        query = f"{pattern}.ai"

        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.get(
                        self.api_url,
                        params={"q": query, "output": "json"}
                    )

                    if response.status_code == 200:
                        data = response.json()

                        for entry in data:
                            try:
                                # Parse certificate not_before date
                                not_before_str = entry.get('not_before')
                                if not not_before_str:
                                    continue

                                cert_time = datetime.fromisoformat(
                                    not_before_str.replace('Z', '+00:00')
                                ).replace(tzinfo=None)

                                # Filter: only certificates issued in last N hours
                                if cert_time < cutoff_time:
                                    continue

                                # Extract and clean domain name
                                domain_name = entry.get('name_value', '')
                                domain = clean_domain(domain_name)

                                # Validate domain ends with .ai
                                if is_valid_domain(domain) and domain.endswith('.ai'):
                                    domains.append(domain)

                            except (ValueError, AttributeError):
                                continue

                        return list(set(domains))

                    elif response.status_code == 429:
                        # Rate limited - wait and retry
                        wait_time = self.retry_delay * (attempt + 1)
                        logger.debug("rate_limited", pattern=pattern, wait=wait_time)
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        # Other error - don't retry
                        break

            except httpx.TimeoutException:
                # Timeout - try again with backoff
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
                continue
            except Exception as e:
                logger.debug("pattern_query_error", pattern=pattern, error=str(e))
                break

        return list(set(domains))

    async def get_certificate_info(self, domain: str) -> Dict:
        """Get detailed certificate information for a specific domain"""
        params = {"q": domain, "output": "json"}

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(self.api_url, params=params)

                if response.status_code == 200:
                    data = response.json()
                    if data and len(data) > 0:
                        # Return most recent certificate
                        return data[0]

        except Exception as e:
            logger.error("get_certificate_info_failed", domain=domain, error=str(e))

        return {}
