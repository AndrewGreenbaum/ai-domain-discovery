"""Screenshot capture service using Playwright"""
import asyncio
from datetime import datetime
from typing import Optional
import structlog
from playwright.async_api import async_playwright, Browser, Page, TimeoutError as PlaywrightTimeout
from config.settings import settings

logger = structlog.get_logger()


class ScreenshotService:
    """Handle screenshot capture with Playwright"""

    def __init__(self):
        """Initialize screenshot service"""
        self.timeout = settings.screenshot_timeout * 1000  # Convert to ms
        self._browser: Optional[Browser] = None

    async def __aenter__(self):
        """Async context manager entry"""
        await self.start_browser()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.stop_browser()

    async def start_browser(self):
        """Start Playwright browser (headless)"""
        try:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=True,
                args=[
                    '--disable-gpu',
                    '--no-sandbox',
                    '--disable-dev-shm-usage',  # Important for Docker/limited memory
                    '--disable-setuid-sandbox',
                    '--disable-web-security',
                ]
            )
            logger.info("playwright_browser_started")
        except Exception as e:
            logger.error("browser_start_failed", error=str(e))
            raise

    async def stop_browser(self):
        """Stop Playwright browser"""
        if self._browser:
            try:
                await self._browser.close()
            except Exception as e:
                logger.warning("browser_close_error", error=str(e))
            finally:
                self._browser = None

        if hasattr(self, '_playwright') and self._playwright:
            try:
                await self._playwright.stop()
            except Exception as e:
                logger.warning("playwright_stop_error", error=str(e))
            finally:
                self._playwright = None

            logger.info("playwright_browser_stopped")

    async def capture_screenshot(
        self,
        domain: str,
        url: Optional[str] = None
    ) -> Optional[bytes]:
        """
        Capture screenshot of domain

        Args:
            domain: Domain name (e.g., "autoai.ai")
            url: Optional full URL (defaults to https://{domain})

        Returns:
            Screenshot bytes (PNG) or None if failed
        """
        if not self._browser:
            await self.start_browser()

        if not url:
            url = f"https://{domain}"

        page: Optional[Page] = None

        try:
            # Create new page
            page = await self._browser.new_page(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )

            # Navigate to URL with timeout
            logger.info("screenshot_navigating", domain=domain, url=url)
            await page.goto(url, timeout=self.timeout, wait_until='networkidle')

            # Wait a bit for dynamic content
            await asyncio.sleep(2)

            # Capture screenshot
            screenshot_bytes = await page.screenshot(
                type='png',
                full_page=True  # Capture entire page
            )

            logger.info("screenshot_captured",
                       domain=domain,
                       size_kb=len(screenshot_bytes) / 1024)

            return screenshot_bytes

        except PlaywrightTimeout:
            logger.warning("screenshot_timeout",
                          domain=domain,
                          timeout_s=settings.screenshot_timeout)
            return None

        except Exception as e:
            logger.error("screenshot_failed",
                        domain=domain,
                        error=str(e),
                        error_type=type(e).__name__)
            return None

        finally:
            if page:
                await page.close()

    async def capture_viewport_only(
        self,
        domain: str,
        url: Optional[str] = None
    ) -> Optional[bytes]:
        """
        Capture only viewport (not full page) - faster

        Args:
            domain: Domain name
            url: Optional full URL

        Returns:
            Screenshot bytes or None
        """
        if not self._browser:
            await self.start_browser()

        if not url:
            url = f"https://{domain}"

        page: Optional[Page] = None

        try:
            page = await self._browser.new_page(
                viewport={'width': 1920, 'height': 1080}
            )

            await page.goto(url, timeout=self.timeout, wait_until='domcontentloaded')
            await asyncio.sleep(1)

            screenshot_bytes = await page.screenshot(
                type='png',
                full_page=False  # Only viewport
            )

            logger.info("viewport_screenshot_captured",
                       domain=domain,
                       size_kb=len(screenshot_bytes) / 1024)

            return screenshot_bytes

        except Exception as e:
            logger.error("viewport_screenshot_failed",
                        domain=domain,
                        error=str(e))
            return None

        finally:
            if page:
                await page.close()
