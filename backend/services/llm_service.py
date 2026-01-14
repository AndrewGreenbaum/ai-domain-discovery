"""
LLM Service - AI-powered domain analysis using OpenAI or Anthropic
"""
import os
import json
import httpx
from typing import Optional, Dict, Any
from utils.logger import logger
from config.settings import settings  # Load .env via pydantic


class LLMService:
    """
    Service for LLM-powered domain analysis.

    Uses:
    1. Uncertain domain evaluation - When rule-based scoring is ambiguous
    2. Content classification - Understanding what the startup does
    3. Quality/legitimacy assessment - Is this a real startup?
    """

    # Default score thresholds (will be overridden by llm_scoring_mode)
    # EXPANDED: Was 40-70, now 35-85 to catch suspicious high-scoring old domains
    UNCERTAIN_SCORE_MIN = 35
    UNCERTAIN_SCORE_MAX = 85

    # Scoring mode presets - EXPANDED RANGES
    # We expanded because established companies (like botchat.ai) were getting
    # high scores (80+) without LLM evaluation
    SCORING_MODES = {
        "conservative": (35, 85),   # Was (40, 70) - catch more edge cases
        "moderate": (30, 90),       # Was (35, 75) - expanded
        "aggressive": (0, 100),     # ALL live domains get LLM
    }

    def __init__(self):
        # Use settings (which loads .env) for Anthropic key, fall back to os.getenv
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.anthropic_api_key = settings.anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")
        self.provider = self._detect_provider()
        # Set model based on provider
        if self.provider == "anthropic":
            self.model = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
        else:
            self.model = os.getenv("LLM_MODEL", "gpt-4o-mini")
        self.enabled = self.provider is not None

        # Apply scoring mode from settings
        scoring_mode = getattr(settings, 'llm_scoring_mode', 'conservative')
        if scoring_mode in self.SCORING_MODES:
            self.UNCERTAIN_SCORE_MIN, self.UNCERTAIN_SCORE_MAX = self.SCORING_MODES[scoring_mode]
        logger.info("llm_scoring_mode_applied",
                    mode=scoring_mode,
                    min_score=self.UNCERTAIN_SCORE_MIN,
                    max_score=self.UNCERTAIN_SCORE_MAX)

        if self.enabled:
            logger.info("llm_service_initialized", provider=self.provider, model=self.model)
        else:
            logger.warning("llm_service_disabled", reason="No API key found (OPENAI_API_KEY or ANTHROPIC_API_KEY)")

    def _detect_provider(self) -> Optional[str]:
        """Detect which LLM provider to use based on available API keys"""
        if self.openai_api_key:
            return "openai"
        elif self.anthropic_api_key:
            return "anthropic"
        return None

    async def evaluate_domain(
        self,
        domain: str,
        title: str,
        description: str,
        content_sample: str,
        rule_based_score: int,
        validation_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Comprehensive LLM evaluation of a domain.

        Returns:
            {
                "is_legitimate_startup": bool,
                "confidence": float (0-1),
                "category": str (e.g., "AI SaaS", "Developer Tools"),
                "business_model": str (e.g., "B2B SaaS", "Marketplace"),
                "target_audience": str,
                "product_description": str,
                "quality_assessment": str ("high", "medium", "low"),
                "suggested_score": int (0-100),
                "reasoning": str,
                "red_flags": list[str],
                "positive_signals": list[str]
            }
        """
        if not self.enabled:
            logger.debug("llm_evaluation_skipped", domain=domain, reason="LLM not enabled")
            return None

        prompt = self._build_evaluation_prompt(
            domain, title, description, content_sample, rule_based_score, validation_data
        )

        try:
            if self.provider == "openai":
                response = await self._call_openai(prompt)
            else:
                response = await self._call_anthropic(prompt)

            result = self._parse_response(response)

            logger.info(
                "llm_evaluation_complete",
                domain=domain,
                is_legitimate=result.get("is_legitimate_startup"),
                category=result.get("category"),
                suggested_score=result.get("suggested_score"),
                confidence=result.get("confidence")
            )

            return result

        except Exception as e:
            logger.error("llm_evaluation_failed", domain=domain, error=str(e))
            return None

    async def classify_content(
        self,
        domain: str,
        title: str,
        content_sample: str
    ) -> Optional[Dict[str, Any]]:
        """
        Quick content classification - what does this startup do?

        Returns:
            {
                "category": str,
                "subcategory": str,
                "business_model": str,
                "target_audience": str,
                "key_features": list[str],
                "confidence": float
            }
        """
        if not self.enabled:
            return None

        prompt = f"""Analyze this website and classify the business:

Domain: {domain}
Title: {title}
Content: {content_sample[:1500]}

Respond in JSON format:
{{
    "category": "main category (e.g., AI/ML, Developer Tools, Marketing, Sales, HR, Finance, etc.)",
    "subcategory": "specific subcategory",
    "business_model": "B2B SaaS, B2C, Marketplace, API, etc.",
    "target_audience": "who is the target customer",
    "key_features": ["feature1", "feature2", "feature3"],
    "one_liner": "one sentence description of what they do",
    "confidence": 0.0-1.0
}}"""

        try:
            if self.provider == "openai":
                response = await self._call_openai(prompt, max_tokens=500)
            else:
                response = await self._call_anthropic(prompt, max_tokens=500)

            return self._parse_response(response)

        except Exception as e:
            logger.error("llm_classification_failed", domain=domain, error=str(e))
            return None

    async def assess_legitimacy(
        self,
        domain: str,
        title: str,
        content_sample: str,
        has_ssl: bool,
        is_redirect: bool,
        registrar: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        """
        Quick legitimacy check - is this a real startup or spam/parking?

        Returns:
            {
                "is_legitimate": bool,
                "confidence": float,
                "verdict": str ("legitimate_startup", "coming_soon", "parking", "spam", "established_company"),
                "reasoning": str,
                "red_flags": list[str]
            }
        """
        if not self.enabled:
            return None

        prompt = f"""Determine if this is a legitimate new startup or not:

Domain: {domain}
Title: {title}
Content Sample: {content_sample[:1000]}
Has SSL: {has_ssl}
Is Redirect: {is_redirect}
Registrar: {registrar or "Unknown"}

Classify as one of:
- legitimate_startup: Real new company with original product/service
- coming_soon: Legitimate startup in pre-launch phase
- parking: Domain parking page or placeholder
- spam: Spam, scam, or low-quality site
- established_company: Not new - existing company's new domain

Respond in JSON:
{{
    "is_legitimate": true/false,
    "confidence": 0.0-1.0,
    "verdict": "one of the categories above",
    "reasoning": "brief explanation",
    "red_flags": ["any concerning signals"],
    "positive_signals": ["any good signals"]
}}"""

        try:
            if self.provider == "openai":
                response = await self._call_openai(prompt, max_tokens=400)
            else:
                response = await self._call_anthropic(prompt, max_tokens=400)

            return self._parse_response(response)

        except Exception as e:
            logger.error("llm_legitimacy_check_failed", domain=domain, error=str(e))
            return None

    def _build_evaluation_prompt(
        self,
        domain: str,
        title: str,
        description: str,
        content_sample: str,
        rule_based_score: int,
        validation_data: Dict[str, Any]
    ) -> str:
        """Build the comprehensive evaluation prompt with domain age and company context"""

        # Extract critical age/company data
        domain_age_days = validation_data.get('domain_age_days')
        domain_created_date = validation_data.get('domain_created_date')
        parent_company = validation_data.get('parent_company')
        company_age = validation_data.get('company_age')
        established_signals = validation_data.get('established_signals', [])

        # Format domain age section
        if domain_age_days is not None:
            age_info = f"- Domain Age: {domain_age_days} days (registered: {domain_created_date or 'Unknown'})"
            age_warning = ""
            if domain_age_days > 365 * 3:
                age_warning = "\n  ⚠️ CRITICAL: Domain is over 3 YEARS old - very unlikely to be a new startup!"
            elif domain_age_days > 365:
                age_warning = "\n  ⚠️ WARNING: Domain is over 1 YEAR old - suspicious for 'new' startup"
            elif domain_age_days > 90:
                age_warning = "\n  ⚠️ NOTE: Domain is over 90 days old"
            age_info += age_warning
        else:
            age_info = "- Domain Age: UNKNOWN (WHOIS lookup failed - be suspicious)"

        # Format parent company section
        if parent_company:
            company_info = f"\n- ⚠️ PARENT COMPANY DETECTED: {parent_company}"
        else:
            company_info = "\n- Parent Company: None detected"

        if company_age:
            company_info += f"\n- Company Age: {company_age} years"
            if company_age > 3:
                company_info += " ⚠️ (ESTABLISHED - not a new startup!)"

        if established_signals:
            company_info += f"\n- ⚠️ ESTABLISHED SIGNALS: {', '.join(established_signals)}"

        return f"""You are an expert startup analyst. Your job is to identify GENUINELY NEW AI startups (< 1 year old).

## CRITICAL CONTEXT - READ CAREFULLY
You're evaluating domains from Certificate Transparency logs. Many established companies register NEW SSL certificates for:
- Product launches under new domains
- Marketing campaigns
- Rebrands or acquisitions
- Domain speculation/squatting

A new SSL certificate does NOT mean a new company!

## Domain Information
- Domain: {domain}
- Title: {title}
- Meta Description: {description}
- Rule-based Score: {rule_based_score}/100

## Age & Company Analysis (CRITICAL!)
{age_info}{company_info}

## Validation Data
- Is Live: {validation_data.get('is_live', 'Unknown')}
- HTTP Status: {validation_data.get('http_status_code', 'Unknown')}
- Has SSL: {validation_data.get('has_ssl', False)}
- Is Parking: {validation_data.get('is_parking', False)}
- Is For Sale: {validation_data.get('is_for_sale', False)}
- Is Redirect: {validation_data.get('is_redirect', False)}
- Registrar: {validation_data.get('registrar', 'Unknown')}

## Page Content Sample
{content_sample[:2000]}

## Your Task - BE SKEPTICAL!
1. Is this a GENUINELY NEW AI startup (founded < 1 year ago)?
2. Or is it an established company with a new domain?
3. Does the content suggest a brand new venture or an extension of existing business?
4. Are there any signals of being backed by a larger company?

SCORING GUIDELINES:
- New startup (< 1 year, no parent company): 60-95 based on quality
- Coming soon (legitimate pre-launch): 50-70
- Established company's new product: MAX 25 (not what we're looking for)
- Domain > 1 year old claiming to be "new": MAX 30
- Domain > 3 years old: MAX 15
- Parking/for-sale: MAX 10
- Parent company detected: MAX 20

