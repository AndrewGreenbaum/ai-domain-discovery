"""DISCOVERY_AGENT - Finds NEW .ai domains from MULTIPLE FREE SOURCES"""
from typing import List, Set
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio

# Multiple discovery services (all free!)
from services.ct_logs import CTLogsService
from services.multi_ct_logs import MultiCTLogsService
from services.github_discovery import GitHubDiscoveryService
from services.startup_scraper import StartupScraperService
from services.dns_discovery import DNSDiscoveryService
from services.mcp_services import brave_search  # MCP integration
from services.registrar_feeds import registrar_feeds  # Domain registrar feeds

from models.domain import Domain
from utils.logger import logger

# Limit concurrent discovery tasks to prevent overwhelming external APIs
MAX_CONCURRENT_DISCOVERY_TASKS = 3


class DiscoveryAgent:
    """
    Agent responsible for discovering new .ai domains from MULTIPLE FREE SOURCES:
    - Multiple Certificate Transparency logs
    - GitHub repositories
    - Startup directories (Product Hunt, YC, etc.)
    - DNS enumeration
    """

    def __init__(self):
        # Initialize all free discovery services
        self.ct_service = CTLogsService()  # Original single source
        self.multi_ct_service = MultiCTLogsService()  # Multiple CT sources
        self.github_service = GitHubDiscoveryService()  # GitHub API (free tier)
        self.startup_scraper = StartupScraperService()  # Web scraping (free)
        self.dns_service = DNSDiscoveryService()  # DNS enumeration (free)
        self.brave_search = brave_search  # Brave Search MCP (API key required)
        self.registrar_feeds = registrar_feeds  # Domain registrar feeds (free)
        # Semaphore to limit concurrent discovery tasks (prevents API rate limits)
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_DISCOVERY_TASKS)

    async def _run_with_semaphore(self, coro):
        """Run a coroutine with semaphore to limit concurrency"""
        async with self._semaphore:
            return await coro

    async def discover_new_domains(self, hours_back: int = 24) -> List[str]:
        """
        Query ALL FREE SOURCES and find new .ai domains

        Args:
            hours_back: How many hours back to search

        Returns:
            Deduplicated list of domain names discovered from all sources
        """
        logger.info("multi_source_discovery_started", hours_back=hours_back)

        all_domains: Set[str] = set()

        try:
            # Run all discovery methods with semaphore to limit concurrency
            # This prevents overwhelming external APIs with too many simultaneous requests
            tasks = [
                self._run_with_semaphore(self._discover_from_ct_logs(hours_back)),
                self._run_with_semaphore(self._discover_from_github()),
                self._run_with_semaphore(self._discover_from_startups()),
                self._run_with_semaphore(self._discover_from_dns_patterns()),
                self._run_with_semaphore(self._discover_from_brave_search()),
                self._run_with_semaphore(self._discover_from_hacker_news()),
                self._run_with_semaphore(self._discover_from_registrar_feeds()),
            ]

            # Wait for all sources to complete (max 3 concurrent via semaphore)
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Combine results from all sources
            source_names = ["CT Logs", "GitHub", "Startups", "DNS", "Brave Search", "Hacker News", "Registrar Feeds"]
            for source_name, result in zip(source_names, results):
                if isinstance(result, Exception):
                    logger.warning("source_failed", source=source_name, error=str(result))
                    continue

                if result:
                    all_domains.update(result)
                    logger.info("source_completed", source=source_name, domains=len(result))

            # Deduplicate
            unique_domains = list(all_domains)

            logger.info(
                "multi_source_discovery_completed",
                total_domains=len(unique_domains),
                sources_used=len(source_names),
                hours_back=hours_back
            )

            return unique_domains

        except Exception as e:
            logger.error("discovery_agent_failed", error=str(e))
            return []

    async def _discover_from_ct_logs(self, hours_back: int) -> List[str]:
        """Discover from multiple CT log sources"""
        try:
            # Use multi-source CT logs service
            domains = await self.multi_ct_service.query_all_sources(hours_back)
            return domains
        except Exception as e:
            logger.error("ct_logs_discovery_failed", error=str(e))
            return []

    async def _discover_from_github(self) -> List[str]:
        """Discover from GitHub repositories"""
        try:
            # Search last 7 days of GitHub activity
            domains = await self.github_service.discover_from_github(days_back=7)
            return domains
        except Exception as e:
            logger.error("github_discovery_failed", error=str(e))
            return []

    async def _discover_from_startups(self) -> List[str]:
        """Discover from startup directories"""
        try:
            # Scrape public startup directories
            domains = await self.startup_scraper.discover_from_directories()

            # Also try Product Hunt RSS feed
            ph_domains = await self.startup_scraper.discover_from_product_hunt_rss()
            domains.extend(ph_domains)

            return list(set(domains))
        except Exception as e:
            logger.error("startup_discovery_failed", error=str(e))
            return []

    async def _discover_from_dns_patterns(self) -> List[str]:
        """Discover using DNS pattern matching"""
        try:
            # Try common AI company domain patterns
            domains = await self.dns_service.discover_pattern_based()
            return domains
        except Exception as e:
            logger.error("dns_discovery_failed", error=str(e))
            return []

    async def _discover_from_hacker_news(self) -> List[str]:
        """Discover from Hacker News mentions"""
        try:
            domains = await self.dns_service.discover_via_hacker_news()
            return domains
        except Exception as e:
            logger.error("hackernews_discovery_failed", error=str(e))
            return []

    async def _discover_from_registrar_feeds(self) -> List[str]:
        """Discover from domain registrar feeds (RDAP, auctions, etc.)"""
        try:
            domains = await self.registrar_feeds.discover_from_registrar_feeds()
            return domains
        except Exception as e:
            logger.error("registrar_feeds_discovery_failed", error=str(e))
            return []

    async def _discover_from_brave_search(self) -> List[str]:
        """Discover from Brave Search MCP - search for new AI startups and .ai domains"""
        try:
            import re
            all_domains = set()

            # OPTIMIZED: Queries that find ACTUAL .ai company websites
            # These broad AI tool queries return real .ai domain results
            search_queries = [
                # AI Tool Categories (proven to return .ai domains)
                'AI image generator',
                'AI writing assistant',
                'AI voice generator',
                'AI video maker',
                'AI coding assistant',
                'AI chatbot platform',
                'AI transcription tool',
                'AI presentation maker',
                'AI avatar generator',
                'AI music generator',

                # Specific comparisons (finds competitors with .ai domains)
                'perplexity.ai alternative',
                'character.ai similar apps',
                'copy.ai vs jasper',
                'midjourney alternative .ai',
                'chatgpt alternative .ai',

                # Product categories
                'AI text to speech',
                'AI document assistant',
                'AI meeting notes',
                'AI customer support chatbot',
                'AI sales assistant tool',

                # New/trending
                'best new AI tools 2025',
                'AI startup tools',
                'free AI tools online',
            ]

            # Domains from article sites to SKIP (they write about .ai, not actual .ai sites)
            skip_domains = {
                'forbes.com', 'techcrunch.com', 'wired.com', 'theverge.com',
                'venturebeat.com', 'zdnet.com', 'cnet.com', 'engadget.com',
                'medium.com', 'substack.com', 'linkedin.com', 'twitter.com',
                'nominus.com', 'networksolutions.com', 'godaddy.com', 'namecheap.com',
                'openprovider.com', 'get.tech', 'smartbranding.com', 'growthrocks.com'
            }

            for query in search_queries:
                try:
                    results = await self.brave_search.web_search(query, count=15, freshness="pm")  # past month

                    for result in results:
                        url = result.get("url", "").lower()

                        # Skip article/blog sites that write ABOUT .ai domains
                        if any(skip in url for skip in skip_domains):
                            continue

                        # PRIORITY: Extract .ai domain directly from URL (actual .ai websites)
                        if '.ai' in url:
                            domain_match = re.search(r'(?:https?://)?(?:www\.)?([a-zA-Z0-9][-a-zA-Z0-9]*\.ai)(?:[/?#]|$)', url)
                            if domain_match:
                                domain = domain_match.group(1)
                                if len(domain) > 4 and len(domain) < 50:
                                    all_domains.add(domain)
                                    continue  # Found direct .ai site, skip text parsing

                        # SECONDARY: Extract mentioned .ai domains from title/description
                        title = result.get("title", "")
                        description = result.get("description", "")

                        for text in [title, description]:
                            domain_matches = re.findall(r'\b([a-zA-Z][a-zA-Z0-9-]*\.ai)\b', text.lower())
                            for domain in domain_matches:
                                # Filter out common false positives and very short ones
                                false_positives = {'the.ai', 'an.ai', 'is.ai', 'to.ai', 'of.ai',
                                                   'in.ai', 'on.ai', 'for.ai', 'with.ai', 'and.ai',
                                                   'this.ai', 'that.ai', 'what.ai', 'how.ai', 'why.ai'}
                                if domain not in false_positives and len(domain) > 5 and len(domain) < 50:
                                    all_domains.add(domain)

                    # Rate limiting between queries (avoid 429 errors)
                    await asyncio.sleep(1.0)

                except Exception as e:
                    logger.warning("brave_search_query_failed", query=query[:50], error=str(e))
                    await asyncio.sleep(2.0)  # Extra delay on error
                    continue

            logger.info("brave_search_discovery_completed", domains=len(all_domains))
            return list(all_domains)

        except Exception as e:
            logger.error("brave_search_discovery_failed", error=str(e))
            return []

    async def filter_existing(self, db: AsyncSession, domains: List[str]) -> List[str]:
        """
        Filter out domains that already exist in database

        Args:
            db: Database session
            domains: List of domains to check

        Returns:
            List of truly new domains
        """
        if not domains:
            return []

        logger.info("filtering_existing_domains", total=len(domains))

        try:
            # Query database for existing domains
            stmt = select(Domain.domain).where(Domain.domain.in_(domains))
            result = await db.execute(stmt)
            existing = {row[0] for row in result.fetchall()}

            # Filter out existing
            new_domains = [d for d in domains if d not in existing]

            logger.info(
                "existing_filtered",
                total=len(domains),
                existing=len(existing),
                new=len(new_domains)
            )

            return new_domains

        except Exception as e:
            logger.error("filter_existing_failed", error=str(e))
            return domains  # Return all if filtering fails

    async def save_discoveries(self, db: AsyncSession, domains: List[str]) -> int:
        """
        Save newly discovered domains to database with 'pending' status

        Uses individual inserts with conflict handling to prevent race conditions
        when multiple workers discover the same domain concurrently.

        Args:
            db: Database session
            domains: List of new domains

        Returns:
            Number of domains saved
        """
        if not domains:
            return 0

        logger.info("saving_discoveries", count=len(domains))

        saved_count = 0
        failed_count = 0
        now = datetime.utcnow()  # Use naive datetime for DB

        for domain_name in domains:
            try:
                # Check if domain already exists (race condition protection)
                stmt = select(Domain).where(Domain.domain == domain_name)
                result = await db.execute(stmt)
                existing = result.scalar_one_or_none()

                if existing:
                    logger.debug("domain_already_exists", domain=domain_name)
                    continue

                domain = Domain(
                    domain=domain_name,
                    discovered_at=now,
                    status='pending',
                    is_live=False,
                )
                db.add(domain)
                await db.flush()  # Flush to catch constraint violations early
                saved_count += 1

            except Exception as e:
                # Handle unique constraint violation (race condition)
                if "UNIQUE constraint" in str(e) or "duplicate key" in str(e).lower():
                    logger.debug("duplicate_domain_skipped", domain=domain_name)
                else:
                    logger.warning("save_domain_failed", domain=domain_name, error=str(e))
                    failed_count += 1
                await db.rollback()  # Rollback this one domain
                continue

        try:
            await db.commit()
            logger.info("discoveries_saved", count=saved_count, failed=failed_count)
        except Exception as e:
            await db.rollback()
            logger.error("save_discoveries_commit_failed", error=str(e), error_type=type(e).__name__)
            return 0

        return saved_count

    async def run_discovery_pipeline(self, db: AsyncSession, hours_back: int = 24) -> dict:
        """
        Run complete discovery pipeline:
        1. Discover new domains from CT logs
        2. Filter out existing domains
        3. Save new domains to database

        Returns:
            Dictionary with discovery results
        """
        logger.info("discovery_pipeline_started")

        # Step 1: Discover from CT logs
        all_domains = await self.discover_new_domains(hours_back)

        # Step 2: Filter existing
        new_domains = await self.filter_existing(db, all_domains)

        # Step 3: Save to database
        saved_count = await self.save_discoveries(db, new_domains)

        result = {
            "domains_found": len(all_domains),
            "domains_new": len(new_domains),
            "domains_saved": saved_count,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        logger.info("discovery_pipeline_completed", **result)
        return result
