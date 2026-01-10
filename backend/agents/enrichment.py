"""
ENRICHMENT AGENT
Visual enrichment, screenshot capture, and LLM content analysis for premium domains
"""
import asyncio
from datetime import datetime, timezone
from typing import Optional
import structlog
from services.screenshot_service import ScreenshotService
from services.s3_service import S3Service
from services.mcp_services import playwright_service  # MCP integration
from services.llm_evaluator import LLMEvaluator  # LLM for content analysis
from models.schemas import EnrichmentResult
from config.settings import settings

logger = structlog.get_logger()


class EnrichmentAgent:
    """
    Agent 5: ENRICHMENT

    Captures screenshots and performs visual analysis for premium domains.
    Only runs for domains with quality_score >= 70 AND is_live == True
    """

    def __init__(self):
        """Initialize enrichment agent"""
        self.screenshot_service = ScreenshotService()
        self.s3_service = S3Service()
        self.playwright_service = playwright_service  # MCP Playwright integration
        self.llm_evaluator = LLMEvaluator()  # LLM for content analysis

        logger.info("enrichment_agent_initialized",
                   enabled=settings.screenshot_enabled,
                   threshold=settings.enrichment_score_threshold,
                   llm_available=self.llm_evaluator.is_available())

    async def enrich_domain(
        self,
        domain: str,
        validation_data: dict
    ) -> EnrichmentResult:
        """
        Run complete enrichment pipeline for a domain

        Args:
            domain: Domain name (e.g., "autoai.ai")
            validation_data: Validation results from ValidationAgent

        Returns:
            EnrichmentResult with screenshot URL and analysis
        """
        start_time = datetime.utcnow()  # Use naive datetime for DB

        logger.info("enrichment_started", domain=domain)

        # Check if enrichment is enabled
        if not settings.screenshot_enabled:
            logger.info("enrichment_disabled", domain=domain)
            return EnrichmentResult(
                domain=domain,
                enriched_at=start_time,
                screenshot_url=None,
                screenshot_path=None,
                screenshot_status="disabled",
                visual_analysis=None,
                enrichment_confidence=0.0
            )

        # Initialize result
        result = EnrichmentResult(
            domain=domain,
            enriched_at=start_time,
            screenshot_url=None,
            screenshot_path=None,
            screenshot_status="pending",
            visual_analysis={},
            enrichment_confidence=0.0
        )

        try:
            # Step 1: Capture screenshot
            screenshot_result = await self._capture_and_upload_screenshot(
                domain,
                validation_data.get('final_url', f"https://{domain}")
            )

            if screenshot_result:
                result.screenshot_url = screenshot_result['url']
                result.screenshot_path = screenshot_result['key']
                result.screenshot_status = "captured"

                # Step 2: Analyze visual content using LLM
                visual_analysis = await self._analyze_visual_content(
                    domain=domain,
                    screenshot_url=screenshot_result['url'],
                    validation_data=validation_data  # Pass validation data for LLM analysis
                )
                result.visual_analysis = visual_analysis

                # Step 3: Extract page structure using MCP Playwright
                page_structure = await self._extract_page_structure_mcp(domain)
                if page_structure:
                    result.visual_analysis["page_structure"] = page_structure
                    result.enrichment_confidence = 0.9  # Higher confidence with structure data
                else:
                    result.enrichment_confidence = 0.8  # Basic confidence

                logger.info("enrichment_completed",
                           domain=domain,
                           screenshot_captured=True,
                           duration_s=(datetime.now(timezone.utc) - start_time).total_seconds())
            else:
                result.screenshot_status = "failed"
                logger.warning("enrichment_screenshot_failed", domain=domain)

        except Exception as e:
            logger.error("enrichment_error",
                        domain=domain,
                        error=str(e),
                        error_type=type(e).__name__)
            result.screenshot_status = "error"

        return result

    async def _capture_and_upload_screenshot(
        self,
        domain: str,
        url: str
    ) -> Optional[dict]:
        """
        Capture screenshot and upload to S3

        Args:
            domain: Domain name
            url: Full URL to capture

        Returns:
            Dict with {'url': s3_url, 'key': s3_key} or None if failed
        """
        try:
            # Start browser
            async with self.screenshot_service as screenshot_svc:
                # Capture screenshot
                screenshot_bytes = await screenshot_svc.capture_screenshot(domain, url)

                if not screenshot_bytes:
                    logger.warning("screenshot_capture_returned_none", domain=domain)
                    return None

                # Upload to S3
                s3_url, s3_key = await self.s3_service.upload_screenshot(
                    screenshot_bytes,
                    domain,
                    datetime.utcnow()  # Use naive datetime for consistency
                )

                return {
                    'url': s3_url,
                    'key': s3_key,
                    'size_bytes': len(screenshot_bytes)
                }

        except Exception as e:
            logger.error("screenshot_upload_error",
                        domain=domain,
                        error=str(e))
            return None

    async def _analyze_visual_content(
        self,
        domain: str,
        screenshot_url: str,
        validation_data: dict = None
    ) -> dict:
        """
        Analyze visual content using LLM

        Uses Claude to analyze the website content and provide:
        - Business model detection
        - Target audience identification
        - Quality assessment
        - Professionalism score
        - Key features and competitive advantages

        Args:
            domain: Domain name
            screenshot_url: S3 URL of screenshot
            validation_data: Optional validation data with content

        Returns:
            Dict with visual analysis results from LLM
        """
        # Start with basic result
        result = {
            "analyzed": False,
            "screenshot_url": screenshot_url
        }

        # Use LLM for deep content analysis if available
        if self.llm_evaluator.is_available() and validation_data:
            try:
                logger.info("llm_content_analysis_started", domain=domain)

                llm_analysis = await self.llm_evaluator.analyze_content_for_enrichment(
                    domain=domain,
                    title=validation_data.get('title', ''),
                    meta_description=validation_data.get('meta_description', ''),
                    content_sample=validation_data.get('content_sample', ''),
                    page_structure=None  # Will be added in step 3
                )

                # Merge LLM analysis into result
                result.update({
                    "analyzed": True,
                    "llm_analysis": llm_analysis,
                    "business_model": llm_analysis.get("business_model"),
                    "target_audience": llm_analysis.get("target_audience"),
                    "product_description": llm_analysis.get("product_description"),
                    "quality_assessment": llm_analysis.get("quality_assessment"),
                    "professionalism_score": llm_analysis.get("professionalism_score"),
                    "key_features": llm_analysis.get("key_features", []),
                    "competitive_advantages": llm_analysis.get("competitive_advantages", []),
                    "pricing_model": llm_analysis.get("pricing_model"),
                    "category": llm_analysis.get("category"),
                    "llm_cost_usd": llm_analysis.get("cost_usd", 0.0)
                })

                logger.info("llm_content_analysis_completed",
                           domain=domain,
                           business_model=llm_analysis.get("business_model"),
                           quality=llm_analysis.get("quality_assessment"),
                           cost_usd=llm_analysis.get("cost_usd", 0))

            except Exception as e:
                logger.error("llm_content_analysis_error",
                           domain=domain,
                           error=str(e))
                result["llm_error"] = str(e)
        else:
            if not self.llm_evaluator.is_available():
                result["note"] = "LLM unavailable - set ANTHROPIC_API_KEY"
            else:
                result["note"] = "No validation data for LLM analysis"

        return result

    async def _extract_page_structure_mcp(self, domain: str) -> Optional[dict]:
        """
        Extract page structure using MCP Playwright service

        Args:
            domain: Domain name

        Returns:
            Page structure data or None if failed
        """
        try:
            logger.info("extracting_page_structure_mcp", domain=domain)

            structure = await self.playwright_service.extract_page_structure(domain)

            if structure:
                logger.info("page_structure_extracted",
                           domain=domain,
                           h1_count=len(structure.get("headings", {}).get("h1", [])),
                           links=structure.get("counts", {}).get("links", 0))

                return {
                    "headings": structure.get("headings", {}),
                    "element_counts": structure.get("counts", {}),
                    "has_navigation": structure.get("structure", {}).get("hasNav", False),
                    "has_footer": structure.get("structure", {}).get("hasFooter", False),
                    "has_video": structure.get("structure", {}).get("hasVideo", False),
                    "meta_description": structure.get("meta", {}).get("description", ""),
                    "og_image": structure.get("meta", {}).get("ogImage", "")
                }

            return None

        except Exception as e:
            logger.error("page_structure_extraction_failed",
                        domain=domain,
                        error=str(e))
            return None

    async def cleanup(self):
        """Cleanup resources"""
        if hasattr(self.screenshot_service, '_browser') and self.screenshot_service._browser:
            await self.screenshot_service.stop_browser()

        logger.info("enrichment_agent_cleanup_completed")
