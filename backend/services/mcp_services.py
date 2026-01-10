"""
MCP Integration Services
Provides access to external MCP services for enhanced agent capabilities
"""
from typing import Dict, List, Optional, Any
import os
import httpx
import asyncio
from datetime import datetime

from utils.logger import logger


class BraveSearchService:
    """
    Brave Search API integration for web and local search
    Replaces manual scraping with structured search results
    """

    def __init__(self):
        # Try to get from settings first, fallback to env var
        try:
            from config.settings import settings
            self.api_key = settings.brave_search_api_key or os.getenv("BRAVE_SEARCH_API_KEY", "")
        except:
            self.api_key = os.getenv("BRAVE_SEARCH_API_KEY", "")

        self.base_url = "https://api.search.brave.com/res/v1"
        self.timeout = httpx.Timeout(30.0)

        if not self.api_key:
            logger.warning("brave_search_no_api_key",
                          message="BRAVE_SEARCH_API_KEY not set, search features disabled")

    async def web_search(self,
                         query: str,
                         count: int = 10,
                         freshness: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Perform web search using Brave Search API

        Args:
            query: Search query
            count: Number of results (1-20)
            freshness: Filter by freshness (e.g., "pw" for past week, "pd" for past day)

        Returns:
            List of search results with title, url, description
        """
        if not self.api_key:
            logger.warning("brave_search_disabled", query=query)
            return []

        try:
            headers = {
                "Accept": "application/json",
                "X-Subscription-Token": self.api_key
            }

            params = {
                "q": query,
                "count": min(count, 20)  # API max is 20
            }

            if freshness:
                params["freshness"] = freshness

            async with httpx.AsyncClient(timeout=self.timeout, headers=headers) as client:
                response = await client.get(f"{self.base_url}/web/search", params=params)

                if response.status_code == 200:
                    data = response.json()
                    results = []

                    for item in data.get("web", {}).get("results", []):
                        results.append({
                            "title": item.get("title", ""),
                            "url": item.get("url", ""),
                            "description": item.get("description", ""),
                            "age": item.get("age"),
                            "page_age": item.get("page_age")
                        })

                    logger.info("brave_search_success",
                               query=query,
                               results_count=len(results))
                    return results
                else:
                    logger.error("brave_search_error",
                                query=query,
                                status_code=response.status_code)
                    return []

        except Exception as e:
            logger.error("brave_search_exception", query=query, error=str(e))
            return []

    async def local_search(self, query: str, count: int = 5) -> List[Dict[str, Any]]:
        """
        Perform local business search using Brave Local Search API

        Args:
            query: Local search query (e.g., "AI startups in San Francisco")
            count: Number of results (1-20)

        Returns:
            List of local results with business info
        """
        if not self.api_key:
            logger.warning("brave_local_search_disabled", query=query)
            return []

        try:
            headers = {
                "Accept": "application/json",
                "X-Subscription-Token": self.api_key
            }

            params = {
                "q": query,
                "count": min(count, 20)
            }

            async with httpx.AsyncClient(timeout=self.timeout, headers=headers) as client:
                response = await client.get(f"{self.base_url}/local/search", params=params)

                if response.status_code == 200:
                    data = response.json()
                    results = []

                    for item in data.get("results", []):
                        results.append({
                            "name": item.get("title", ""),
                            "address": item.get("address", ""),
                            "phone": item.get("phone"),
                            "rating": item.get("rating"),
                            "reviews": item.get("review_count")
                        })

                    logger.info("brave_local_search_success",
                               query=query,
                               results_count=len(results))
                    return results
                else:
                    logger.error("brave_local_search_error",
                                query=query,
                                status_code=response.status_code)
                    return []

        except Exception as e:
            logger.error("brave_local_search_exception", query=query, error=str(e))
            return []

    async def search_domain_mentions(self, domain: str, days_back: int = 30) -> List[Dict[str, Any]]:
        """
        Search for recent mentions of a domain across the web

        Args:
            domain: Domain name to search for
            days_back: How many days back to search (7, 30, 90)

        Returns:
            List of recent mentions with context
        """
        # Map days to Brave freshness parameter
        freshness_map = {
            1: "pd",    # past day
            7: "pw",    # past week
            30: "pm",   # past month
            90: "py"    # past year
        }

        # Find closest freshness parameter
        freshness = None
        for days, param in sorted(freshness_map.items()):
            if days_back <= days:
                freshness = param
                break

        query = f'"{domain}"'
        return await self.web_search(query, count=20, freshness=freshness)

    async def search_company_info(self, company_name: str) -> List[Dict[str, Any]]:
        """
        Search for company information (funding, team, news)

        Args:
            company_name: Company name to research

        Returns:
            List of relevant search results
        """
        queries = [
            f'"{company_name}" funding',
            f'"{company_name}" founders',
            f'"{company_name}" AI startup',
            f'"{company_name}" launch'
        ]

        all_results = []
        for query in queries:
            results = await self.web_search(query, count=5)
            all_results.extend(results)
            await asyncio.sleep(0.5)  # Rate limiting

        # Deduplicate by URL
        seen_urls = set()
        unique_results = []
        for result in all_results:
            if result["url"] not in seen_urls:
                seen_urls.add(result["url"])
                unique_results.append(result)

        return unique_results[:20]  # Return top 20 unique results


class PlaywrightService:
    """
    Enhanced Playwright integration using MCP capabilities
    Provides better screenshot and page analysis features
    """

    def __init__(self):
        self.timeout = 30000  # 30 seconds
        self.enabled = os.getenv("SCREENSHOT_ENABLED", "true").lower() == "true"

    async def capture_full_page_screenshot(self,
                                           domain: str,
                                           save_path: str) -> Optional[Dict[str, Any]]:
        """
        Capture full-page screenshot using Playwright

        Args:
            domain: Domain to screenshot
            save_path: Where to save the screenshot

        Returns:
            Screenshot metadata (path, dimensions, etc.)
        """
        if not self.enabled:
            logger.warning("playwright_disabled", domain=domain)
            return None

        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()

                # Navigate to page
                url = f"https://{domain}"
                await page.goto(url, timeout=self.timeout, wait_until="networkidle")

                # Take full page screenshot
                await page.screenshot(path=save_path, full_page=True)

                # Get page dimensions
                dimensions = await page.evaluate("""
                    () => {
                        return {
                            width: document.documentElement.scrollWidth,
                            height: document.documentElement.scrollHeight
                        }
                    }
                """)

                # Get page title
                title = await page.title()

                await browser.close()

                logger.info("screenshot_captured",
                           domain=domain,
                           path=save_path,
                           dimensions=dimensions)

                return {
                    "path": save_path,
                    "width": dimensions["width"],
                    "height": dimensions["height"],
                    "title": title,
                    "captured_at": datetime.utcnow().isoformat()
                }

        except Exception as e:
            logger.error("screenshot_failed", domain=domain, error=str(e))
            return None

    async def extract_page_structure(self, domain: str) -> Optional[Dict[str, Any]]:
        """
        Extract detailed page structure and metadata

        Args:
            domain: Domain to analyze

        Returns:
            Page structure data (headings, links, forms, etc.)
        """
        if not self.enabled:
            logger.warning("playwright_disabled", domain=domain)
            return None

        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()

                url = f"https://{domain}"
                await page.goto(url, timeout=self.timeout, wait_until="domcontentloaded")

                # Extract page structure
                structure = await page.evaluate("""
                    () => {
                        // Count elements
                        const h1s = Array.from(document.querySelectorAll('h1')).map(h => h.textContent.trim());
                        const h2s = Array.from(document.querySelectorAll('h2')).map(h => h.textContent.trim());
                        const links = document.querySelectorAll('a').length;
                        const images = document.querySelectorAll('img').length;
                        const forms = document.querySelectorAll('form').length;
                        const buttons = document.querySelectorAll('button').length;

                        // Check for specific elements
                        const hasNav = document.querySelector('nav') !== null;
                        const hasFooter = document.querySelector('footer') !== null;
                        const hasVideo = document.querySelector('video') !== null;

                        // Get meta tags
                        const metaDescription = document.querySelector('meta[name="description"]')?.content || '';
                        const ogImage = document.querySelector('meta[property="og:image"]')?.content || '';

                        return {
                            headings: {
                                h1: h1s,
                                h2: h2s
                            },
                            counts: {
                                links: links,
                                images: images,
                                forms: forms,
                                buttons: buttons
                            },
                            structure: {
                                hasNav: hasNav,
                                hasFooter: hasFooter,
                                hasVideo: hasVideo
                            },
                            meta: {
                                description: metaDescription,
                                ogImage: ogImage
                            }
                        };
                    }
                """)

                await browser.close()

                logger.info("page_structure_extracted", domain=domain)
                return structure

        except Exception as e:
            logger.error("page_structure_extraction_failed", domain=domain, error=str(e))
            return None


class FetchService:
    """
    Enhanced HTTP fetch service using MCP fetch capabilities
    Provides better content fetching and parsing
    """

    def __init__(self):
        self.timeout = httpx.Timeout(30.0)
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

    async def fetch_url_with_metadata(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Fetch URL and extract rich metadata

        Args:
            url: URL to fetch

        Returns:
            Content and metadata
        """
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                headers=self.headers,
                follow_redirects=True
            ) as client:
                response = await client.get(url)

                if response.status_code == 200:
                    return {
                        "url": str(response.url),
                        "status_code": response.status_code,
                        "content": response.text,
                        "headers": dict(response.headers),
                        "encoding": response.encoding,
                        "is_redirect": str(response.url) != url,
                        "final_url": str(response.url)
                    }
                else:
                    logger.warning("fetch_non_200", url=url, status=response.status_code)
                    return None

        except Exception as e:
            logger.error("fetch_failed", url=url, error=str(e))
            return None

    async def fetch_multiple_urls(self, urls: List[str]) -> List[Dict[str, Any]]:
        """
        Fetch multiple URLs concurrently

        Args:
            urls: List of URLs to fetch

        Returns:
            List of fetch results
        """
        tasks = [self.fetch_url_with_metadata(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out exceptions and None values
        return [r for r in results if r is not None and not isinstance(r, Exception)]


# Singleton instances
brave_search = BraveSearchService()
playwright_service = PlaywrightService()
fetch_service = FetchService()
