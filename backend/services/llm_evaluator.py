"""
LLM Evaluator Service - UNIFIED Claude integration for domain evaluation
Consolidates llm_evaluator.py and llm_service.py into single service.

Features:
- Native async via httpx (no blocking)
- Retry logic for rate limiting
- Scoring mode support (conservative/moderate/aggressive)
- Cost tracking
- Multiple evaluation methods (evaluate_domain, classify_content, etc.)
"""
import os
import asyncio
import json
import base64
import httpx
from typing import Dict, Optional, Any, Union
from models.schemas import ValidationResult
from utils.logger import logger

# Try to load settings, fall back to env vars
try:
    from config.settings import settings
except ImportError:
    settings = None


class LLMEvaluator:
    """
    UNIFIED LLM service for domain evaluation.

    This is the SINGLE source of truth for LLM calls. Do NOT use llm_service.py.
    """

    # Scoring mode presets
    SCORING_MODES = {
        "conservative": (35, 85),   # Expanded range
        "moderate": (30, 90),       # Expanded range
        "aggressive": (0, 100),     # ALL live domains
    }

    def __init__(self):
        # Get API key from settings or env
        if settings and settings.anthropic_api_key:
            self.api_key = settings.anthropic_api_key
        else:
            self.api_key = os.getenv("ANTHROPIC_API_KEY")

        if not self.api_key:
            logger.warning("llm_evaluator_no_api_key",
                          message="ANTHROPIC_API_KEY not set - LLM evaluation disabled")

        self.model = os.getenv("LLM_MODEL", "claude-3-5-sonnet-20241022")
        self.temperature = float(os.getenv("LLM_TEMPERATURE", "0.3"))
        self.max_tokens = int(os.getenv("LLM_MAX_TOKENS", "500"))

        # Apply scoring mode
        if settings:
            scoring_mode = getattr(settings, 'llm_scoring_mode', 'aggressive')
        else:
            scoring_mode = os.getenv("LLM_SCORING_MODE", "aggressive")

        if scoring_mode in self.SCORING_MODES:
            self.score_min, self.score_max = self.SCORING_MODES[scoring_mode]
        else:
            self.score_min, self.score_max = 0, 100

        self.scoring_mode = scoring_mode

        logger.info("llm_evaluator_initialized",
                   model=self.model,
                   scoring_mode=scoring_mode,
                   score_range=f"{self.score_min}-{self.score_max}")

    async def _call_anthropic(self, prompt: str, max_tokens: int = None) -> tuple:
        """
        Native async call to Anthropic API via httpx.

        Returns:
            (response_text, usage_dict) or raises exception
        """
        if max_tokens is None:
            max_tokens = self.max_tokens

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.model,
                    "max_tokens": max_tokens,
                    "temperature": self.temperature,
                    "messages": [{"role": "user", "content": prompt}],
                    "system": "You are an expert startup analyst. Respond in the exact format requested."
                }
            )

            response.raise_for_status()
            data = response.json()

            response_text = data["content"][0]["text"]
            usage = {
                "input_tokens": data.get("usage", {}).get("input_tokens", 0),
                "output_tokens": data.get("usage", {}).get("output_tokens", 0)
            }

            return response_text, usage

    async def _call_anthropic_vision(
        self,
        text_prompt: str,
        image_data: bytes,
        media_type: str = "image/png",
        max_tokens: int = None
    ) -> tuple:
        """
        Call Claude API with vision/image content (Claude 3.5 Sonnet supports vision).

        Args:
            text_prompt: The text prompt to accompany the image
            image_data: Raw image bytes (PNG, JPEG, etc.)
            media_type: MIME type of the image (image/png, image/jpeg, etc.)
            max_tokens: Max tokens for response

        Returns:
            (response_text, usage_dict) or raises exception
        """
        if max_tokens is None:
            max_tokens = self.max_tokens

        # Encode image to base64
        image_base64 = base64.b64encode(image_data).decode("utf-8")

        async with httpx.AsyncClient(timeout=60.0) as client:  # Longer timeout for vision
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.model,
                    "max_tokens": max_tokens,
                    "temperature": self.temperature,
                    "messages": [{
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": image_base64
                                }
                            },
                            {
                                "type": "text",
                                "text": text_prompt
                            }
                        ]
                    }],
                    "system": "You are an expert startup analyst with vision capabilities. Analyze visual elements carefully. Respond in the exact format requested."
                }
            )

            response.raise_for_status()
            data = response.json()

            response_text = data["content"][0]["text"]
            usage = {
                "input_tokens": data.get("usage", {}).get("input_tokens", 0),
                "output_tokens": data.get("usage", {}).get("output_tokens", 0)
            }

            return response_text, usage

    async def analyze_screenshot(
        self,
        domain: str,
        screenshot_bytes: bytes,
        validation: Optional[ValidationResult] = None
    ) -> Dict:
        """
        Analyze a website screenshot using Claude's vision capabilities.

        This provides visual analysis of:
        - Professional design quality
        - Brand presence and legitimacy
        - UI/UX maturity
        - Parking page detection
        - Coming soon vs real product
        - Visual red flags (stock photos, generic templates)

        Args:
            domain: Domain name being analyzed
            screenshot_bytes: PNG screenshot bytes
            validation: Optional validation data for context

        Returns:
            {
                "visual_quality": "high" | "medium" | "low",
                "is_parking_visual": bool,
                "is_coming_soon_visual": bool,
                "has_real_product": bool,
                "design_maturity": 1-10,
                "brand_presence": bool,
                "visual_red_flags": ["flag1", "flag2"],
                "visual_positive_signals": ["signal1", "signal2"],
                "visual_assessment": "brief description",
                "suggested_score_modifier": -20 to +20,
                "confidence": 0.0-1.0,
                "cost_usd": float
            }
        """
        if not self.api_key:
            logger.error("vision_analysis_disabled", domain=domain)
            return self._fallback_vision_response()

        # Build context from validation if available
        context_info = ""
        if validation:
            context_info = f"""
Additional context from validation:
- Title: {validation.title or 'Unknown'}
- Is Live: {validation.is_live}
- Is Parking (text analysis): {validation.is_parking}
- Is For Sale: {validation.is_for_sale}
"""

        prompt = f"""Analyze this website screenshot for {domain}.
{context_info}
Evaluate the visual design, professionalism, and legitimacy. Look for:

1. DESIGN QUALITY: Is this professionally designed or template/generic?
2. BRAND PRESENCE: Does it have a real logo, brand colors, unique identity?
3. PRODUCT VISIBILITY: Can you see actual product UI, features, or just marketing?
4. PARKING INDICATORS: Generic "domain for sale", placeholder images, registrar branding?
5. COMING SOON: Countdown timer, waitlist form, "launching soon" with no real content?
6. RED FLAGS: Stock photos everywhere, broken images, Lorem ipsum, generic startup templates
7. LEGITIMACY SIGNALS: Team photos, real testimonials, actual screenshots, pricing pages

Respond in JSON format:
{{
    "visual_quality": "high" | "medium" | "low",
    "is_parking_visual": true/false,
    "is_coming_soon_visual": true/false,
    "has_real_product": true/false,
    "design_maturity": 1-10,
    "brand_presence": true/false,
    "visual_red_flags": ["list of concerning visual elements"],
    "visual_positive_signals": ["list of good visual signals"],
    "visual_assessment": "2-3 sentence assessment of what you see",
    "suggested_score_modifier": -20 to +20 (negative for poor quality, positive for high quality),
    "confidence": 0.0-1.0
}}"""

        try:
            logger.info("vision_analysis_started", domain=domain, model=self.model)

            response_text, usage = await self._call_anthropic_vision(
                prompt, screenshot_bytes, max_tokens=800
            )

            result = self._parse_vision_response(response_text, domain)
            cost_usd = self._calculate_cost_from_dict(usage)
            result["cost_usd"] = cost_usd

            logger.info(
                "vision_analysis_completed",
                domain=domain,
                visual_quality=result.get("visual_quality"),
                has_product=result.get("has_real_product"),
                score_modifier=result.get("suggested_score_modifier"),
                cost_usd=cost_usd
            )

            return result

        except Exception as e:
            logger.error("vision_analysis_failed", domain=domain, error=str(e))
            return self._fallback_vision_response()

    def _parse_vision_response(self, response_text: str, domain: str) -> Dict:
        """Parse vision analysis response"""
        try:
            # Clean response
            text = response_text.strip()
            if text.startswith("```json"):
                text = text[7:]
            elif text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]

            result = json.loads(text.strip())

            # Ensure required fields with defaults
            result.setdefault("visual_quality", "medium")
            result.setdefault("is_parking_visual", False)
            result.setdefault("is_coming_soon_visual", False)
            result.setdefault("has_real_product", False)
            result.setdefault("design_maturity", 5)
            result.setdefault("brand_presence", False)
            result.setdefault("visual_red_flags", [])
            result.setdefault("visual_positive_signals", [])
            result.setdefault("visual_assessment", "")
            result.setdefault("suggested_score_modifier", 0)
            result.setdefault("confidence", 0.5)

            # Clamp score modifier
            result["suggested_score_modifier"] = max(-20, min(20, result["suggested_score_modifier"]))

            return result

        except json.JSONDecodeError as e:
            logger.warning("vision_response_parse_error", domain=domain, error=str(e))
            return self._fallback_vision_response()

    def _fallback_vision_response(self) -> Dict:
        """Fallback when vision analysis unavailable"""
        return {
            "visual_quality": "unknown",
            "is_parking_visual": False,
            "is_coming_soon_visual": False,
            "has_real_product": False,
            "design_maturity": 5,
            "brand_presence": False,
            "visual_red_flags": [],
            "visual_positive_signals": [],
            "visual_assessment": "Vision analysis unavailable",
            "suggested_score_modifier": 0,
            "confidence": 0.0,
            "cost_usd": 0.0
        }

    async def research_with_web_search(
        self,
        domain: str,
        company_name: Optional[str] = None,
        validation: Optional[ValidationResult] = None
    ) -> Dict:
        """
        Use web search to research a domain/company, then analyze with LLM.

        This performs:
        1. Web search for domain mentions, company info, funding, founders
        2. LLM analysis of search results to extract intelligence
        3. Company age/establishment detection
        4. Red flag identification from public sources

        Args:
            domain: Domain name to research
            company_name: Optional company name (extracted from site)
            validation: Optional validation data for context

        Returns:
            {
                "company_found": bool,
                "company_name": str or None,
                "company_age_years": int or None,
                "is_established_company": bool,
                "funding_info": str or None,
                "founder_info": str or None,
                "news_mentions": list,
                "red_flags": list,
                "positive_signals": list,
                "research_summary": str,
                "suggested_score_modifier": -30 to +20,
                "confidence": 0.0-1.0,
                "cost_usd": float
            }
        """
        if not self.api_key:
            logger.error("web_research_disabled", domain=domain)
            return self._fallback_web_research_response()

        # Import brave_search service
        try:
            from services.mcp_services import brave_search
        except ImportError:
            logger.error("brave_search_import_failed", domain=domain)
            return self._fallback_web_research_response()

        # Perform web searches
        search_results = []

        try:
            # Search for domain mentions
            domain_results = await brave_search.web_search(f'"{domain}"', count=10)
            search_results.extend(domain_results)

            # Search for company info if we have a company name
            if company_name:
                company_results = await brave_search.search_company_info(company_name)
                search_results.extend(company_results)
            else:
                # Try to get company name from domain
                domain_base = domain.replace('.ai', '').replace('-', ' ').replace('_', ' ')
                company_results = await brave_search.web_search(
                    f'"{domain_base}" AI startup company',
                    count=5
                )
                search_results.extend(company_results)

            # Search for funding/established info
            funding_results = await brave_search.web_search(
                f'"{domain}" OR "{company_name or domain_base}" funding raised series',
                count=5
            )
            search_results.extend(funding_results)

        except Exception as e:
            logger.error("web_search_failed", domain=domain, error=str(e))

        if not search_results:
            logger.warning("no_search_results", domain=domain)
            return self._fallback_web_research_response()

        # Deduplicate results
        seen_urls = set()
        unique_results = []
        for result in search_results:
            if result.get("url") not in seen_urls:
                seen_urls.add(result.get("url"))
                unique_results.append(result)

        # Format search results for LLM
        formatted_results = "\n".join([
            f"- [{r.get('title', 'No title')}]({r.get('url', '')}): {r.get('description', 'No description')[:200]}"
            for r in unique_results[:15]
        ])

        # Get additional context
        context_info = ""
        if validation:
            context_info = f"""
Site context:
- Title: {validation.title or 'Unknown'}
- Is Live: {validation.is_live}
- Domain Age Days: {getattr(validation, 'domain_age_days', 'Unknown')}
"""

        prompt = f"""Analyze these web search results about {domain} to determine if this is:
1. A genuinely NEW AI startup (founded < 1 year ago)
2. An established company's new product/domain
3. Unknown/insufficient information

{context_info}

WEB SEARCH RESULTS:
{formatted_results}

Look for:
- Company founding date mentions
- Funding history (if funded years ago, NOT a new startup)
- Founder/team mentions with history
- Previous products or company pivots
- News articles about launches
- Any indication this is a large company's side project

BE SKEPTICAL: If search results mention this company existed before 2024, or show substantial funding/history, it's NOT a new startup.

Respond in JSON format:
{{
    "company_found": true/false,
    "company_name": "extracted company name or null",
    "company_age_years": estimated years old or null,
    "is_established_company": true/false,
    "founding_year": year or null,
    "funding_info": "any funding mentioned or null",
    "founder_info": "founder names if found or null",
    "news_mentions": ["summary of relevant news"],
    "red_flags": ["concerns found in search results"],
    "positive_signals": ["good signs for new startup"],
    "research_summary": "2-3 sentence summary of findings",
    "suggested_score_modifier": -30 to +20 (-30 for established company, +20 for confirmed new startup with good signals),
    "confidence": 0.0-1.0
}}"""

        try:
            logger.info("web_research_started", domain=domain, results_count=len(unique_results))

            response_text, usage = await self._call_anthropic(prompt, max_tokens=1000)

            result = self._parse_web_research_response(response_text, domain)
            cost_usd = self._calculate_cost_from_dict(usage)
            result["cost_usd"] = cost_usd

            logger.info(
                "web_research_completed",
                domain=domain,
                company_found=result.get("company_found"),
                is_established=result.get("is_established_company"),
                score_modifier=result.get("suggested_score_modifier"),
                cost_usd=cost_usd
            )

            return result

        except Exception as e:
            logger.error("web_research_analysis_failed", domain=domain, error=str(e))
            return self._fallback_web_research_response()

    def _parse_web_research_response(self, response_text: str, domain: str) -> Dict:
        """Parse web research analysis response"""
        try:
            text = response_text.strip()
            if text.startswith("```json"):
                text = text[7:]
            elif text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]

            result = json.loads(text.strip())

            # Ensure required fields
            result.setdefault("company_found", False)
            result.setdefault("company_name", None)
            result.setdefault("company_age_years", None)
            result.setdefault("is_established_company", False)
            result.setdefault("founding_year", None)
            result.setdefault("funding_info", None)
            result.setdefault("founder_info", None)
            result.setdefault("news_mentions", [])
            result.setdefault("red_flags", [])
            result.setdefault("positive_signals", [])
            result.setdefault("research_summary", "")
            result.setdefault("suggested_score_modifier", 0)
            result.setdefault("confidence", 0.5)

            # Clamp score modifier
            result["suggested_score_modifier"] = max(-30, min(20, result["suggested_score_modifier"]))

            return result

        except json.JSONDecodeError as e:
            logger.warning("web_research_parse_error", domain=domain, error=str(e))
            return self._fallback_web_research_response()

    def _fallback_web_research_response(self) -> Dict:
        """Fallback when web research unavailable"""
        return {
            "company_found": False,
            "company_name": None,
            "company_age_years": None,
            "is_established_company": False,
            "founding_year": None,
            "funding_info": None,
            "founder_info": None,
            "news_mentions": [],
            "red_flags": [],
            "positive_signals": [],
            "research_summary": "Web research unavailable",
            "suggested_score_modifier": 0,
            "confidence": 0.0,
            "cost_usd": 0.0
        }

    async def evaluate_domain(
        self,
        domain: str,
        validation: ValidationResult,
        agent_score: int
    ) -> Dict:
        """
        Use Claude to evaluate if domain is a real startup.

        Args:
            domain: Domain name
            validation: Validation result from agents
            agent_score: Score from rule-based agents (for context)

        Returns:
            {
                "verdict": "REAL_STARTUP" | "FOR_SALE" | "PARKING" | "ESTABLISHED",
                "confidence": 0.95,
                "reasoning": "Detailed explanation...",
                "key_indicators": ["indicator1", "indicator2"],
                "suggested_score": 85,
                "cost_usd": 0.001,
                # Extended format (for compatibility with llm_service)
                "is_legitimate_startup": True,
                "category": "AI/ML",
                "red_flags": [],
                "positive_signals": []
            }
        """
        if not self.api_key:
            logger.error("llm_evaluation_disabled", domain=domain)
            return self._fallback_response(agent_score)

        # Build prompt
        prompt = self._build_evaluation_prompt(domain, validation, agent_score)

        # Retry logic for rate limiting
        max_retries = 3
        retry_delay = 2.0

        for attempt in range(max_retries):
            try:
                logger.info("llm_evaluation_started", domain=domain, model=self.model, attempt=attempt + 1)

                response_text, usage = await self._call_anthropic(prompt)

                # Parse response
                result = self._parse_llm_response(response_text, domain)

                # Calculate cost
                cost_usd = self._calculate_cost_from_dict(usage)
                result["cost_usd"] = cost_usd

                logger.info(
                    "llm_evaluation_completed",
                    domain=domain,
                    verdict=result["verdict"],
                    confidence=result["confidence"],
                    cost_usd=cost_usd
                )

                return result

            except httpx.HTTPStatusError as e:
                error_str = str(e).lower()
                status_code = e.response.status_code if hasattr(e, 'response') else 0

                # Check for rate limiting (429)
                if status_code == 429 or '429' in error_str or 'rate' in error_str:
                    if attempt < max_retries - 1:
                        wait_time = retry_delay * (2 ** attempt)
                        logger.warning("llm_rate_limited",
                                     domain=domain,
                                     attempt=attempt + 1,
                                     wait=wait_time)
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        logger.error("llm_rate_limit_exhausted",
                                   domain=domain,
                                   attempts=max_retries)
                else:
                    logger.error("llm_evaluation_failed",
                               domain=domain,
                               error=str(e),
                               status_code=status_code,
                               attempt=attempt + 1)
                return self._fallback_response(agent_score)

            except Exception as e:
                error_str = str(e).lower()
                if 'overloaded' in error_str:
                    if attempt < max_retries - 1:
                        wait_time = retry_delay * (2 ** attempt)
                        logger.warning("llm_overloaded",
                                     domain=domain,
                                     attempt=attempt + 1,
                                     wait=wait_time)
                        await asyncio.sleep(wait_time)
                        continue

                logger.error("llm_evaluation_failed",
                           domain=domain,
                           error=str(e),
                           attempt=attempt + 1)
                return self._fallback_response(agent_score)

        return self._fallback_response(agent_score)

    def _build_evaluation_prompt(
        self,
        domain: str,
        validation: ValidationResult,
        agent_score: int
    ) -> str:
        """Build structured prompt for Claude 3.5 Sonnet with enhanced reasoning"""

        # Extract domain age and company info if available
        domain_age_days = getattr(validation, 'domain_age_days', None)
        domain_created_date = getattr(validation, 'domain_created_date', None)
        parent_company = getattr(validation, 'parent_company', None)
        company_age = getattr(validation, 'company_age', None)
        is_redirect = getattr(validation, 'is_redirect', False)
        final_url = getattr(validation, 'final_url', None)

        # Build age section
        age_section = ""
        if domain_age_days is not None:
            age_section = f"\n- Domain Age: {domain_age_days} days (registered: {domain_created_date or 'Unknown'})"
            if domain_age_days > 365 * 3:
                age_section += "\n  ⚠️ CRITICAL: Domain is over 3 YEARS old - very unlikely to be a new startup!"
            elif domain_age_days > 365:
                age_section += "\n  ⚠️ WARNING: Domain is over 1 YEAR old - suspicious for 'new' startup"
        else:
            age_section = "\n- Domain Age: UNKNOWN (WHOIS lookup failed)"

        # Build company section
        company_section = ""
        if parent_company:
            company_section = f"\n- ⚠️ PARENT COMPANY DETECTED: {parent_company}"
        if company_age and company_age > 3:
            company_section += f"\n- ⚠️ Company Age: {company_age} years (ESTABLISHED - not a new startup!)"

        # Build redirect section
        redirect_section = ""
        if is_redirect:
            redirect_section = f"\n- ⚠️ REDIRECT DETECTED: Domain redirects to {final_url}"

        return f"""You are Claude 3.5 Sonnet, an expert AI startup analyst. Your task is to identify GENUINELY NEW AI startups vs parking pages, marketplaces, and ESTABLISHED companies masquerading as new.

## CRITICAL CONTEXT
You're evaluating domains from Certificate Transparency logs. Many established companies register NEW SSL certificates for:
- Product launches under new domains
- Marketing campaigns
- Rebrands or acquisitions
- Domain speculation/squatting

A new SSL certificate does NOT mean a new company!

## Domain Information
- Domain: {domain}
- Title: {validation.title or "N/A"}
- Meta Description: {validation.meta_description or "N/A"}
- HTTP Status: {validation.http_status_code}
- Has SSL: {validation.has_ssl}
- Is Live: {validation.is_live}
- Agent Score (rule-based): {agent_score}/100

## Age & Company Analysis (CRITICAL!)
{age_section}{company_section}{redirect_section}

## Page Content Sample
{validation.content_sample[:800] if validation.content_sample else "N/A"}

## Classification Options
1. REAL_STARTUP - Genuinely NEW AI startup (founded < 1 year ago)
2. FOR_SALE - Domain listed on marketplace for sale
3. PARKING - Parking/placeholder page with no real content
4. ESTABLISHED - Established company (older than 3 years) with new domain
5. REDIRECT - Redirects to another established company's site
6. COMING_SOON - Legitimate pre-launch page with real startup signals

## SCORING GUIDELINES (BE STRICT!)
- New startup (< 1 year, no parent company): 60-95 based on quality
- Coming soon (legitimate pre-launch): 50-70
- Established company's new product: MAX 25 (not what we're looking for)
- Domain > 1 year old claiming to be "new": MAX 30
- Domain > 3 years old: MAX 15
- Parking/for-sale: MAX 10
- Parent company detected: MAX 20
- Redirect to established site: MAX 15

## Respond in this exact format:

VERDICT: [One of the 6 options above]
CONFIDENCE: [0.0 to 1.0]
SCORE: [0-100, following guidelines above]
REASONING: [2-3 sentences explaining your classification - MUST mention age/company factors if relevant]
KEY_INDICATORS: [Comma-separated list of specific text/signals you noticed]

## Detection Guidelines
**Real startups have:** product descriptions, waitlist forms, team info, demo links, specific AI use case
**Parking pages have:** generic "coming soon", "future home of", "domain registered", no company name
**For-sale domains mention:** "buy this domain", "make offer", Porkbun, Sedo, Dan.com, GoDaddy auctions
**Established companies:** founding year >3 years ago, large user counts (millions), Series B+ funding, "trusted by Fortune 500"

BE SKEPTICAL - when in doubt, assign a LOWER score."""

    def _parse_llm_response(self, response: str, domain: str) -> Dict:
        """Parse Claude's structured response"""
        try:
            lines = response.strip().split('\n')

            verdict = None
            confidence = 0.5
            score = 50
            reasoning = ""
            indicators = []

            for line in lines:
                line = line.strip()

                if line.startswith("VERDICT:"):
                    verdict = line.split(":", 1)[1].strip()
                elif line.startswith("CONFIDENCE:"):
                    confidence = float(line.split(":", 1)[1].strip())
                elif line.startswith("SCORE:"):
                    score = int(line.split(":", 1)[1].strip())
                elif line.startswith("REASONING:"):
                    reasoning = line.split(":", 1)[1].strip()
                elif line.startswith("KEY_INDICATORS:"):
                    indicators_str = line.split(":", 1)[1].strip()
                    indicators = [i.strip() for i in indicators_str.split(",")]

            # Validate verdict
            valid_verdicts = ["REAL_STARTUP", "FOR_SALE", "PARKING", "ESTABLISHED", "REDIRECT", "COMING_SOON"]
            if verdict not in valid_verdicts:
                logger.warning("llm_invalid_verdict", domain=domain, verdict=verdict)
                verdict = "PARKING" if score < 50 else "REAL_STARTUP"

            # Map verdict to is_legitimate_startup
            is_legitimate = verdict in ["REAL_STARTUP", "COMING_SOON"]

            return {
                "verdict": verdict,
                "confidence": confidence,
                "suggested_score": score,
                "reasoning": reasoning,
                "key_indicators": indicators,
                "raw_response": response,
                # Extended format for compatibility with llm_service
                "is_legitimate_startup": is_legitimate,
                "category": "Unknown",  # Will be set by categorization if available
                "red_flags": [],  # Can be extracted from indicators
                "positive_signals": [i for i in indicators if not any(neg in i.lower() for neg in ['no', 'missing', 'lack', 'generic'])]
            }

        except Exception as e:
            logger.error("llm_response_parse_failed", domain=domain, error=str(e))
            return {
                "verdict": "PARKING",
                "confidence": 0.3,
                "suggested_score": 40,
                "reasoning": f"Parse error: {str(e)}",
                "key_indicators": [],
                "raw_response": response,
                # Extended format for compatibility
                "is_legitimate_startup": False,
                "category": "Unknown",
                "red_flags": ["Parse error"],
                "positive_signals": []
            }

    def _calculate_cost(self, usage) -> float:
        """Calculate API cost in USD (legacy format)"""
        return self._calculate_cost_from_dict({
            "input_tokens": getattr(usage, 'input_tokens', 0),
            "output_tokens": getattr(usage, 'output_tokens', 0)
        })

    def _calculate_cost_from_dict(self, usage: dict) -> float:
        """Calculate API cost in USD from dict format"""
        # Claude 3.5 Sonnet pricing (as of 2024)
        # Input: $3.00 per million tokens
        # Output: $15.00 per million tokens

        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)

        input_cost = (input_tokens / 1_000_000) * 3.00
        output_cost = (output_tokens / 1_000_000) * 15.00

        return input_cost + output_cost

    def _fallback_response(self, agent_score: int) -> Dict:
        """Fallback when LLM unavailable"""
        verdict = "PARKING" if agent_score < 50 else "REAL_STARTUP"
        return {
            "verdict": verdict,
            "confidence": 0.0,
            "suggested_score": agent_score,
            "reasoning": "LLM unavailable - using agent score",
            "key_indicators": [],
            "cost_usd": 0.0,
            # Extended format for compatibility
            "is_legitimate_startup": verdict == "REAL_STARTUP",
            "category": "Unknown",
            "red_flags": [],
            "positive_signals": []
        }

    def is_available(self) -> bool:
        """Check if LLM evaluation is available"""
        return self.api_key is not None

    @property
    def enabled(self) -> bool:
        """Alias for is_available() - compatibility with llm_service"""
        return self.is_available()

    def should_use_llm(self, rule_based_score: int, is_parking: bool = False, is_for_sale: bool = False) -> bool:
        """
        Determine if LLM evaluation should be used for this domain.
        Compatibility method from llm_service.

        Args:
            rule_based_score: Score from rule-based agents
            is_parking: Whether domain is detected as parking
            is_for_sale: Whether domain is detected as for-sale

        Returns:
            True if LLM should evaluate this domain
        """
        if not self.is_available():
            return False

        # Don't waste LLM on clear parking/for-sale
        if is_parking or is_for_sale:
            return False

        # Use scoring mode thresholds
        return self.score_min <= rule_based_score <= self.score_max

    def get_status(self) -> Dict:
        """Get LLM service status - for API endpoints"""
        return {
            "enabled": self.is_available(),
            "provider": "anthropic" if self.is_available() else None,
            "model": self.model,
            "scoring_mode": self.scoring_mode,
            "score_range": {
                "min": self.score_min,
                "max": self.score_max
            }
        }

    async def analyze_content_for_enrichment(
        self,
        domain: str,
        title: str,
        meta_description: str,
        content_sample: str,
        page_structure: dict = None
    ) -> Dict:
        """
        Use Claude to analyze website content for enrichment

        Provides deeper analysis for high-quality domains:
        - Business model detection
        - Target audience identification
        - Product/service description
        - Competitive positioning
        - Quality assessment

        Args:
            domain: Domain name
            title: Page title
            meta_description: Meta description
            content_sample: Page content sample
            page_structure: Optional page structure data from MCP

        Returns:
            {
                "business_model": "SaaS" | "API" | "Marketplace" | etc,
                "target_audience": "Developers" | "Enterprise" | etc,
                "product_description": "Brief description...",
                "quality_assessment": "High" | "Medium" | "Low",
                "professionalism_score": 85,
                "key_features": ["feature1", "feature2"],
                "competitive_advantages": ["advantage1"],
                "pricing_model": "Freemium" | "Subscription" | etc,
                "cost_usd": 0.001
            }
        """
        if not self.api_key:
            return self._fallback_enrichment_response()

        prompt = self._build_enrichment_prompt(
            domain, title, meta_description, content_sample, page_structure
        )

        # Retry logic for rate limiting
        max_retries = 3
        retry_delay = 2.0

        for attempt in range(max_retries):
            try:
                logger.info("llm_enrichment_analysis_started", domain=domain, attempt=attempt + 1)

                # Native async via httpx
                response_text, usage = await self._call_anthropic(prompt, max_tokens=600)

                result = self._parse_enrichment_response(response_text, domain)

                cost_usd = self._calculate_cost_from_dict(usage)
                result["cost_usd"] = cost_usd

                logger.info(
                    "llm_enrichment_analysis_completed",
                    domain=domain,
                    business_model=result.get("business_model"),
                    quality=result.get("quality_assessment"),
                    cost_usd=cost_usd
                )

                return result

            except httpx.HTTPStatusError as e:
                status_code = e.response.status_code if hasattr(e, 'response') else 0
                if status_code == 429:
                    if attempt < max_retries - 1:
                        wait_time = retry_delay * (2 ** attempt)
                        logger.warning("llm_enrichment_rate_limited",
                                     domain=domain,
                                     attempt=attempt + 1,
                                     wait=wait_time)
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        logger.error("llm_enrichment_rate_limit_exhausted",
                                   domain=domain,
                                   attempts=max_retries)
                else:
                    logger.error("llm_enrichment_analysis_failed",
                               domain=domain,
                               error=str(e),
                               attempt=attempt + 1)
                return self._fallback_enrichment_response()

            except Exception as e:
                error_str = str(e).lower()
                if 'overloaded' in error_str:
                    if attempt < max_retries - 1:
                        wait_time = retry_delay * (2 ** attempt)
                        await asyncio.sleep(wait_time)
                        continue
                logger.error("llm_enrichment_analysis_failed",
                           domain=domain,
                           error=str(e),
                           attempt=attempt + 1)
                return self._fallback_enrichment_response()

        return self._fallback_enrichment_response()

    def _build_enrichment_prompt(
        self,
        domain: str,
        title: str,
        meta_description: str,
        content_sample: str,
        page_structure: dict
    ) -> str:
        """Build prompt for enrichment analysis"""
        structure_info = ""
        if page_structure:
            structure_info = f"""
- Headings: {page_structure.get('headings', {})}
- Has Navigation: {page_structure.get('has_navigation', 'Unknown')}
- Has Footer: {page_structure.get('has_footer', 'Unknown')}
- Element Counts: {page_structure.get('element_counts', {})}"""

        return f"""You are an expert business analyst evaluating AI startup websites.

Analyze this AI startup's website and extract business intelligence.

**Domain:** {domain}
**Page Title:** {title or "N/A"}
**Meta Description:** {meta_description or "N/A"}
**Content Sample:** {content_sample[:800] if content_sample else "N/A"}
{structure_info}

**Respond in this exact format:**

BUSINESS_MODEL: [SaaS|API|Marketplace|Platform|Tool|Service|Other]
TARGET_AUDIENCE: [Developers|Enterprise|SMB|Consumers|Researchers|Creators|Other]
PRODUCT_DESCRIPTION: [1-2 sentence description of what they do]
QUALITY_ASSESSMENT: [High|Medium|Low]
PROFESSIONALISM_SCORE: [0-100]
KEY_FEATURES: [Feature1, Feature2, Feature3]
COMPETITIVE_ADVANTAGES: [Advantage1, Advantage2]
PRICING_MODEL: [Free|Freemium|Subscription|Usage-Based|Enterprise|Unknown]
CATEGORY: [Chatbot|Analytics|Automation|Creative|Developer Tools|Data|Security|Healthcare|Finance|Education|Other]

**Guidelines:**
- High quality: Professional design, clear value prop, specific features, team info
- Medium quality: Decent design, basic product info, some details missing
- Low quality: Generic, unclear product, minimal content
- Focus on AI-specific business signals"""

    def _parse_enrichment_response(self, response: str, domain: str) -> Dict:
        """Parse enrichment analysis response"""
        try:
            result = {
                "business_model": "Unknown",
                "target_audience": "Unknown",
                "product_description": "",
                "quality_assessment": "Medium",
                "professionalism_score": 50,
                "key_features": [],
                "competitive_advantages": [],
                "pricing_model": "Unknown",
                "category": "Other",
                "raw_response": response
            }

            for line in response.strip().split('\n'):
                line = line.strip()

                if line.startswith("BUSINESS_MODEL:"):
                    result["business_model"] = line.split(":", 1)[1].strip()
                elif line.startswith("TARGET_AUDIENCE:"):
                    result["target_audience"] = line.split(":", 1)[1].strip()
                elif line.startswith("PRODUCT_DESCRIPTION:"):
                    result["product_description"] = line.split(":", 1)[1].strip()
                elif line.startswith("QUALITY_ASSESSMENT:"):
                    result["quality_assessment"] = line.split(":", 1)[1].strip()
                elif line.startswith("PROFESSIONALISM_SCORE:"):
                    try:
                        result["professionalism_score"] = int(line.split(":", 1)[1].strip())
                    except ValueError:
                        pass
                elif line.startswith("KEY_FEATURES:"):
                    features_str = line.split(":", 1)[1].strip()
                    result["key_features"] = [f.strip() for f in features_str.split(",")]
                elif line.startswith("COMPETITIVE_ADVANTAGES:"):
                    advantages_str = line.split(":", 1)[1].strip()
                    result["competitive_advantages"] = [a.strip() for a in advantages_str.split(",")]
                elif line.startswith("PRICING_MODEL:"):
                    result["pricing_model"] = line.split(":", 1)[1].strip()
                elif line.startswith("CATEGORY:"):
                    result["category"] = line.split(":", 1)[1].strip()

            return result

        except Exception as e:
            logger.error("llm_enrichment_parse_failed", domain=domain, error=str(e))
            return self._fallback_enrichment_response()

    def _fallback_enrichment_response(self) -> Dict:
        """Fallback when LLM unavailable for enrichment"""
        return {
            "business_model": "Unknown",
            "target_audience": "Unknown",
            "product_description": "LLM analysis unavailable",
            "quality_assessment": "Unknown",
            "professionalism_score": 50,
            "key_features": [],
            "competitive_advantages": [],
            "pricing_model": "Unknown",
            "category": "Other",
            "cost_usd": 0.0
        }


# ============================================================================
# SINGLETON INSTANCE - Use this for compatibility with llm_service imports
# ============================================================================

# Global singleton instance
llm_evaluator = LLMEvaluator()

# Alias for backward compatibility with llm_service imports
# Usage: from services.llm_evaluator import llm_service
llm_service = llm_evaluator
