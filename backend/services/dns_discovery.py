"""DNS Discovery - Find .ai domains through DNS enumeration (FREE)"""
import httpx
import asyncio
from typing import List, Set
from utils.logger import logger
from utils.helpers import is_valid_domain


class DNSDiscoveryService:
    """
    Discover .ai domains through various DNS-based methods
    100% FREE - uses public DNS APIs
    """

    def __init__(self):
        # Common subdomain prefixes to check
        self.common_subdomains = [
            'www', 'api', 'app', 'mail', 'blog', 'dev', 'staging',
            'admin', 'docs', 'dashboard', 'portal', 'beta', 'demo'
        ]

        # EXPANDED: 200+ common domain patterns for AI companies
        self.ai_patterns = [
            # Core AI terms (most likely to be registered)
            'chat', 'bot', 'ai', 'gpt', 'llm', 'agent', 'auto',
            'code', 'write', 'build', 'gen', 'ask', 'think', 'mind',
            'api', 'app', 'dev', 'hub', 'lab', 'pro', 'io', 'net',
            'data', 'learn', 'model', 'deep', 'neural', 'brain', 'smart',

            # AI products
            'copilot', 'assist', 'helper', 'wizard', 'magic', 'genius',
            'predict', 'detect', 'analyze', 'search', 'find', 'get',
            'create', 'make', 'design', 'draw', 'paint', 'art',

            # Business AI
            'sales', 'market', 'lead', 'crm', 'support', 'help',
            'email', 'mail', 'send', 'notify', 'alert', 'monitor',
            'workflow', 'task', 'job', 'schedule', 'automate', 'flow',

            # Voice/Vision AI
            'voice', 'speak', 'talk', 'call', 'meet', 'video',
            'image', 'photo', 'vision', 'see', 'watch', 'scan',
            'text', 'read', 'write', 'note', 'doc', 'word',

            # Platform names
            'cloud', 'server', 'host', 'edge', 'node', 'base',
            'platform', 'studio', 'suite', 'kit', 'tool', 'box',
            'dash', 'board', 'panel', 'console', 'portal', 'gate',

            # Prefixes/Suffixes
            'super', 'hyper', 'ultra', 'mega', 'max', 'plus',
            'fast', 'quick', 'instant', 'rapid', 'swift', 'turbo',
            'easy', 'simple', 'lite', 'mini', 'micro', 'nano',
            'open', 'free', 'next', 'new', 'fresh', 'future',

            # Common startup names
            'nova', 'spark', 'flux', 'pulse', 'wave', 'beam',
            'core', 'prime', 'alpha', 'beta', 'omega', 'delta',
            'pixel', 'bit', 'byte', 'digit', 'cyber', 'tech',

            # Industry specific
            'health', 'medical', 'care', 'doc', 'med', 'bio',
            'finance', 'trade', 'invest', 'pay', 'bank', 'money',
            'legal', 'law', 'contract', 'sign', 'verify', 'trust',
            'edu', 'learn', 'teach', 'tutor', 'study', 'course',

            # Action verbs
            'run', 'start', 'go', 'do', 'try', 'use',
            'share', 'post', 'send', 'sync', 'link', 'connect',
            'save', 'store', 'keep', 'hold', 'archive', 'backup',

            # Compound patterns (common combinations)
            'chatbot', 'aibot', 'myai', 'getai', 'tryai', 'useai',
            'aiapp', 'aiapi', 'aitool', 'aihelp', 'aiassist', 'aichat',
            'smartai', 'fastai', 'easyai', 'simpleai', 'freeai', 'openai',
            'deepai', 'autoai', 'codeai', 'dataai', 'voiceai', 'textai',
        ]

        # Rate limiting
        self.concurrent_limit = 10
        self.request_delay = 0.1

    async def discover_via_dns_enumeration(self, seed_domains: List[str]) -> List[str]:
        """
        Enumerate subdomains and related domains for given seeds

        Args:
            seed_domains: List of known .ai domains to expand from

        Returns:
            List of newly discovered domains
        """
        logger.info("dns_enumeration_started", seed_count=len(seed_domains))

        discovered: Set[str] = set()

        # For each seed domain, try to find related domains
        for seed in seed_domains[:10]:  # Limit to first 10 to avoid too many queries
            try:
                # Try common subdomains
                for subdomain in self.common_subdomains[:5]:  # Limit to 5 per domain
                    potential = f"{subdomain}.{seed}"
                    if await self._check_dns_exists(potential):
                        discovered.add(potential)

            except Exception as e:
                logger.warning("dns_enum_failed", domain=seed, error=str(e))
                continue

        logger.info("dns_enumeration_completed", discovered=len(discovered))
        return list(discovered)

    async def discover_via_dns_dumpster(self, domain: str = "ai") -> List[str]:
        """
        Use DNSDumpster (free service) to find .ai domains

        Args:
            domain: TLD to search (default: "ai")

        Returns:
            List of discovered .ai domains
        """
        # DNSDumpster requires form submission, so this is a simplified version
        # In production, you'd implement proper form handling

        logger.info("dns_dumpster_discovery_started")
        domains = []

        try:
            # Note: DNSDumpster requires CSRF token handling
            # For now, we'll skip actual implementation
            # This would require selenium or more complex scraping
            pass

        except Exception as e:
            logger.warning("dns_dumpster_failed", error=str(e))

        return domains

    async def discover_via_public_dns_apis(self) -> List[str]:
        """
        Query public DNS APIs for .ai domain records
        FREE services: DNS.coffee, Google DNS, Cloudflare DNS
        """
        logger.info("public_dns_api_discovery_started")

        domains: Set[str] = set()

        try:
            # Use SecurityTrails' free tier (limited)
            # Or DNS.coffee public records

            # For MVP, we'll use simple DNS queries
            # Full implementation would require more sophisticated querying
            pass

        except Exception as e:
            logger.warning("public_dns_api_failed", error=str(e))

        return list(domains)

    async def _check_dns_exists(self, domain: str) -> bool:
        """
        Check if a domain has DNS records (simple check)

        Args:
            domain: Domain to check

        Returns:
            True if domain appears to exist
        """
        try:
            # Use Google's DNS-over-HTTPS (free)
            dns_api = f"https://dns.google/resolve?name={domain}&type=A"

            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(dns_api)

                if response.status_code == 200:
                    data = response.json()
                    # If 'Answer' exists, domain has DNS records
                    if data.get('Answer'):
                        return True

        except Exception:
            pass

        return False

    async def discover_pattern_based(self, patterns: List[str] = None) -> List[str]:
        """
        Generate and test common AI company domain patterns using concurrent DNS lookups

        Args:
            patterns: Custom patterns to try (uses defaults if None)

        Returns:
            List of valid domains found
        """
        if patterns is None:
            patterns = self.ai_patterns

        logger.info("pattern_based_discovery_started", patterns=len(patterns))

        discovered: Set[str] = set()

        # Generate all potential domains to check
        potential_domains = set()

        for pattern in patterns:
            # Base pattern
            potential_domains.add(f"{pattern}.ai")

            # Also try with common suffixes
            for suffix in ['app', 'bot', 'hub', 'lab', 'pro', 'io']:
                potential_domains.add(f"{pattern}{suffix}.ai")

            # Also try with common prefixes
            for prefix in ['get', 'try', 'use', 'my', 'the']:
                potential_domains.add(f"{prefix}{pattern}.ai")

        logger.info("dns_checking_domains", total=len(potential_domains))

        # Use semaphore for concurrent but rate-limited DNS checks
        semaphore = asyncio.Semaphore(self.concurrent_limit)

        async def check_domain_with_limit(domain: str) -> str:
            """Check a single domain with rate limiting"""
            async with semaphore:
                try:
                    if await self._check_dns_exists(domain):
                        if is_valid_domain(domain):
                            return domain
                except Exception:
                    pass
                finally:
                    await asyncio.sleep(self.request_delay)
            return None

        # Check all domains concurrently
        tasks = [check_domain_with_limit(d) for d in potential_domains]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Collect valid results
        for result in results:
            if result and isinstance(result, str):
                discovered.add(result)

        logger.info("pattern_based_discovery_completed", discovered=len(discovered))
        return list(discovered)

    async def discover_via_hacker_news(self) -> List[str]:
        """
        Search Hacker News for recently mentioned .ai domains

        Returns:
            List of discovered .ai domains
        """
        import re
        logger.info("hackernews_discovery_started")

        domains: Set[str] = set()

        try:
            # HN Algolia API - search recent stories
            search_queries = [
                "site:.ai",
                ".ai launch",
                ".ai startup",
                "AI tool .ai",
            ]

            async with httpx.AsyncClient(timeout=15.0) as client:
                for query in search_queries:
                    try:
                        response = await client.get(
                            "https://hn.algolia.com/api/v1/search_by_date",
                            params={
                                "query": query,
                                "tags": "story",
                                "numericFilters": "created_at_i>=" + str(int((asyncio.get_event_loop().time()) - 7*24*60*60)),
                            }
                        )

                        if response.status_code == 200:
                            data = response.json()
                            for hit in data.get("hits", []):
                                # Check URL
                                url = hit.get("url", "")
                                if url:
                                    matches = re.findall(r'\b([a-zA-Z][a-zA-Z0-9-]*\.ai)\b', url.lower())
                                    domains.update(matches)

                                # Check title
                                title = hit.get("title", "")
                                if title:
                                    matches = re.findall(r'\b([a-zA-Z][a-zA-Z0-9-]*\.ai)\b', title.lower())
                                    domains.update(matches)

                        await asyncio.sleep(0.5)

                    except Exception as e:
                        logger.warning("hn_query_failed", query=query, error=str(e))
                        continue

        except Exception as e:
            logger.error("hackernews_discovery_failed", error=str(e))

        # Filter out common false positives
        filtered = {d for d in domains if len(d) > 4 and d not in ['the.ai', 'an.ai', 'is.ai', 'to.ai', 'of.ai']}

        logger.info("hackernews_discovery_completed", discovered=len(filtered))
        return list(filtered)
