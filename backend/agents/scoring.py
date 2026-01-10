"""SCORING_AGENT - Adaptive quality scoring with category-specific weights + LLM"""
from typing import Dict, Tuple, Optional, Any
from models.schemas import ValidationResult, ScoringResult
from utils.logger import logger


class ScoringAgent:
    """Agent responsible for adaptive domain quality scoring with LLM enhancement"""

    def __init__(self):
        # Lazy-load dependencies to prevent circular imports
        # InvestigatorAgent and llm_service are loaded on first use
        self._investigator = None
        self._llm_service = None

        # LLM evaluation results storage (for returning to caller)
        self.last_llm_evaluation: Optional[Dict[str, Any]] = None

    @property
    def investigator(self):
        """Lazy-load InvestigatorAgent to prevent circular import"""
        if self._investigator is None:
            from agents.investigator import InvestigatorAgent
            self._investigator = InvestigatorAgent()
        return self._investigator

    @property
    def llm_service(self):
        """Lazy-load llm_service to prevent circular import"""
        if self._llm_service is None:
            from services.llm_service import llm_service
            self._llm_service = llm_service
        return self._llm_service

    # Category-specific weight profiles (class attribute)
    category_weights = {
        "LAUNCHING_NOW": {
            "domain_quality": 0.15,
            "launch_readiness": 0.35,  # Higher for launched sites
            "content_originality": 0.25,
            "professional_setup": 0.15,
            "early_signals": 0.10,
        },
        "COMING_SOON": {
            "domain_quality": 0.25,
            "launch_readiness": 0.15,
            "content_originality": 0.10,
            "professional_setup": 0.20,
            "early_signals": 0.30,  # Higher for pre-launch signals
        },
        "JUST_REGISTERED": {
            "domain_quality": 0.40,  # Domain name is everything
            "launch_readiness": 0.10,
            "content_originality": 0.05,
            "professional_setup": 0.25,
            "early_signals": 0.20,
        },
        "STEALTH_MODE": {
            "domain_quality": 0.30,
            "launch_readiness": 0.20,
            "content_originality": 0.15,
            "professional_setup": 0.25,
            "early_signals": 0.10,
        },
        "INSTANT_REJECT": {  # Parking/for-sale - heavily penalize
            "domain_quality": 0.10,  # Name doesn't matter
            "launch_readiness": 0.60,  # This will be near-zero for parking
            "content_originality": 0.10,  # No original content
            "professional_setup": 0.10,
            "early_signals": 0.10,
        },
        "DEFAULT": {  # Fallback
            "domain_quality": 0.20,
            "launch_readiness": 0.25,
            "content_originality": 0.20,
            "professional_setup": 0.20,
            "early_signals": 0.15,
        }
    }

    # Premium keywords (class attribute)
    premium_keywords = [
        "ai", "chat", "code", "data", "learn", "smart",
        "auto", "fast", "easy", "quick", "best", "top",
        "pro", "plus", "max", "ultra", "super", "agent"
    ]

    async def calculate_scores(self, domain: str, validation: ValidationResult) -> ScoringResult:
        """
        Calculate all scoring components with confidence scoring

        Args:
            domain: Domain name
            validation: Validation result

        Returns:
            ScoringResult with all scores and confidence levels
        """
        logger.info("adaptive_scoring_started", domain=domain)

        # Calculate individual scores with confidence
        domain_quality, dq_conf = self.score_domain_quality(domain)
        launch_readiness, lr_conf = self.score_launch_readiness(validation)
        content_originality, co_conf = self.score_content_originality(validation)
        professional_setup, ps_conf = self.score_professional_setup(validation)
        early_signals, es_conf = self.score_early_signals(validation)

        # Build score dict with confidence
        scores = {
            "domain_quality": (domain_quality, dq_conf),
            "launch_readiness": (launch_readiness, lr_conf),
            "content_originality": (content_originality, co_conf),
            "professional_setup": (professional_setup, ps_conf),
            "early_signals": (early_signals, es_conf),
        }

        # Determine preliminary category for weight selection
        prelim_category = self._preliminary_categorize(validation, domain_quality)

        # Calculate adaptive weighted final score
        final_score = self.calculate_adaptive_final_score(scores, prelim_category)

        # CRITICAL: Phase 0 - UNVALIDATED DOMAIN PENALTY
        # If domain is not live and we have NO content data, it's suspicious
        # Cap at 35/100 to prevent scoring domains we can't actually verify
        if not validation.is_live and not validation.title and not validation.content_sample:
            original_score = final_score
            final_score = min(final_score, 35)
            logger.warning(
                "unvalidated_domain_penalty",
                domain=domain,
                original_score=original_score,
                penalized_score=final_score,
                reason="No validation data - domain not reachable"
            )

        # CRITICAL: Phase 0.5 - FOR-SALE & PARKING PENALTY
        # Domains for sale or parked are NOT startups - harsh penalty
        # Cap score at 35/100 maximum (even lower than unvalidated)
        if validation.is_for_sale or validation.is_parking:
            original_score = final_score
            final_score = min(final_score, 35)
            penalty_reason = "FOR SALE" if validation.is_for_sale else "PARKING"
            prelim_category = "INSTANT_REJECT"
            logger.warning(
                "for_sale_parking_penalty_applied",
                domain=domain,
                original_score=original_score,
                penalized_score=final_score,
                reason=penalty_reason,
                is_for_sale=validation.is_for_sale,
                is_parking=validation.is_parking
            )

        # CRITICAL: Phase 1 - HARSH REDIRECT PENALTY
        # If domain redirects to another domain, it's an established company
        # Cap score at 20/100 maximum
        if validation.is_redirect:
            original_score = final_score
            final_score = min(final_score, 20)
            prelim_category = "REDIRECT_ESTABLISHED"
            logger.warning(
                "redirect_penalty_applied",
                domain=domain,
                original_score=original_score,
                penalized_score=final_score,
                redirect_to=validation.final_domain
            )

        # =====================================================================
        # PHASE 2 ANALYSIS - Run BEFORE LLM to pass context
        # Extract parent company, company age, established signals FIRST
        # =====================================================================
        parent_company = None
        company_age = None
        established_signals = []
        is_established = False

        if not validation.is_redirect and validation.is_live:
            # Get page content for analysis
            page_content = validation.content_sample or ""
            title = validation.title or ""

            # Check for parent company
            parent_company = self.investigator.extract_parent_company(page_content, title)

            # Check for established company signals
            is_established, established_signals = self.investigator.detect_established_signals(page_content)

            # Check company age from content
            founding_year = self.investigator.extract_founding_year(page_content)
            company_age = self.investigator.calculate_company_age(founded_year=founding_year)

            logger.info(
                "phase2_analysis_complete",
                domain=domain,
                parent_company=parent_company,
                company_age=company_age,
                is_established=is_established,
                signals=established_signals[:3] if established_signals else []
            )

        # =====================================================================
        # CRITICAL: Phase 1.5 - GRANULAR DOMAIN AGE PENALTIES (WHOIS)
        # Different penalty levels based on how old the domain is
        # =====================================================================
        domain_age_penalty_applied = False
        whois_failed = validation.domain_age_days is None

        if validation.domain_age_days is not None:
            age_days = validation.domain_age_days

            # TIER 1: Domain > 3 years old - MAX 10 (very unlikely new startup)
            if age_days > 365 * 3:
                original_score = final_score
                final_score = min(final_score, 10)
                prelim_category = "PRE_EXISTING_DOMAIN"
                domain_age_penalty_applied = True
                logger.warning(
                    "domain_age_penalty_tier1",
                    domain=domain,
                    domain_age_days=age_days,
                    created_date=validation.domain_created_date,
                    original_score=original_score,
                    penalized_score=final_score,
                    reason=f"Domain is {age_days // 365} YEARS old (> 3 years)"
                )

            # TIER 2: Domain > 1 year old - MAX 25 (suspicious for "new" startup)
            elif age_days > 365:
                original_score = final_score
                final_score = min(final_score, 25)
                prelim_category = "PRE_EXISTING_DOMAIN"
                domain_age_penalty_applied = True
                logger.warning(
                    "domain_age_penalty_tier2",
                    domain=domain,
                    domain_age_days=age_days,
                    created_date=validation.domain_created_date,
                    original_score=original_score,
                    penalized_score=final_score,
                    reason=f"Domain is {age_days // 365} year(s) old (> 1 year)"
                )

            # TIER 3: Domain > 90 days old - MAX 40 (likely not brand new)
            elif age_days > 90:
                original_score = final_score
                final_score = min(final_score, 40)
                domain_age_penalty_applied = True
                logger.info(
                    "domain_age_penalty_tier3",
                    domain=domain,
                    domain_age_days=age_days,
                    created_date=validation.domain_created_date,
                    original_score=original_score,
                    penalized_score=final_score,
                    reason=f"Domain is {age_days} days old (> 90 days)"
                )
        else:
            # WHOIS FAILED - Apply soft penalty (can't verify domain age)
            # Only apply if score is suspiciously high
            if final_score > 70:
                original_score = final_score
                final_score = min(final_score, 65)  # Cap at 65 when age unknown
                logger.warning(
                    "whois_failed_soft_penalty",
                    domain=domain,
                    original_score=original_score,
                    penalized_score=final_score,
                    reason="WHOIS lookup failed - cannot verify domain age"
                )

        # =====================================================================
        # CRITICAL: Phase 2 - PARENT COMPANY & ESTABLISHED COMPANY PENALTY
        # Apply penalties based on Phase 2 analysis done above
        # =====================================================================
        if not validation.is_redirect and validation.is_live:
            should_penalize = False
            penalty_reason = ""

            if parent_company:
                should_penalize = True
                penalty_reason = f"Owned by {parent_company}"
                prelim_category = "PRODUCT_SUBDOMAIN"

            if company_age and company_age > 3:
                should_penalize = True
                penalty_reason = f"Company age: {company_age} years (> 3 years threshold)"
                prelim_category = "ESTABLISHED_COMPANY"

            if is_established:
                should_penalize = True
                penalty_reason = f"Established signals: {', '.join(established_signals)}"
                prelim_category = "ESTABLISHED_COMPANY"

            if should_penalize:
                original_score = final_score
                final_score = min(final_score, 20)
                logger.warning(
                    "established_company_penalty_applied",
                    domain=domain,
                    original_score=original_score,
                    penalized_score=final_score,
                    reason=penalty_reason,
                    parent_company=parent_company,
                    company_age=company_age,
                    signals=established_signals
                )

        # =================================================================
        # LLM ENHANCEMENT: For uncertain domains, use AI for better scoring
        # ENHANCED: Also force LLM for suspicious high-scoring old domains
        # =================================================================
        self.last_llm_evaluation = None
        llm_adjusted_score = None
        llm_category = None
        llm_classification = None

        # Check if we should FORCE LLM evaluation for suspicious cases
        # Suspicious = High score (>75) BUT domain is old (>365 days) or WHOIS failed
        force_llm_evaluation = False
        if final_score > 75 and validation.is_live:
            # Force LLM if domain is old (>1 year) - something fishy
            if validation.domain_age_days is not None and validation.domain_age_days > 365:
                force_llm_evaluation = True
                logger.info(
                    "forcing_llm_suspicious_old_domain",
                    domain=domain,
                    score=final_score,
                    domain_age_days=validation.domain_age_days,
                    reason="High score but old domain"
                )
            # Force LLM if WHOIS failed and score is high - can't verify age
            elif whois_failed:
                force_llm_evaluation = True
                logger.info(
                    "forcing_llm_whois_failed",
                    domain=domain,
                    score=final_score,
                    reason="High score but WHOIS failed"
                )
            # Force LLM if parent company detected but score still high
            elif parent_company:
                force_llm_evaluation = True
                logger.info(
                    "forcing_llm_parent_company",
                    domain=domain,
                    score=final_score,
                    parent_company=parent_company,
                    reason="Parent company detected but score still high"
                )

        # Expanded LLM trigger: 35-85 instead of 40-70, OR forced evaluation
        should_use_llm = (
            force_llm_evaluation or
            (self.llm_service.should_use_llm(final_score, validation.is_parking, validation.is_for_sale)
             and validation.is_live and validation.content_sample)
        )

        if should_use_llm:
            logger.info("llm_evaluation_starting", domain=domain, rule_based_score=final_score, forced=force_llm_evaluation)

            try:
                # Build ENHANCED validation dict for LLM with Phase 2 data
                validation_dict = {
                    "is_live": validation.is_live,
                    "http_status_code": validation.http_status_code,
                    "has_ssl": validation.has_ssl,
                    "is_parking": validation.is_parking,
                    "is_for_sale": validation.is_for_sale,
                    "is_redirect": validation.is_redirect,
                    "registrar": validation.registrar,
                    # Domain age data
                    "domain_age_days": validation.domain_age_days,
                    "domain_created_date": str(validation.domain_created_date) if validation.domain_created_date else None,
                    # Phase 2 data - CRITICAL for LLM to make good decisions
                    "parent_company": parent_company,
                    "company_age": company_age,
                    "established_signals": established_signals,
                }

                # Get comprehensive LLM evaluation
                llm_result = await self.llm_service.evaluate_domain(
                    domain=domain,
                    title=validation.title or "",
                    description=validation.meta_description or "",
                    content_sample=validation.content_sample or "",
                    rule_based_score=final_score,
                    validation_data=validation_dict
                )

                if llm_result:
                    self.last_llm_evaluation = llm_result

                    # Get LLM suggested score
                    suggested_score = llm_result.get("suggested_score")
                    llm_confidence = llm_result.get("confidence", 0)
                    is_legitimate = llm_result.get("is_legitimate_startup", True)

                    # Only adjust score if LLM is confident
                    if suggested_score is not None and llm_confidence >= 0.7:
                        # If LLM says NOT legitimate with high confidence, penalize
                        if not is_legitimate and llm_confidence >= 0.8:
                            original_score = final_score
                            final_score = min(final_score, 30)
                            llm_adjusted_score = final_score
                            logger.warning(
                                "llm_illegitimate_penalty",
                                domain=domain,
                                original_score=original_score,
                                llm_score=suggested_score,
                                final_score=final_score,
                                confidence=llm_confidence,
                                reasoning=llm_result.get("reasoning", "")[:200]
                            )
                        else:
                            # Blend rule-based and LLM scores (weighted by confidence)
                            # Higher confidence = more weight to LLM score
                            blend_weight = min(llm_confidence, 0.6)  # Max 60% LLM influence
                            blended_score = (1 - blend_weight) * final_score + blend_weight * suggested_score
                            llm_adjusted_score = int(round(blended_score))

                            # Only adjust if there's a meaningful difference
                            if abs(llm_adjusted_score - final_score) >= 5:
                                original_score = final_score
                                final_score = llm_adjusted_score
                                logger.info(
                                    "llm_score_adjustment",
                                    domain=domain,
                                    original_score=original_score,
                                    llm_suggested=suggested_score,
                                    blended_score=final_score,
                                    confidence=llm_confidence,
                                    blend_weight=blend_weight
                                )

                    # Store LLM classification
                    llm_category = llm_result.get("category")
                    llm_classification = {
                        "category": llm_result.get("category"),
                        "subcategory": llm_result.get("subcategory"),
                        "business_model": llm_result.get("business_model"),
                        "target_audience": llm_result.get("target_audience"),
                        "product_description": llm_result.get("product_description"),
                        "quality_assessment": llm_result.get("quality_assessment"),
                        "red_flags": llm_result.get("red_flags", []),
                        "positive_signals": llm_result.get("positive_signals", []),
                    }

                    logger.info(
                        "llm_evaluation_complete",
                        domain=domain,
                        is_legitimate=is_legitimate,
                        category=llm_category,
                        confidence=llm_confidence,
                        final_score=final_score
                    )

            except Exception as e:
                logger.error("llm_evaluation_error", domain=domain, error=str(e))
                # Continue with rule-based score on LLM failure

        result = ScoringResult(
            domain=domain,
            quality_score=final_score,
            domain_quality_score=domain_quality,
            launch_readiness_score=launch_readiness,
            content_originality_score=content_originality,
            professional_setup_score=professional_setup,
            early_signals_score=early_signals,
        )

        logger.info(
            "adaptive_scoring_completed",
            domain=domain,
            quality_score=final_score,
            category=prelim_category,
            avg_confidence=sum(c for _, c in scores.values()) / len(scores),
            is_redirect=validation.is_redirect
        )

        return result

    def score_domain_quality(self, domain: str) -> Tuple[float, float]:
        """
        Score domain name quality (0-100) with confidence

        Returns:
            (score, confidence)
        """
        score = 50.0
        confidence = 1.0  # Always have domain name

        # Remove .ai extension
        name = domain.replace('.ai', '')

        # Length scoring (shorter is better)
        if len(name) <= 5:
            score += 30
        elif len(name) <= 8:
            score += 20
        elif len(name) <= 12:
            score += 10
        else:
            score -= (len(name) - 12) * 2

        # Premium keyword bonus
        if any(keyword in name.lower() for keyword in self.premium_keywords):
            score += 15

        # Penalties
        if '-' in name:
            score -= 10
        if any(char.isdigit() for char in name):
            score -= 10

        # Dictionary word bonus
        if name.lower() in self.premium_keywords:
            score += 20

        return max(0, min(100, score)), confidence

    def score_launch_readiness(self, validation: ValidationResult) -> Tuple[float, float]:
        """Score with confidence based on data availability"""
        # CRITICAL: If domain is not live, it's worthless for startup discovery
        if not validation.is_live:
            return 0.0, 1.0  # Confident it's not live

        # CRITICAL: Parking and for-sale pages get near-zero scores
        if validation.is_parking or validation.is_for_sale:
            return 5.0, 1.0  # Even lower - these are useless

        score = 40.0
        confidence = 0.7  # Base confidence when live

        # Has title
        if validation.title:
            score += 20
            confidence += 0.1

        # Has meta description
        if validation.meta_description:
            score += 15
            confidence += 0.1

        # Has substantial content
        if validation.content_sample and len(validation.content_sample) > 100:
            score += 25
            confidence += 0.1

        return min(100, score), min(1.0, confidence)

    def score_content_originality(self, validation: ValidationResult) -> Tuple[float, float]:
        """Score content uniqueness with confidence"""
        if not validation.is_live:
            return 0.0, 0.3  # Low confidence, no data

        if validation.is_parking:
            return 0.0, 1.0  # Confident it's not original

        score = 30.0
        confidence = 0.5

        # Check for template indicators
        if validation.title:
            confidence += 0.2
            template_phrases = ['coming soon', 'under construction', 'default page', 'welcome']
            if not any(phrase in validation.title.lower() for phrase in template_phrases):
                score += 25

        # Unique description
        if validation.meta_description and len(validation.meta_description) > 50:
            score += 20
            confidence += 0.2

        # Substantial content
        if validation.content_sample and len(validation.content_sample) > 150:
            score += 25
            confidence += 0.1

        return min(100, score), min(1.0, confidence)

    def score_professional_setup(self, validation: ValidationResult) -> Tuple[float, float]:
        """Score technical setup quality with confidence"""
        score = 0.0
        confidence = 1.0  # Can always assess technical setup

        # SSL/HTTPS
        if validation.has_ssl:
            score += 30

        # Valid HTTP status
        if validation.http_status_code and 200 <= validation.http_status_code < 300:
            score += 30

        # Proper HTML structure
        if validation.title and validation.meta_description:
            score += 20

        # Is live
        if validation.is_live:
            score += 20

        return min(100, score), confidence

    def score_early_signals(self, validation: ValidationResult) -> Tuple[float, float]:
        """Score early startup signals with confidence"""
        if not validation.is_live:
            return 0.0, 0.4  # Low confidence without content

        score = 30.0
        confidence = 0.6

        text = f"{validation.title} {validation.meta_description} {validation.content_sample}".lower()

        if not text.strip():
            return 0.0, 0.3

        confidence = 0.8  # Have text to analyze

        # Positive signals
        positive_signals = [
            'waitlist', 'early access', 'beta', 'sign up',
            'join', 'coming soon', 'launching', 'notify',
            'product', 'platform', 'solution', 'service'
        ]

        matches = sum(1 for signal in positive_signals if signal in text)
        score += min(50, matches * 10)

        # Email/social presence
        if any(term in text for term in ['@', 'email', 'twitter', 'linkedin']):
            score += 20
            confidence += 0.1

        return min(100, score), min(1.0, confidence)

    def calculate_adaptive_final_score(
        self,
        scores: Dict[str, Tuple[float, float]],
        category: str
    ) -> int:
        """
        Calculate weighted final score with adaptive weight redistribution

        Args:
            scores: Dict of {component: (score, confidence)}
            category: Domain category for weight selection

        Returns:
            Final quality score (0-100)
        """
        # Get category-specific weights
        weights = self.category_weights.get(category, self.category_weights["DEFAULT"])

        # Identify low-confidence components (confidence < 0.5)
        low_confidence_components = [
            comp for comp, (_, conf) in scores.items() if conf < 0.5
        ]

        # Redistribute weights from low-confidence components
        if low_confidence_components:
            weights = self._redistribute_weights(weights, low_confidence_components)

        # Calculate weighted score
        final = sum(
            scores[component][0] * weight
            for component, weight in weights.items()
        )

        # Apply confidence penalty
        avg_confidence = sum(conf for _, conf in scores.values()) / len(scores)
        confidence_factor = 0.7 + (0.3 * avg_confidence)  # 0.7 to 1.0

        final = final * confidence_factor

        return int(round(final))

    def _redistribute_weights(
        self,
        weights: Dict[str, float],
        low_confidence: list
    ) -> Dict[str, float]:
        """
        Redistribute weights from low-confidence components

        Args:
            weights: Original weights
            low_confidence: List of low-confidence component names

        Returns:
            Adjusted weights (still sum to 1.0)
        """
        new_weights = weights.copy()

        # Total weight to redistribute
        redistribute_amount = sum(weights[comp] for comp in low_confidence)

        # Set low-confidence weights to half
        for comp in low_confidence:
            new_weights[comp] = weights[comp] * 0.5

        # Distribute remaining weight to high-confidence components
        high_confidence = [c for c in weights if c not in low_confidence]

        if high_confidence:
            bonus_per_component = (redistribute_amount * 0.5) / len(high_confidence)
            for comp in high_confidence:
                new_weights[comp] += bonus_per_component

        # Normalize to ensure sum = 1.0
        total = sum(new_weights.values())
        new_weights = {k: v / total for k, v in new_weights.items()}

        logger.debug("weights_redistributed", original=weights, new=new_weights)

        return new_weights

    def _preliminary_categorize(self, validation: ValidationResult, domain_score: float) -> str:
        """Preliminary categorization for weight selection"""
        if validation.is_for_sale or validation.is_parking:
            return "INSTANT_REJECT"

        if not validation.is_live:
            return "JUST_REGISTERED"

        # Check for coming soon
        if validation.title:
            text = validation.title.lower()
            if any(term in text for term in ['coming soon', 'launching', 'waitlist']):
                return "COMING_SOON"

        # High domain quality + live = likely launching
        if domain_score >= 70 and validation.is_live:
            return "LAUNCHING_NOW"

        # Minimal content but professional
        if validation.has_ssl and validation.is_live:
            return "STEALTH_MODE"

        return "DEFAULT"

    def categorize_domain(self, score: int, validation: ValidationResult) -> str:
        """Final categorization based on score and validation"""
        if validation.is_for_sale:
            return "INSTANT_REJECT"

        if validation.is_parking:
            return "INSTANT_REJECT"

        if not validation.is_live:
            return "JUST_REGISTERED"

        # Check for coming soon
        if validation.title:
            text = validation.title.lower()
            if any(term in text for term in ['coming soon', 'launching', 'waitlist']):
                return "COMING_SOON"

        # Score-based with adaptive thresholds
        if score >= 80:
            return "LAUNCHING_NOW"
        elif score >= 65:
            return "STEALTH_MODE"
        elif score >= 45:
            return "SOFT_LAUNCH"
        else:
            return "JUST_REGISTERED"
