"""Startup Directory Scraper - Find .ai domains from public startup lists (FREE)"""
import httpx
import re
import json
from typing import List, Set, Optional
from bs4 import BeautifulSoup
from utils.logger import logger
from utils.helpers import clean_domain, is_valid_domain


class StartupScraperService:
    """
    Scrape public startup directories for .ai domains
    100% FREE - no API keys needed
    EXPANDED: 15+ sources for maximum coverage
    """

    def __init__(self):
        self.domain_pattern = re.compile(r'(?:https?://)?([a-z0-9-]+\.ai)(?:[^a-z0-9-]|$)', re.IGNORECASE)
        self.timeout = 15.0

        # Public startup directories (free to access)
        # EXPANDED: More sources for better discovery
        self.sources = {
            # ===== Primary Startup Directories =====
            "ycombinator": {
                "url": "https://www.ycombinator.com/companies",
                "enabled": True,
                "category": "accelerator"
            },
            "ycombinator_ai": {
                "url": "https://www.ycombinator.com/companies?tags=Artificial%20Intelligence",
                "enabled": True,
                "category": "accelerator"
            },
            "product_hunt": {
                "url": "https://www.producthunt.com/topics/artificial-intelligence",
                "enabled": True,
                "category": "launch_platform"
            },
            "product_hunt_today": {
                "url": "https://www.producthunt.com/posts",
                "enabled": True,
                "category": "launch_platform"
            },
            "indie_hackers": {
                "url": "https://www.indiehackers.com/products",
                "enabled": True,
                "category": "community"
            },
            "betalist": {
                "url": "https://betalist.com/markets/artificial-intelligence",
                "enabled": True,
                "category": "launch_platform"
            },
            "betalist_new": {
                "url": "https://betalist.com/startups",
                "enabled": True,
                "category": "launch_platform"
            },

            # ===== Tech News (RSS/HTML) =====
            "techcrunch_ai": {
                "url": "https://techcrunch.com/category/artificial-intelligence/",
                "enabled": True,
                "category": "news"
            },
            "venturebeat_ai": {
                "url": "https://venturebeat.com/category/ai/",
                "enabled": True,
                "category": "news"
            },
            "theverge_ai": {
                "url": "https://www.theverge.com/ai-artificial-intelligence",
                "enabled": True,
                "category": "news"
            },

            # ===== Startup Discovery Platforms =====
            "crunchbase_ai": {
                "url": "https://www.crunchbase.com/hub/artificial-intelligence-startups",
                "enabled": True,
                "category": "database"
            },
            "angellist": {
                "url": "https://angel.co/artificial-intelligence",
                "enabled": True,
                "category": "database"
            },
            "f6s": {
                "url": "https://www.f6s.com/companies/artificial-intelligence/co",
                "enabled": True,
                "category": "database"
            },
            "startupbase": {
                "url": "https://startupbase.com/startups?tag=ai",
                "enabled": True,
                "category": "database"
            },

            # ===== Reddit/Community =====
            "reddit_startups": {
                "url": "https://www.reddit.com/r/startups/new/.json",
                "enabled": True,
                "category": "community",
                "json_api": True
            },
            "reddit_saas": {
                "url": "https://www.reddit.com/r/SaaS/new/.json",
                "enabled": True,
                "category": "community",
                "json_api": True
            },
            "reddit_machinelearning": {
                "url": "https://www.reddit.com/r/MachineLearning/new/.json",
                "enabled": True,
                "category": "community",
                "json_api": True
            },

            # ===== Hacker News =====
            "hackernews_show": {
                "url": "https://news.ycombinator.com/shownew",
                "enabled": True,
                "category": "community"
            },
            "hackernews_new": {
                "url": "https://news.ycombinator.com/newest",
                "enabled": True,
                "category": "community"
            },

            # ===== GitHub Trending =====
            "github_trending": {
                "url": "https://github.com/trending?since=daily",
                "enabled": True,
                "category": "code"
            },

            # ===== AI-Specific Directories =====
            "aitools_directory": {
                "url": "https://www.futuretools.io/",
                "enabled": True,
                "category": "ai_directory"
            },
            "theresanaiforthat": {
                "url": "https://theresanaiforthat.com/new/",
                "enabled": True,
                "category": "ai_directory"
            },
            "toolify_ai": {
                "url": "https://www.toolify.ai/",
                "enabled": True,
                "category": "ai_directory"
            },
        }

    async def discover_from_directories(self) -> List[str]:
        """
        Scrape startup directories for .ai domains

        Returns:
            List of discovered .ai domains
        """
        logger.info("startup_scraper_started", sources=len(self.sources))

        all_domains: Set[str] = set()

        # Scrape each enabled source
        for source_name, config in self.sources.items():
            if not config["enabled"]:
                continue

            try:
                # Check if this is a JSON API source (like Reddit)
                is_json = config.get("json_api", False)
                domains = await self._scrape_source(source_name, config["url"], is_json)
                all_domains.update(domains)
                logger.info("source_scraped", source=source_name, domains_found=len(domains))

            except Exception as e:
                logger.warning("scrape_failed", source=source_name, error=str(e))
                continue

        # Also scrape RSS feeds
        rss_domains = await self.discover_from_product_hunt_rss()
        all_domains.update(rss_domains)

        unique_domains = list(all_domains)
        logger.info("startup_scraper_completed", total_domains=len(unique_domains))

        return unique_domains

    async def _scrape_source(self, source_name: str, url: str, is_json: bool = False) -> Set[str]:
        """Scrape a single source for .ai domains"""
        domains = set()

        try:
            # More browser-like headers to avoid bot detection
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
            }

            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                response = await client.get(url, headers=headers)

                if response.status_code == 200:
                    if is_json:
                        # Handle JSON API (Reddit)
                        domains = self._extract_from_json(response.text)
                    else:
                        # Parse HTML
                        soup = BeautifulSoup(response.text, 'html.parser')

                        # Find all links
                        links = soup.find_all('a', href=True)

                        for link in links:
                            href = link['href']
                            # Extract .ai domains from URLs
                            matches = self.domain_pattern.findall(href)
                            for match in matches:
                                domain = clean_domain(match)
                                if is_valid_domain(domain):
                                    domains.add(domain)

                        # Also check text content
                        text = soup.get_text()
                        text_matches = self.domain_pattern.findall(text)
                        for match in text_matches:
                            domain = clean_domain(match)
                            if is_valid_domain(domain) and len(domain) > 4:
                                domains.add(domain)

        except Exception as e:
            logger.error("scrape_error", source=source_name, error=str(e))
            raise

        return domains

    def _extract_from_json(self, json_text: str) -> Set[str]:
        """Extract .ai domains from JSON response (Reddit API)"""
        domains = set()
        try:
            data = json.loads(json_text)
            # Reddit JSON structure: data.children[].data.url, data.children[].data.selftext
            json_str = json.dumps(data)
            matches = self.domain_pattern.findall(json_str)
            for match in matches:
                domain = clean_domain(match)
                if is_valid_domain(domain) and len(domain) > 4:
                    domains.add(domain)
        except json.JSONDecodeError:
            pass
        return domains

    async def discover_from_product_hunt_rss(self) -> List[str]:
        """
        Scrape Product Hunt's RSS feed for new .ai domain launches
        FREE - no API key needed
        """
        domains = set()

        try:
            rss_url = "https://www.producthunt.com/feed"

            headers = {
                "User-Agent": "Mozilla/5.0 (compatible; AIDomainBot/1.0)"
            }

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(rss_url, headers=headers)

                if response.status_code == 200:
                    # Parse RSS XML
                    soup = BeautifulSoup(response.text, 'xml')

                    # Find all items (products)
                    items = soup.find_all('item')

                    for item in items:
                        # Get description and link
                        description = item.find('description')
                        link = item.find('link')

                        if description:
                            text = description.get_text()
                            matches = self.domain_pattern.findall(text)
                            for match in matches:
                                domain = clean_domain(match)
                                if is_valid_domain(domain):
                                    domains.add(domain)

                        if link:
                            link_text = link.get_text()
                            matches = self.domain_pattern.findall(link_text)
                            for match in matches:
                                domain = clean_domain(match)
                                if is_valid_domain(domain):
                                    domains.add(domain)

        except Exception as e:
            logger.warning("product_hunt_rss_failed", error=str(e))

        return list(domains)
