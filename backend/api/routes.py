"""FastAPI routes for domain discovery API"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from datetime import datetime, timezone, timedelta
from typing import List, Optional

from models.domain import Domain, DiscoveryRun
from models.metrics import (
    DiscoveryMetrics, QualityMetrics, SystemMetrics, MetricAlert
)
from models.schemas import (
    DomainResponse,
    DiscoveryRunResponse,
    DailyReportResponse,
    StatsResponse,
    DiscoveryMetricsResponse,
    QualityMetricsResponse,
    SystemMetricsResponse,
    MetricAlertResponse,
    InvestigationResponse,
)
from services.database import get_db
from services.metrics import MetricsService
from agents.implementer import ImplementerAgent
from agents.validation import ValidationAgent
from agents.scoring import ScoringAgent
from utils.logger import logger

router = APIRouter(prefix="/api")

# Initialize agents and services
implementer = ImplementerAgent()
validation_agent = ValidationAgent()
scoring_agent = ScoringAgent()
metrics_service = MetricsService()


@router.post("/discover/daily", response_model=dict)
async def trigger_daily_discovery(
    hours_back: int = Query(default=24, ge=1, le=168),
    db: AsyncSession = Depends(get_db)
):
    """
    Trigger manual discovery run

    Args:
        hours_back: How many hours back to search (1-168)
    """
    logger.info("api_trigger_discovery", hours_back=hours_back)

    try:
        result = await implementer.orchestrate_discovery_run(db, hours_back)
        return result
    except Exception as e:
        logger.error("api_discover_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/domains/today", response_model=List[DomainResponse])
async def get_todays_domains(
    db: AsyncSession = Depends(get_db)
):
    """Get all domains discovered today"""
    logger.info("api_get_todays_domains")

    # Use naive datetime for database comparison (PostgreSQL asyncpg compatibility)
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    stmt = select(Domain).where(
        Domain.discovered_at >= today
    ).order_by(Domain.discovered_at.desc())

    result = await db.execute(stmt)
    domains = result.scalars().all()

    return domains


@router.get("/domains/{domain_id}", response_model=DomainResponse)
async def get_domain_by_id(
    domain_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get specific domain by ID"""
    logger.info("api_get_domain", domain_id=domain_id)

    stmt = select(Domain).where(Domain.id == domain_id)
    result = await db.execute(stmt)
    domain = result.scalar_one_or_none()

    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")

    return domain


@router.get("/domains", response_model=List[DomainResponse])
async def get_domains(
    hours_back: Optional[int] = Query(default=24, ge=1, le=720),
    status: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None),
    min_score: Optional[int] = Query(default=None, ge=0, le=100),
    max_score: Optional[int] = Query(default=None, ge=0, le=100),
    limit: int = Query(default=100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db)
):
    """
    Get domains with filters

    Args:
        hours_back: Hours to look back (default 24)
        status: Filter by status
        search: Search in domain name
        min_score: Minimum quality score (0-100)
        max_score: Maximum quality score (0-100)
        limit: Max results (default 100)
    """
    logger.info("api_get_domains", hours_back=hours_back, status=status, min_score=min_score, max_score=max_score)

    # Use naive datetime for database comparison (PostgreSQL asyncpg compatibility)
    cutoff_time = datetime.utcnow() - timedelta(hours=hours_back)

    # Build query
    conditions = [Domain.discovered_at >= cutoff_time]

    if status:
        conditions.append(Domain.status == status)

    if search:
        conditions.append(Domain.domain.ilike(f"%{search}%"))

    if min_score is not None:
        conditions.append(Domain.quality_score >= min_score)

    if max_score is not None:
        conditions.append(Domain.quality_score <= max_score)

    stmt = select(Domain).where(
        and_(*conditions)
    ).order_by(Domain.discovered_at.desc()).limit(limit)

    result = await db.execute(stmt)
    domains = result.scalars().all()

    return domains


