"""
Domain Registrar Feeds Service - Find newly registered .ai domains
Sources: RDAP, WHOIS queries, SecurityTrails, public feeds
"""
import httpx
import asyncio
import re
from datetime import datetime, timedelta
from typing import List, Set, Dict, Any, Optional
from utils.logger import logger
from utils.helpers import clean_domain, is_valid_domain


class RegistrarFeedsService:
    """
    Query domain registrar data sources to find newly registered .ai domains.

    Sources (all FREE or have free tiers):
    1. RDAP queries - Registration Data Access Protocol (free)
    2. DNSdumpster - free
    3. SecurityTrails - free tier (50 queries/month)
    4. WhoisXML API - free tier (500 queries/month)
    5. Public drop lists / expiry feeds
    """

    def __init__(self):
        self.timeout = 20.0
        self.domain_pattern = re.compile(r'([a-z0-9-]+\.ai)(?:[^a-z0-9-]|$)', re.IGNORECASE)

        # High-value prefixes to check for new .ai registrations
        # These are patterns likely to be used by startups
        self.prefixes_to_check = [
            # Tech/AI patterns
            "get", "try", "use", "my", "the", "go", "hey", "hi",
            "chat", "talk", "ask", "help", "code", "dev", "build",
            "ai", "ml", "gpt", "llm", "bot", "auto", "smart",
            "data", "cloud", "api", "app", "web", "net",
            "flow", "hub", "lab", "studio", "works", "hq",

            # Business patterns
            "sales", "lead", "crm", "hr", "pay", "fin", "legal",
            "meet", "team", "work", "task", "doc", "note",

            # Creative patterns
            "art", "design", "write", "create", "make", "gen",
            "image", "video", "voice", "music", "photo",

            # Marketing patterns
            "brand", "copy", "social", "ad", "email", "seo",

            # Productivity
            "quick", "fast", "easy", "simple", "one", "all",
            "super", "mega", "ultra", "pro", "plus", "max",
        ]

        # Public data sources for newly registered domains
        self.public_sources = {
            "domainwatch_feed": {
                "url": "https://domainwatch.com/feeds/ai-domains.rss",
                "type": "rss",
                "enabled": False  # Most are paid
            },
            "domain_name_news": {
                "url": "https://www.domainnamewire.com/feed/",
                "type": "rss",
                "enabled": True  # Free RSS about domain news
            },
            "namepros_new": {
                "url": "https://www.namepros.com/forums/domain-name-news.14/index.rss",
                "type": "rss",
                "enabled": True  # Free RSS about domain registrations
            }
        }

    async def discover_from_registrar_feeds(self) -> List[str]:
        """
        Main method: Query multiple registrar data sources for .ai domains.

        Returns:
            List of discovered .ai domains
        """
        logger.info("registrar_feeds_started")
        all_domains: Set[str] = set()

        # 1. Query RDAP for high-value prefixes
        rdap_domains = await self._query_rdap_prefixes()
        all_domains.update(rdap_domains)

        # 2. Scrape public RSS feeds for domain news
        feed_domains = await self._scrape_public_feeds()
        all_domains.update(feed_domains)

        # 3. Check domain auction sites
        auction_domains = await self._check_auction_sites()
        all_domains.update(auction_domains)

        logger.info("registrar_feeds_completed", total_domains=len(all_domains))
        return list(all_domains)

    async def _query_rdap_prefixes(self) -> Set[str]:
        """
        Query RDAP servers for specific .ai domain prefixes.
        RDAP is the modern replacement for WHOIS.
        """
        domains = set()

        # .ai RDAP server (Anguilla registry)
        rdap_server = "https://rdap.nic.ai/domain/"

        # Query a sample of high-value prefixes
        # Limit to avoid rate limiting
        prefixes_to_query = self.prefixes_to_check[:20]

        for prefix in prefixes_to_query:
            domain = f"{prefix}.ai"
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(f"{rdap_server}{domain}")

                    if response.status_code == 200:
                        # Domain exists - check registration date
                        data = response.json()
                        events = data.get("events", [])

                        for event in events:
                            if event.get("eventAction") == "registration":
                                reg_date_str = event.get("eventDate", "")
                                if reg_date_str:
                                    try:
                                        reg_date = datetime.fromisoformat(reg_date_str.replace("Z", "+00:00"))
                                        # Check if registered in last 7 days
                                        if reg_date > datetime.now().replace(tzinfo=reg_date.tzinfo) - timedelta(days=7):
                                            domains.add(domain)
                                            logger.info("rdap_new_domain_found", domain=domain, reg_date=reg_date_str)
                                    except ValueError:
                                        pass

                # Rate limit to be polite to RDAP servers
                await asyncio.sleep(0.5)

            except Exception as e:
                logger.debug("rdap_query_failed", domain=domain, error=str(e))
                continue

        return domains

    async def _scrape_public_feeds(self) -> Set[str]:
        """Scrape public RSS feeds about domain news/registrations"""
        domains = set()

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        for source_name, config in self.public_sources.items():
            if not config.get("enabled", False):
                continue

            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.get(config["url"], headers=headers)

                    if response.status_code == 200:
                        # Extract .ai domains from the feed content
                        matches = self.domain_pattern.findall(response.text)
                        for match in matches:
                            domain = clean_domain(match)
                            if is_valid_domain(domain) and len(domain) > 4:
                                domains.add(domain)

                        logger.info("feed_scraped", source=source_name, domains_found=len(matches))

            except Exception as e:
                logger.warning("feed_scrape_failed", source=source_name, error=str(e))
                continue

        return domains

    async def _check_auction_sites(self) -> Set[str]:
        """Check domain auction/listing feeds for .ai domains

        Note: Major auction sites (GoDaddy, Sedo, Afternic) block bots with 403.
        Using alternative sources that work:
        - NameJet RSS feeds (free, no bot protection)
        - Park.io expired domains API
        - Domainnamewire domain sales reports
        """
        domains = set()

        # Alternative sources that don't block bots
        auction_sources = [
            # NameJet - their blog/feed mentions domain sales
            {
                "url": "https://www.namejet.com/Pages/Auctions/BackorderSnap.aspx",
                "type": "html",
                "enabled": False,  # Requires session, disabled
            },
            # Domain sales news feeds (mention domains being sold)
            {
                "url": "https://domaingang.com/feed/",
                "type": "rss",
                "enabled": True,
            },
            # OnlineDomain news - reports .ai domain sales
            {
                "url": "https://onlinedomain.com/feed/",
                "type": "rss",
                "enabled": True,
            },
        ]

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }

        for source in auction_sources:
            if not source.get("enabled", True):
                continue

            url = source["url"]
            try:
                async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                    response = await client.get(url, headers=headers)

                    if response.status_code == 200:
                        matches = self.domain_pattern.findall(response.text)
                        for match in matches:
                            domain = clean_domain(match)
                            if is_valid_domain(domain) and len(domain) > 4:
                                domains.add(domain)
                        logger.debug("auction_source_success", url=url[:50], domains_found=len(matches))
                    else:
                        logger.debug("auction_source_http_error", url=url[:50], status=response.status_code)

            except Exception as e:
                logger.debug("auction_check_failed", url=url[:50], error=str(e))
                continue

        return domains

    async def check_whoisxml_newly_registered(self, api_key: Optional[str] = None) -> Set[str]:
        """
        Query WhoisXML API for newly registered .ai domains.
        FREE tier: 500 queries/month

        Requires: WHOISXML_API_KEY environment variable
        """
        import os
        api_key = api_key or os.getenv("WHOISXML_API_KEY")

        if not api_key:
            logger.debug("whoisxml_api_disabled", reason="No API key")
            return set()

        domains = set()

        # WhoisXML Newly Registered Domains API
        base_url = "https://newly-registered-domains.whoisxmlapi.com/api/v1"

        # Query for .ai domains registered in the last 24 hours
        params = {
            "apiKey": api_key,
            "tld": "ai",
            "sinceDate": (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d"),
            "outputFormat": "JSON"
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(base_url, params=params)

                if response.status_code == 200:
                    data = response.json()
                    domain_list = data.get("domainsList", [])

                    for domain_info in domain_list:
                        domain_name = domain_info.get("domainName", "")
                        if domain_name and is_valid_domain(domain_name):
                            domains.add(domain_name.lower())

                    logger.info("whoisxml_query_success", domains_found=len(domains))
                else:
                    logger.warning("whoisxml_query_failed", status=response.status_code)

        except Exception as e:
            logger.error("whoisxml_api_error", error=str(e))

        return domains

    async def check_security_trails(self, api_key: Optional[str] = None) -> Set[str]:
        """
        Query SecurityTrails API for .ai domain data.
        FREE tier: 50 queries/month

        Requires: SECURITYTRAILS_API_KEY environment variable
        """
        import os
        api_key = api_key or os.getenv("SECURITYTRAILS_API_KEY")

        if not api_key:
            logger.debug("securitytrails_api_disabled", reason="No API key")
            return set()

        domains = set()

        # SecurityTrails domain search API
        base_url = "https://api.securitytrails.com/v1/domains/list"

        headers = {
            "APIKEY": api_key,
            "Content-Type": "application/json"
        }

        # Search for recently seen .ai domains
        payload = {
            "filter": {
                "apex_domain": "ai"
            }
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(base_url, headers=headers, json=payload)

                if response.status_code == 200:
                    data = response.json()
                    records = data.get("records", [])

                    for record in records:
                        domain_name = record.get("hostname", "")
                        if domain_name and domain_name.endswith(".ai"):
                            domains.add(domain_name.lower())

                    logger.info("securitytrails_query_success", domains_found=len(domains))
                else:
                    logger.warning("securitytrails_query_failed", status=response.status_code)

        except Exception as e:
            logger.error("securitytrails_api_error", error=str(e))

        return domains


# Singleton instance
registrar_feeds = RegistrarFeedsService()
