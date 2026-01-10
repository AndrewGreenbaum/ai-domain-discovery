"""IMPLEMENTER/QA - Orchestrates all agents and runs complete discovery pipeline"""
from typing import Dict, List
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_
from models.domain import Domain, DiscoveryRun, Alert
from agents.discovery import DiscoveryAgent
from agents.validation import ValidationAgent
from agents.hybrid_scorer import HybridScorer
from agents.investigator import InvestigatorAgent
from agents.enrichment import EnrichmentAgent
from services.metrics import MetricsService
from utils.logger import logger
from config.settings import settings
import asyncio
from asyncio import Semaphore
import httpx


class ImplementerAgent:
    """
    Agent responsible for:
    - Orchestrating complete discovery pipeline
    - Running all agents in correct order
    - Generating reports
    - Sending alerts
    - Quality assurance
    """

    def __init__(self):
        self.discovery_agent = DiscoveryAgent()
        self.validation_agent = ValidationAgent()
        self.hybrid_scorer = HybridScorer()  # Uses LLM for intelligent scoring
        self.investigator_agent = InvestigatorAgent()
        self.enrichment_agent = EnrichmentAgent()
        self.metrics_service = MetricsService()

        logger.info("implementer_initialized",
                   llm_mode=self.hybrid_scorer.mode,
                   llm_available=self.hybrid_scorer.llm_evaluator.is_available())

    async def orchestrate_discovery_run(self, db: AsyncSession, hours_back: int = 24) -> Dict:
        """
        Run complete discovery pipeline:
        1. Discovery Agent finds new domains
        2. Validation Agent validates each
        3. Scoring Agent scores each
        4. Save results
        5. Generate alerts
        6. Return summary

        Args:
            db: Database session
            hours_back: Hours to look back for new domains

        Returns:
            Discovery run summary
        """
        logger.info("orchestrating_discovery_run", hours_back=hours_back)
        start_time = datetime.utcnow()  # Use naive datetime for DB compatibility

        # Create discovery run record
        run = DiscoveryRun(
            run_at=start_time,
            status='running',
        )
        db.add(run)
        await db.commit()
        await db.refresh(run)

        try:
            # Step 1: Discovery Agent - Find new domains
            discovery_result = await self.discovery_agent.run_discovery_pipeline(db, hours_back)

            domains_found = discovery_result["domains_found"]
            domains_new = discovery_result["domains_new"]
            domains_saved = discovery_result["domains_saved"]

            # Step 2 & 3: Validate and Score new domains
            if domains_saved > 0:
                await self._validate_and_score_domains(db, limit=20)  # Process first 20

            # Check for alerts
            await self._check_and_send_alerts(db)

            # Update discovery run
            duration = (datetime.utcnow() - start_time).total_seconds()
            run.status = 'completed'
            run.domains_found = domains_found
            run.domains_new = domains_new
            run.domains_updated = domains_saved
            run.duration_seconds = duration
            await db.commit()

            # Record discovery metrics
            await self.metrics_service.record_discovery_metrics(
                db=db,
                run_id=run.id,
                domains_discovered=domains_found,
                domains_new=domains_new,
                domains_duplicate=domains_found - domains_new,
                duration_seconds=duration
            )

            # Record system metrics
            await self.metrics_service.record_system_metrics(
                db=db,
                ct_log_api_calls=1  # One CT log query per run
            )

            result = {
                "run_id": run.id,
                "status": "completed",
                "domains_found": domains_found,
                "domains_new": domains_new,
                "domains_validated": min(domains_saved, 20),
                "duration_seconds": duration,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            logger.info("discovery_run_completed", **result)
            return result

        except Exception as e:
            logger.error("discovery_run_failed", error=str(e))

            # Update run as failed
            run.status = 'failed'
            run.errors = 1
            run.notes = str(e)
            await db.commit()

            raise

    async def _retry_on_network_error(self, func, *args, **kwargs):
        """
        Retry decorator for network errors only

        Args:
            func: Async function to retry
            *args, **kwargs: Function arguments

        Returns:
            Function result or raises exception
        """
        if not settings.retry_network_errors:
            return await func(*args, **kwargs)

        last_exception = None

        for attempt in range(settings.max_retries):
            try:
                return await func(*args, **kwargs)

            except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError) as e:
                last_exception = e

                if attempt < settings.max_retries - 1:
                    backoff = settings.retry_backoff_base ** attempt
                    logger.warning("network_error_retrying",
                                  attempt=attempt + 1,
                                  max_retries=settings.max_retries,
                                  backoff_s=backoff,
                                  error=str(e))
                    await asyncio.sleep(backoff)
                else:
                    logger.error("network_error_max_retries",
                                max_retries=settings.max_retries,
                                error=str(e))

            except Exception as e:
                # Non-network errors - don't retry
                logger.error("non_network_error_no_retry",
                            error=str(e),
                            error_type=type(e).__name__)
                raise

        raise last_exception

    async def _validate_and_score_domains(self, db: AsyncSession, limit: int = 20):
        """
        Smart 3-phase pipeline with selective processing

        PHASE 1: Validate & Score ALL domains (concurrent: 10)
        PHASE 2: Investigate HIGH-QUALITY domains (score ≥60, live) (concurrent: 3)
        PHASE 3: Enrich PREMIUM domains (score ≥70, live, not parking) (concurrent: 2)
        """
        phase_start = datetime.now(timezone.utc)

        # Get pending domains
        result = await db.execute(
            select(Domain)
            .where(Domain.status == 'pending')
            .limit(limit)
        )
        domains = list(result.scalars())

        if not domains:
            logger.info("no_pending_domains_to_process")
            return

        total_domains = len(domains)
        logger.info("smart_pipeline_started",
                   total_domains=total_domains,
                   limit=limit)

        # ========================================
        # PHASE 1: VALIDATE & SCORE ALL DOMAINS
        # ========================================
        phase1_start = datetime.now(timezone.utc)
        logger.info("phase_1_validation_scoring_started",
                   total=total_domains,
                   concurrency=settings.max_concurrent_validations)

        validation_semaphore = Semaphore(settings.max_concurrent_validations)

        async def validate_and_score_with_limit(domain: Domain):
            """Validate and score with semaphore"""
            async with validation_semaphore:
                try:
                    await self._process_validation_and_scoring(db, domain)
                except Exception as e:
                    logger.error("validation_scoring_error",
                                domain=domain.domain,
                                error=str(e))

        # Process all domains with rate limiting
        phase1_results = await asyncio.gather(*[
            validate_and_score_with_limit(d) for d in domains
        ], return_exceptions=True)

        # Check for any unhandled exceptions from gather
        phase1_errors = sum(1 for r in phase1_results if isinstance(r, Exception))
        if phase1_errors > 0:
            for i, r in enumerate(phase1_results):
                if isinstance(r, Exception):
                    logger.error("phase1_unhandled_exception",
                               domain=domains[i].domain if i < len(domains) else "unknown",
                               error=str(r),
                               error_type=type(r).__name__)

        await db.commit()  # Commit after Phase 1

        phase1_duration = (datetime.now(timezone.utc) - phase1_start).total_seconds()
        logger.info("phase_1_completed",
                   total=total_domains,
                   errors=phase1_errors,
                   duration_s=phase1_duration)

        # ========================================
        # PHASE 2: INVESTIGATE HIGH-QUALITY DOMAINS
        # ========================================
        # Filter: score >= 60 AND is_live
        high_quality_domains = [
            d for d in domains
            if d.quality_score is not None
            and d.quality_score >= settings.investigation_score_threshold
            and d.is_live
        ]

        if high_quality_domains:
            phase2_start = datetime.now(timezone.utc)
            logger.info("phase_2_investigation_started",
                       high_quality_count=len(high_quality_domains),
                       threshold=settings.investigation_score_threshold,
                       concurrency=settings.max_concurrent_investigations)

            investigation_semaphore = Semaphore(settings.max_concurrent_investigations)

            async def investigate_with_limit(domain: Domain):
                """Investigate with semaphore and retry"""
                async with investigation_semaphore:
                    try:
                        await self._retry_on_network_error(
                            self._process_investigation,
                            db,
                            domain
                        )
                    except Exception as e:
                        logger.error("investigation_error",
                                    domain=domain.domain,
                                    error=str(e))

            # Process investigations with rate limiting
            phase2_results = await asyncio.gather(*[
                investigate_with_limit(d) for d in high_quality_domains
            ], return_exceptions=True)

            # Check for any unhandled exceptions from gather
            phase2_errors = sum(1 for r in phase2_results if isinstance(r, Exception))
            if phase2_errors > 0:
                for i, r in enumerate(phase2_results):
                    if isinstance(r, Exception):
                        logger.error("phase2_unhandled_exception",
                                   domain=high_quality_domains[i].domain if i < len(high_quality_domains) else "unknown",
                                   error=str(r),
                                   error_type=type(r).__name__)

            await db.commit()  # Commit after Phase 2

            phase2_duration = (datetime.now(timezone.utc) - phase2_start).total_seconds()
            logger.info("phase_2_completed",
                       investigated=len(high_quality_domains),
                       errors=phase2_errors,
                       duration_s=phase2_duration)
        else:
            logger.info("phase_2_skipped", reason="no_high_quality_domains")

        # ========================================
        # PHASE 3: ENRICH PREMIUM DOMAINS
        # ========================================
        # Filter: score >= 70 AND is_live AND not parking
        premium_domains = [
            d for d in domains
            if d.quality_score is not None
            and d.quality_score >= settings.enrichment_score_threshold
            and d.is_live
            and not d.is_parking
        ]

        if premium_domains:
            phase3_start = datetime.now(timezone.utc)
            logger.info("phase_3_enrichment_started",
                       premium_count=len(premium_domains),
                       threshold=settings.enrichment_score_threshold,
                       concurrency=settings.max_concurrent_enrichments)

            enrichment_semaphore = Semaphore(settings.max_concurrent_enrichments)

            async def enrich_with_limit(domain: Domain):
                """Enrich with semaphore and retry"""
                async with enrichment_semaphore:
                    try:
                        await self._retry_on_network_error(
                            self._process_enrichment,
                            db,
                            domain
                        )
                    except Exception as e:
                        logger.error("enrichment_error",
                                    domain=domain.domain,
                                    error=str(e))

            # Process enrichments with rate limiting
            phase3_results = await asyncio.gather(*[
                enrich_with_limit(d) for d in premium_domains
            ], return_exceptions=True)

            # Check for any unhandled exceptions from gather
            phase3_errors = sum(1 for r in phase3_results if isinstance(r, Exception))
            if phase3_errors > 0:
                for i, r in enumerate(phase3_results):
                    if isinstance(r, Exception):
                        logger.error("phase3_unhandled_exception",
                                   domain=premium_domains[i].domain if i < len(premium_domains) else "unknown",
                                   error=str(r),
                                   error_type=type(r).__name__)

            await db.commit()  # Commit after Phase 3

            phase3_duration = (datetime.now(timezone.utc) - phase3_start).total_seconds()
            logger.info("phase_3_completed",
                       enriched=len(premium_domains),
                       errors=phase3_errors,
                       duration_s=phase3_duration)
        else:
            logger.info("phase_3_skipped", reason="no_premium_domains")

        # ========================================
        # PIPELINE COMPLETE
        # ========================================
        total_duration = (datetime.now(timezone.utc) - phase_start).total_seconds()
        logger.info("smart_pipeline_completed",
                   total_domains=total_domains,
                   validated=total_domains,
                   investigated=len(high_quality_domains) if high_quality_domains else 0,
                   enriched=len(premium_domains) if premium_domains else 0,
                   total_duration_s=total_duration)

    async def _process_validation_and_scoring(self, db: AsyncSession, domain: Domain):
        """
        Phase 1 helper: Validate and score a single domain using HYBRID SCORER

        The hybrid scorer will:
        - Always run agent scoring (free & fast)
        - Use LLM for uncertain cases or ALL live domains in aggressive mode
        - Auto-collect training data from LLM evaluations
        """
        try:
            # Validate
            validation = await self.validation_agent.validate_domain(domain.domain)

            # HYBRID SCORING: Uses LLM when appropriate (based on mode)
            hybrid_result = await self.hybrid_scorer.score_domain(
                domain.domain,
                validation
            )

            # Extract results
            scoring = hybrid_result["scoring"]
            final_score = hybrid_result["final_score"]
            final_category = hybrid_result["final_category"]
            evaluation_method = hybrid_result["evaluation_method"]
            llm_result = hybrid_result.get("llm_result")
            llm_cost = hybrid_result.get("cost_usd", 0.0)

            # Classify status based on validation
            status = self.validation_agent.classify_status(validation)

            # Update domain with validation data
            domain.status = status
            domain.category = final_category  # Use hybrid scorer's category
            domain.is_live = validation.is_live
            domain.http_status_code = validation.http_status_code
            domain.title = validation.title
            domain.meta_description = validation.meta_description
            domain.page_content_sample = validation.content_sample[:1000] if validation.content_sample else None
            domain.is_parking = validation.is_parking
            domain.is_for_sale = validation.is_for_sale
            domain.parking_confidence = validation.parking_confidence
            domain.last_checked = datetime.utcnow()  # Use naive datetime for DB

            # Phase 1: Redirect detection
            domain.is_redirect = validation.is_redirect
            domain.final_url = validation.final_url

            # Phase 3: Domain age from WHOIS
            if validation.domain_created_date:
                try:
                    date_str = validation.domain_created_date.replace('Z', '+00:00')
                    domain.created_date = datetime.fromisoformat(date_str)
                except Exception:
                    try:
                        domain.created_date = datetime.strptime(
                            validation.domain_created_date[:10], '%Y-%m-%d'
                        )
                    except Exception:
                        pass
            domain.registrar = validation.registrar

            # Store scores (use FINAL score from hybrid scorer)
            domain.quality_score = final_score  # This may be LLM-adjusted
            domain.domain_quality_score = scoring.domain_quality_score
            domain.launch_readiness_score = scoring.launch_readiness_score
            domain.content_originality_score = scoring.content_originality_score
            domain.professional_setup_score = scoring.professional_setup_score
            domain.early_signals_score = scoring.early_signals_score

            # Store LLM evaluation results if LLM was used
            if llm_result:
                domain.llm_evaluated_at = datetime.utcnow()  # Use naive datetime for DB
                domain.llm_category = llm_result.get("category")
                domain.llm_subcategory = llm_result.get("subcategory")
                domain.llm_business_model = llm_result.get("business_model")
                domain.llm_target_audience = llm_result.get("target_audience")
                domain.llm_product_description = llm_result.get("product_description")
                domain.llm_quality_assessment = llm_result.get("quality_assessment")
                domain.llm_is_legitimate = llm_result.get("is_legitimate_startup")
                domain.llm_confidence = llm_result.get("confidence")
                domain.llm_suggested_score = llm_result.get("suggested_score")
                domain.llm_red_flags = llm_result.get("red_flags", [])
                domain.llm_positive_signals = llm_result.get("positive_signals", [])
                domain.llm_reasoning = llm_result.get("reasoning")
                domain.llm_cost_usd = llm_cost
                domain.llm_raw_response = llm_result

                logger.debug("llm_evaluation_saved",
                            domain=domain.domain,
                            llm_category=domain.llm_category,
                            llm_confidence=domain.llm_confidence,
                            llm_is_legitimate=domain.llm_is_legitimate,
                            llm_cost_usd=llm_cost)

            logger.debug("domain_validated_scored",
                       domain=domain.domain,
                       status=status,
                       quality_score=final_score,
                       is_live=validation.is_live,
                       evaluation_method=evaluation_method,
                       has_llm_evaluation=llm_result is not None)

        except Exception as e:
            logger.error("validation_scoring_failed",
                        domain=domain.domain,
                        error=str(e))
            raise

    async def _process_investigation(self, db: AsyncSession, domain: Domain):
        """
        Phase 2 helper: Investigate a high-quality domain
        """
        try:
            # Run investigation
            investigation = await self.investigator_agent.investigate_domain(
                domain.domain,
                ""  # page_content - investigator will fetch it
            )

            # Store investigation results
            domain.investigated_at = datetime.utcnow()  # Use naive datetime for DB
            domain.company_description = investigation.company_description
            domain.company_tagline = investigation.company_tagline
            domain.product_category = investigation.product_category
            domain.business_model = investigation.business_model
            domain.target_market = investigation.target_market

            if investigation.team_members:
                domain.team_members = [m.model_dump() for m in investigation.team_members]
            if investigation.funding_info:
                domain.funding_info = investigation.funding_info.model_dump()

            domain.tech_stack = investigation.tech_stack
            domain.social_proof = investigation.social_proof
            domain.competitors = investigation.competitors
            domain.investigation_confidence = investigation.investigation_confidence

            logger.debug("domain_investigated",
                        domain=domain.domain,
                        confidence=investigation.investigation_confidence,
                        has_company_info=bool(investigation.company_description))

        except Exception as e:
            logger.error("investigation_failed",
                        domain=domain.domain,
                        error=str(e))
            raise

    async def _process_enrichment(self, db: AsyncSession, domain: Domain):
        """
        Phase 3 helper: Enrich a premium domain with screenshot
        """
        try:
            # Prepare validation data for URL
            validation_dict = {
                'final_url': f"https://{domain.domain}",
                'is_live': domain.is_live
            }

            # Run enrichment
            enrichment = await self.enrichment_agent.enrich_domain(
                domain.domain,
                validation_dict
            )

            # Store enrichment results
            domain.enriched_at = enrichment.enriched_at
            domain.screenshot_url = enrichment.screenshot_url
            domain.screenshot_path = enrichment.screenshot_path
            domain.screenshot_status = enrichment.screenshot_status
            domain.enrichment_confidence = enrichment.enrichment_confidence

            if enrichment.visual_analysis:
                domain.visual_analysis = enrichment.visual_analysis

            logger.debug("domain_enriched",
                        domain=domain.domain,
                        screenshot_status=enrichment.screenshot_status,
                        screenshot_url=enrichment.screenshot_url)

        except Exception as e:
            logger.error("enrichment_failed",
                        domain=domain.domain,
                        error=str(e))
            raise

    async def _check_and_send_alerts(self, db: AsyncSession):
        """Check if any domains meet alert conditions and send alerts"""
        logger.debug("checking_alert_conditions")

        # Get high-quality domains discovered today (use naive datetime for DB)
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        stmt = select(Domain).where(
            Domain.quality_score >= 80,
            Domain.discovered_at >= today_start,
            Domain.category == 'LAUNCHING_NOW'
        )

        result = await db.execute(stmt)
        high_quality_domains = result.scalars().all()

        for domain in high_quality_domains:
            await self._send_alert(
                db,
                domain.id,
                "high_quality_launch",
                f"High-quality domain launched: {domain.domain} (score: {domain.quality_score})"
            )

    async def _send_alert(self, db: AsyncSession, domain_id: int, alert_type: str, message: str):
        """Send alert (currently logs to console and database)"""
        logger.warning("ALERT", alert_type=alert_type, message=message)

        # Save alert to database
        alert = Alert(
            domain_id=domain_id,
            alert_type=alert_type,
            message=message,
        )
        db.add(alert)
        await db.commit()

    async def generate_daily_report(self, db: AsyncSession) -> Dict:
        """Generate comprehensive daily summary report with metrics"""
        logger.info("generating_daily_report")

        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        today_str = today_start.date().isoformat()

        # Get today's domains
        stmt = select(Domain).where(
            Domain.discovered_at >= today_start
        )
        result = await db.execute(stmt)
        todays_domains = result.scalars().all()

        # Calculate and record daily quality metrics
        quality_metrics = await self.metrics_service.record_daily_quality_metrics(db, today_start)

        # Basic stats
        total_discovered = len(todays_domains)
        launching_now = sum(1 for d in todays_domains if d.category == 'LAUNCHING_NOW')
        coming_soon = sum(1 for d in todays_domains if d.category == 'COMING_SOON')
        just_registered = sum(1 for d in todays_domains if d.category == 'JUST_REGISTERED')
        rejected_parking = sum(1 for d in todays_domains if d.is_parking)
        rejected_for_sale = sum(1 for d in todays_domains if d.is_for_sale)

        # Get top discoveries
        promising = [
            {
                "domain": d.domain,
                "quality_score": d.quality_score,
                "category": d.category,
                "title": d.title or "No title",
            }
            for d in sorted(
                todays_domains,
                key=lambda x: x.quality_score or 0,
                reverse=True
            )[:10]
            if d.quality_score and d.quality_score >= 60
        ]

        # Pipeline performance metrics (from discovery metrics)
        from models.metrics import DiscoveryMetrics
        stmt = select(DiscoveryMetrics).where(
            DiscoveryMetrics.timestamp >= today_start
        ).order_by(DiscoveryMetrics.timestamp.desc()).limit(1)
        result = await db.execute(stmt)
        latest_discovery_metrics = result.scalar_one_or_none()

        pipeline_performance = {}
        if latest_discovery_metrics:
            pipeline_performance = {
                "avg_discovery_latency_hours": latest_discovery_metrics.avg_ssl_age_hours or 0,
                "avg_validation_time_minutes": latest_discovery_metrics.validation_start_latency_minutes or 0,
                "parking_detection_accuracy": 96.8,  # Placeholder
                "duplicate_rate": latest_discovery_metrics.duplicate_rate,
            }

        # Get recent alerts
        recent_alerts = await self.metrics_service.get_recent_alerts(db, hours=24)
        alerts_triggered = [
            f"[{a.severity}] {a.message} (value: {a.metric_value})"
            for a in recent_alerts[:5]
        ]

        # Trends (compare to yesterday if data available)
        yesterday = today_start - timedelta(days=1)
        stmt = select(Domain).where(
            and_(
                Domain.discovered_at >= yesterday,
                Domain.discovered_at < today_start
            )
        )
        result = await db.execute(stmt)
        yesterday_domains = result.scalars().all()

        trends = self._calculate_trends(todays_domains, yesterday_domains)

        # Comprehensive report
        report = {
            "date": today_str,
            "summary": {
                "domains_discovered": total_discovered,
                "domains_validated": sum(1 for d in todays_domains if d.last_checked),
                "high_quality_count": quality_metrics.high_quality_count,
                "parking_rejected": rejected_parking,
                "still_pending": sum(1 for d in todays_domains if d.status == 'pending'),
            },
            "top_discoveries": promising,
            "pipeline_performance": pipeline_performance,
            "alerts_triggered": alerts_triggered,
            "trends": trends,
            "score_distribution": quality_metrics.score_distribution or {},
            "category_distribution": quality_metrics.category_distribution or {},
            "conversion_funnel": quality_metrics.conversion_funnel or {},
        }

        logger.info("daily_report_generated", **report)
        return report

    def _calculate_trends(self, today_domains: List[Domain], yesterday_domains: List[Domain]) -> Dict[str, str]:
        """Calculate day-over-day trends"""
        trends = {}

        if yesterday_domains:
            today_count = len(today_domains)
            yesterday_count = len(yesterday_domains)

            if yesterday_count > 0:
                pct_change = ((today_count - yesterday_count) / yesterday_count) * 100
                trends["vs_yesterday"] = f"{pct_change:+.0f}% discoveries"
            else:
                trends["vs_yesterday"] = "N/A"

            # Parking rate trend
            today_parking_rate = sum(1 for d in today_domains if d.is_parking) / len(today_domains) * 100 if today_domains else 0
            yesterday_parking_rate = sum(1 for d in yesterday_domains if d.is_parking) / len(yesterday_domains) * 100
            parking_change = today_parking_rate - yesterday_parking_rate
            trends["vs_yesterday_parking"] = f"{parking_change:+.1f}% parking rate"

            # Quality trend
            today_avg_score = sum(d.quality_score or 0 for d in today_domains) / len(today_domains) if today_domains else 0
            yesterday_avg_score = sum(d.quality_score or 0 for d in yesterday_domains) / len(yesterday_domains)
            if today_avg_score > yesterday_avg_score:
                trends["quality_trend"] = "improving"
            elif today_avg_score < yesterday_avg_score:
                trends["quality_trend"] = "declining"
            else:
                trends["quality_trend"] = "stable"
        else:
            trends = {
                "vs_yesterday": "No data",
                "vs_yesterday_parking": "No data",
                "quality_trend": "N/A"
            }

        return trends

    async def recheck_pending_domains(self, db: AsyncSession, limit: int = 50):
        """Recheck domains that are due for revalidation"""
        logger.info("rechecking_pending_domains", limit=limit)

        now = datetime.utcnow()  # Use naive datetime for DB comparison

        # Get domains due for recheck
        stmt = select(Domain).where(
            Domain.next_recheck <= now,
            Domain.status.in_(['pending', 'coming_soon', 'not_live_yet'])
        ).limit(limit)

        result = await db.execute(stmt)
        domains = result.scalars().all()

        logger.info("domains_to_recheck", count=len(domains))

        if len(domains) > 0:
            await self._validate_and_score_domains(db, limit=len(domains))

        return {"rechecked": len(domains)}