@router.post("/validate/{domain}", response_model=dict)
async def validate_specific_domain(
    domain: str,
    db: AsyncSession = Depends(get_db)
):
    """Validate a specific domain on-demand"""
    logger.info("api_validate_domain", domain=domain)

    try:
        # Validate
        validation = await validation_agent.validate_domain(domain)

        # Score
        scoring = await scoring_agent.calculate_scores(domain, validation)

        # Classify
        status = validation_agent.classify_status(validation)
        category = scoring_agent.categorize_domain(scoring.quality_score, validation)

        return {
            "domain": domain,
            "validation": validation.model_dump(),
            "scoring": scoring.model_dump(),
            "status": status,
            "category": category,
        }

    except Exception as e:
        logger.error("api_validate_failed", domain=domain, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reports/today", response_model=dict)
async def get_daily_report(
    db: AsyncSession = Depends(get_db)
):
    """Get today's daily report"""
    logger.info("api_get_daily_report")

    try:
        report = await implementer.generate_daily_report(db)
        return report
    except Exception as e:
        logger.error("api_report_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats/today", response_model=StatsResponse)
async def get_todays_stats(
    db: AsyncSession = Depends(get_db)
):
    """Get quick stats for today"""
    logger.info("api_get_stats")

    # Use naive datetime for database comparison (PostgreSQL asyncpg compatibility)
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    # Count total discovered today
    stmt = select(func.count()).select_from(Domain).where(
        Domain.discovered_at >= today
    )
    result = await db.execute(stmt)
    today_count = result.scalar()

    # Count live domains today
    stmt = select(func.count()).select_from(Domain).where(
        and_(
            Domain.discovered_at >= today,
            Domain.is_live == True
        )
    )
    result = await db.execute(stmt)
    live_count = result.scalar()

    # Count parking domains today
    stmt = select(func.count()).select_from(Domain).where(
        and_(
            Domain.discovered_at >= today,
            Domain.is_parking == True
        )
    )
    result = await db.execute(stmt)
    parking_count = result.scalar()

    return StatsResponse(
        today_count=today_count or 0,
        live_count=live_count or 0,
        parking_count=parking_count or 0,
    )


@router.get("/runs/recent", response_model=List[DiscoveryRunResponse])
async def get_recent_runs(
    limit: int = Query(default=10, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """Get recent discovery runs"""
    logger.info("api_get_recent_runs", limit=limit)

    stmt = select(DiscoveryRun).order_by(
        DiscoveryRun.run_at.desc()
    ).limit(limit)

    result = await db.execute(stmt)
    runs = result.scalars().all()

    return runs


# ============================================================================
# METRICS ENDPOINTS
# ============================================================================

@router.get("/metrics/discovery", response_model=List[DiscoveryMetricsResponse])
async def get_discovery_metrics(
    hours: int = Query(default=24, ge=1, le=168),
    db: AsyncSession = Depends(get_db)
):
    """
    Get discovery performance metrics

    Args:
        hours: Hours to look back (default: 24)
    """
    logger.info("api_get_discovery_metrics", hours=hours)

    # Use naive datetime for database comparison (PostgreSQL asyncpg compatibility)
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    stmt = select(DiscoveryMetrics).where(
        DiscoveryMetrics.timestamp >= cutoff
    ).order_by(DiscoveryMetrics.timestamp.desc())

    result = await db.execute(stmt)
    metrics = result.scalars().all()

    return metrics


@router.get("/metrics/quality/today", response_model=QualityMetricsResponse)
async def get_todays_quality_metrics(
    db: AsyncSession = Depends(get_db)
):
    """Get today's quality metrics"""
    logger.info("api_get_quality_metrics")

    # Use naive datetime for database comparison (PostgreSQL asyncpg compatibility)
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    stmt = select(QualityMetrics).where(
        QualityMetrics.date == today
    ).order_by(QualityMetrics.id.desc()).limit(1)
    result = await db.execute(stmt)
    metrics = result.scalars().first()

    if not metrics:
        # Generate if not exists
        metrics = await metrics_service.record_daily_quality_metrics(db, today)

    return metrics


@router.get("/metrics/quality/range", response_model=List[QualityMetricsResponse])
async def get_quality_metrics_range(
    days: int = Query(default=7, ge=1, le=90),
    db: AsyncSession = Depends(get_db)
):
    """Get quality metrics for date range"""
    logger.info("api_get_quality_metrics_range", days=days)

    # Use naive datetime for database comparison (PostgreSQL asyncpg compatibility)
    cutoff = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days)

    # Get one row per date (most recent by ID) - Works with SQLite and PostgreSQL
    # Use subquery to get max ID per date, then fetch those records
    subquery = (
        select(func.max(QualityMetrics.id).label('max_id'))
        .where(QualityMetrics.date >= cutoff)
        .group_by(QualityMetrics.date)
        .subquery()
    )

    stmt = (
        select(QualityMetrics)
        .where(QualityMetrics.id.in_(select(subquery.c.max_id)))
        .order_by(QualityMetrics.date.desc())
    )

    result = await db.execute(stmt)
    metrics = result.scalars().all()

    return metrics


@router.get("/metrics/system/latest", response_model=SystemMetricsResponse)
async def get_latest_system_metrics(
    db: AsyncSession = Depends(get_db)
):
    """Get latest system health metrics"""
    logger.info("api_get_system_metrics")

    stmt = select(SystemMetrics).order_by(
        SystemMetrics.timestamp.desc()
    ).limit(1)

    result = await db.execute(stmt)
    metrics = result.scalar_one_or_none()

    if not metrics:
        raise HTTPException(status_code=404, detail="No system metrics found")

    return metrics


@router.get("/metrics/alerts", response_model=List[MetricAlertResponse])
async def get_metric_alerts(
    hours: int = Query(default=24, ge=1, le=168),
    severity: Optional[str] = Query(default=None),
    unresolved_only: bool = Query(default=True),
    db: AsyncSession = Depends(get_db)
):
    """
    Get metric alerts

    Args:
        hours: Hours to look back
        severity: Filter by severity (INFO, WARNING, CRITICAL)
        unresolved_only: Show only unresolved alerts
    """
    logger.info("api_get_alerts", hours=hours, severity=severity)

    alerts = await metrics_service.get_recent_alerts(
        db=db,
        hours=hours,
        severity=severity,
        unresolved_only=unresolved_only
    )

    return alerts


@router.get("/metrics/dashboard", response_model=dict)
async def get_metrics_dashboard(
    db: AsyncSession = Depends(get_db)
):
    """
    Get comprehensive metrics dashboard

    Returns all key metrics for dashboard display
    """
    logger.info("api_get_metrics_dashboard")

    # Use naive datetime for database comparison (PostgreSQL asyncpg compatibility)
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    # Get today's quality metrics
    stmt = select(QualityMetrics).where(
        QualityMetrics.date == today
    ).order_by(QualityMetrics.id.desc()).limit(1)
    result = await db.execute(stmt)
    quality_metrics = result.scalars().first()

    # Get latest discovery metrics
    stmt = select(DiscoveryMetrics).order_by(
        DiscoveryMetrics.timestamp.desc()
    ).limit(1)
    result = await db.execute(stmt)
    discovery_metrics = result.scalars().first()

    # Get latest system metrics
    stmt = select(SystemMetrics).order_by(
        SystemMetrics.timestamp.desc()
    ).limit(1)
    result = await db.execute(stmt)
    system_metrics = result.scalars().first()

    # Get active alerts
    alerts = await metrics_service.get_recent_alerts(db, hours=24, unresolved_only=True)

    dashboard = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "quality_metrics": QualityMetricsResponse.model_validate(quality_metrics) if quality_metrics else None,
        "discovery_metrics": DiscoveryMetricsResponse.model_validate(discovery_metrics) if discovery_metrics else None,
        "system_metrics": SystemMetricsResponse.model_validate(system_metrics) if system_metrics else None,
        "active_alerts": [MetricAlertResponse.model_validate(a) for a in alerts],
        "alert_count": len(alerts),
    }

    return dashboard


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "ai-domain-discovery"
    }


