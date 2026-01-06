"""GitHub Discovery - Find .ai domains from GitHub repositories (FREE)"""
import httpx
import re
import asyncio
from typing import List, Set
from datetime import datetime, timedelta
from utils.logger import logger
from utils.helpers import clean_domain, is_valid_domain


class GitHubDiscoveryService:
    """
    Discover .ai domains from GitHub repositories
    FREE: 60 requests/hour without auth, 5000/hour with token
    """

    def __init__(self, github_token: str = None):
        self.code_api_url = "https://api.github.com/search/code"
        self.repo_api_url = "https://api.github.com/search/repositories"

        # Try to get token from settings if not provided
        if github_token is None:
            try:
                from config.settings import settings
                github_token = settings.github_token
            except:
                pass

        self.github_token = github_token
        self.domain_pattern = re.compile(r'\b([a-zA-Z][a-zA-Z0-9-]*\.ai)\b', re.IGNORECASE)

        if self.github_token:
            logger.info("github_discovery_authenticated", rate_limit="5000/hour")
        else:
            logger.warning("github_discovery_unauthenticated", rate_limit="60/hour",
                          message="Set GITHUB_TOKEN in .env for 83x more requests")

    async def discover_from_github(self, days_back: int = 7) -> List[str]:
        """
        Search GitHub for .ai domains in recent commits/repos

        Args:
            days_back: How many days back to search

        Returns:
            List of discovered .ai domains
        """
        logger.info("github_discovery_started", days_back=days_back, has_token=bool(self.github_token))

        domains: Set[str] = set()
        cutoff_date = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%d")

        # EXPANDED: More search queries for better coverage
        # With token: can run all queries (5000/hr)
        # Without token: limited to first 2 queries (60/hr)
        search_queries = [
            # Code searches (requires authentication for best results)
            f'".ai" created:>{cutoff_date} language:markdown',
            f'".ai" created:>{cutoff_date} filename:README',
            f'site:.ai created:>{cutoff_date}',
            f'"https://" ".ai" created:>{cutoff_date} filename:package.json',
            f'"homepage" ".ai" created:>{cutoff_date}',
            f'"url" ".ai" created:>{cutoff_date} filename:config',
        ]

        # Repository searches (find repos with .ai in name or description)
        repo_queries = [
            f".ai created:>{cutoff_date}",
            f"AI tool .ai created:>{cutoff_date}",
            f"artificial intelligence .ai created:>{cutoff_date}",
        ]

        headers = {
            "Accept": "application/vnd.github.v3.text-match+json"
        }
        if self.github_token:
            headers["Authorization"] = f"Bearer {self.github_token}"

        # Determine how many queries to run based on token
        max_code_queries = len(search_queries) if self.github_token else 2
        max_repo_queries = len(repo_queries) if self.github_token else 1

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                # Code searches
                for query in search_queries[:max_code_queries]:
                    try:
                        response = await client.get(
                            self.code_api_url,
                            params={"q": query, "per_page": 50},
                            headers=headers
                        )

                        if response.status_code == 200:
                            data = response.json()
                            items = data.get('items', [])

                            for item in items:
                                # Extract domains from text matches
                                text_content = item.get('text_matches', [])
                                for match in text_content:
                                    fragment = match.get('fragment', '')
                                    found_domains = self._extract_domains(fragment)
                                    domains.update(found_domains)

                                # Also check repository URL
                                repo = item.get('repository', {})
                                homepage = repo.get('homepage', '')
                                if homepage:
                                    found = self._extract_domains(homepage)
                                    domains.update(found)

                        elif response.status_code == 403:
                            remaining = response.headers.get('X-RateLimit-Remaining', '0')
                            logger.warning("github_rate_limited", remaining=remaining)
                            if remaining == '0':
                                break

                        await asyncio.sleep(0.5)  # Rate limiting

                    except Exception as e:
                        logger.warning("github_code_query_failed", query=query[:50], error=str(e))
                        continue

                # Repository searches
                for query in repo_queries[:max_repo_queries]:
                    try:
                        response = await client.get(
                            self.repo_api_url,
                            params={"q": query, "per_page": 50, "sort": "updated"},
                            headers=headers
                        )

                        if response.status_code == 200:
                            data = response.json()
                            items = data.get('items', [])

                            for item in items:
                                # Check homepage URL
                                homepage = item.get('homepage', '')
                                if homepage:
                                    found = self._extract_domains(homepage)
                                    domains.update(found)

                                # Check description
                                description = item.get('description', '') or ''
                                found = self._extract_domains(description)
                                domains.update(found)

                                # Check repo name
                                name = item.get('name', '')
                                if name and '.ai' in name.lower():
                                    found = self._extract_domains(name)
                                    domains.update(found)

                        await asyncio.sleep(0.5)

                    except Exception as e:
                        logger.warning("github_repo_query_failed", query=query[:50], error=str(e))
                        continue

        except Exception as e:
            logger.error("github_discovery_failed", error=str(e))

        # Filter out common false positives
        filtered = {d for d in domains
                   if len(d) > 4
                   and d not in ['the.ai', 'an.ai', 'is.ai', 'to.ai', 'of.ai', 'in.ai', 'on.ai', 'for.ai']
                   and not d.startswith('-')
                   and not d.endswith('-')}

        unique_domains = list(filtered)
        logger.info("github_discovery_completed", domains_found=len(unique_domains))

        return unique_domains

    def _extract_domains(self, text: str) -> Set[str]:
        """Extract .ai domains from text using regex"""
        domains = set()

        if not text:
            return domains

        matches = self.domain_pattern.findall(text.lower())
        for match in matches:
            domain = clean_domain(match)
            if is_valid_domain(domain) and len(domain) > 4:
                domains.add(domain)

        return domains