Respond in JSON format:
{{
    "is_legitimate_startup": true/false,
    "is_genuinely_new": true/false,
    "confidence": 0.0-1.0,
    "estimated_company_age": "< 1 year | 1-3 years | 3+ years | unknown",
    "category": "primary category",
    "subcategory": "specific niche",
    "business_model": "B2B SaaS, B2C, API, etc.",
    "target_audience": "who they're selling to",
    "product_description": "one paragraph about what they do",
    "quality_assessment": "high/medium/low",
    "suggested_score": 0-100,
    "score_reasoning": "why you suggest this score - MUST mention age/company factors",
    "red_flags": ["list of concerns - include age issues"],
    "positive_signals": ["list of good signs"],
    "verdict": "brief final assessment"
}}"""

    async def _call_openai(self, prompt: str, max_tokens: int = 1000) -> str:
        """Call OpenAI API"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.openai_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": "You are an expert startup analyst. Always respond in valid JSON."},
                        {"role": "user", "content": prompt}
                    ],
                    "max_tokens": max_tokens,
                    "temperature": 0.3  # Lower temperature for more consistent analysis
                }
            )

            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]

    async def _call_anthropic(self, prompt: str, max_tokens: int = 1000) -> str:
        """Call Anthropic API"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.anthropic_api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.model,
                    "max_tokens": max_tokens,
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                    "system": "You are an expert startup analyst. Always respond in valid JSON."
                }
            )

            response.raise_for_status()
            data = response.json()
            return data["content"][0]["text"]

    def _parse_response(self, response: str) -> Dict[str, Any]:
        """Parse LLM response, handling markdown code blocks"""
        # Remove markdown code blocks if present
        text = response.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]

        return json.loads(text.strip())

    def should_use_llm(self, rule_based_score: int, is_parking: bool, is_for_sale: bool) -> bool:
        """
        Determine if we should use LLM for this domain.

        Use LLM when:
        1. Score is in "uncertain" range (40-70)
        2. Not clearly parking or for-sale
        3. LLM is enabled
        """
        if not self.enabled:
            return False

        # Don't waste LLM on clear parking/for-sale
        if is_parking or is_for_sale:
            return False

        # Use LLM for uncertain scores
        return self.UNCERTAIN_SCORE_MIN <= rule_based_score <= self.UNCERTAIN_SCORE_MAX


# Singleton instance
llm_service = LLMService()