@router.get("/scheduler/next-run")
async def get_next_scheduled_run():
    """
    Get the next scheduled discovery run time

    Schedule: 9 AM, 2 PM, 8 PM UTC daily
    """
    now = datetime.utcnow()  # Use naive datetime for consistency

    # Scheduled hours in UTC
    schedule_hours = [9, 14, 20]  # 9 AM, 2 PM, 8 PM UTC

    # Find next run time
    today = now.replace(minute=0, second=0, microsecond=0)

    next_run = None
    for hour in schedule_hours:
        candidate = today.replace(hour=hour)
        if candidate > now:
            next_run = candidate
            break

    # If no run left today, next run is tomorrow at 9 AM
    if next_run is None:
        tomorrow = today + timedelta(days=1)
        next_run = tomorrow.replace(hour=9)

    seconds_until_next = int((next_run - now).total_seconds())

    return {
        "next_run_at": next_run.isoformat() + "Z",
        "seconds_until_next": seconds_until_next,
        "schedule": "9 AM, 2 PM, 8 PM UTC",
        "schedule_hours": schedule_hours
    }


@router.get("/llm/status")
async def get_llm_status(db: AsyncSession = Depends(get_db)):
    """
    Get LLM service status

    Returns:
        enabled: Whether LLM evaluation is active
        provider: LLM provider (openai/anthropic)
        model: Model being used
        evaluations_today: Count of LLM evaluations today
        last_evaluation: Timestamp of last LLM evaluation
    """
    from services.llm_service import llm_service

    # Get count of LLM evaluations today (use naive datetime for PostgreSQL)
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    stmt = select(func.count()).select_from(Domain).where(
        and_(
            Domain.llm_evaluated_at >= today,
            Domain.llm_evaluated_at.isnot(None)
        )
    )
    result = await db.execute(stmt)
    evaluations_today = result.scalar() or 0

    # Get last evaluation timestamp
    stmt = select(Domain.llm_evaluated_at).where(
        Domain.llm_evaluated_at.isnot(None)
    ).order_by(Domain.llm_evaluated_at.desc()).limit(1)
    result = await db.execute(stmt)
    last_eval = result.scalar()

    return {
        "enabled": llm_service.enabled,
        "provider": llm_service.provider,
        "model": llm_service.model,
        "evaluations_today": evaluations_today,
        "last_evaluation": last_eval.isoformat() if last_eval else None,
        "score_range": {
            "min": llm_service.UNCERTAIN_SCORE_MIN,
            "max": llm_service.UNCERTAIN_SCORE_MAX
        }
    }


@router.post("/investigate/{domain}", response_model=InvestigationResponse)
async def investigate_domain_endpoint(domain: str):
    """
    Run deep investigation on a specific domain
    
    This endpoint triggers the Investigator Agent to perform:
    - Company information extraction
    - Team member discovery
    - Funding status detection
    - Tech stack analysis
    - Social proof gathering
    """
    try:
        logger.info("api_investigate_domain", domain=domain)
        
        from agents.investigator import InvestigatorAgent
        investigator = InvestigatorAgent()
        
        investigation_result = await investigator.investigate_domain(domain)
        
        return InvestigationResponse(
            domain=domain,
            investigation=investigation_result,
            status="completed"
        )
    
    except Exception as e:
        logger.error("api_investigate_domain_failed", domain=domain, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
