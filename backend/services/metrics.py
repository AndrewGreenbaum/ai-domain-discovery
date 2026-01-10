"""Comprehensive metrics collection and reporting service"""
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from models.domain import Domain, DiscoveryRun
from models.metrics import (
    DiscoveryMetrics, ValidationMetrics, QualityMetrics,
    SystemMetrics, MetricAlert
)
from utils.logger import logger
import os


# Alert thresholds from system specification
DISCOVERY_ALERTS = {
    "zero_discoveries_6h": {
        "threshold": 0,
        "severity": "CRITICAL",
        "message": "No domains found in 6 hours"
    },
    "surge_100_domains": {
        "threshold": 100,
        "severity": "WARNING",
        "message": "Unusual volume, possible spam wave"
    },
    "duplicate_rate_high": {
        "threshold": 10.0,  # %
        "severity": "WARNING",
        "message": ">10% duplicates, check filtering"
    },
    "discovery_latency_high": {
        "threshold": 12.0,  # hours
        "severity": "WARNING",
        "message": ">12h latency, check scheduler"
    }
}

VALIDATION_ALERTS = {
    "parking_accuracy_drop": {
        "threshold": 90.0,  # %
        "severity": "WARNING",
        "message": "<90% parking detection accuracy"
    },
    "http_check_failure_high": {
        "threshold": 20.0,  # %
        "severity": "WARNING",
        "message": ">20% domains unreachable"
    },
    "validation_queue_backlog": {
        "threshold": 100,
        "severity": "WARNING",
        "message": ">100 domains pending validation"
    }
}

QUALITY_ALERTS = {
    "no_high_quality_24h": {
        "threshold": 0,
        "severity": "INFO",
        "message": "No score >80 domains in 24h"
    },
    "high_parking_rate": {
        "threshold": 50.0,  # %
        "severity": "WARNING",
        "message": ">50% parking rate, check CT log filters"
    },
    "confidence_drop": {
        "threshold": 50.0,  # %
        "severity": "WARNING",
        "message": "Avg confidence <50%"
    }
}


class MetricsService:
    """Service for collecting, calculating, and reporting metrics"""

    async def record_discovery_metrics(
        self,
        db: AsyncSession,
        run_id: int,
        domains_discovered: int,
        domains_new: int,
        domains_duplicate: int,
        duration_seconds: float
    ) -> DiscoveryMetrics:
        """
        Record discovery performance metrics for a run

        Args:
            db: Database session
            run_id: Discovery run ID
            domains_discovered: Total domains found
            domains_new: New domains saved
            domains_duplicate: Duplicate domains filtered
            duration_seconds: Total pipeline duration

        Returns:
            DiscoveryMetrics instance
        """
        duplicate_rate = (
            (domains_duplicate / domains_discovered * 100)
            if domains_discovered > 0 else 0.0
        )

        # Calculate data quality metrics from domains
        quality_metrics = await self._calculate_discovery_quality_metrics(
            db, run_id, domains_new
        )

        metrics = DiscoveryMetrics(
            run_id=run_id,
            domains_discovered=domains_discovered,
            domains_new=domains_new,
            domains_duplicate=domains_duplicate,
            duplicate_rate=duplicate_rate,
            full_pipeline_duration_minutes=duration_seconds / 60.0,
            **quality_metrics
        )

        db.add(metrics)
        await db.commit()
        await db.refresh(metrics)

        # Check for alerts
        await self._check_discovery_alerts(db, metrics)

        logger.info(
            "discovery_metrics_recorded",
            run_id=run_id,
            domains_discovered=domains_discovered,
            duplicate_rate=duplicate_rate
        )

        return metrics

    async def _calculate_discovery_quality_metrics(
        self,
        db: AsyncSession,
        run_id: int,
        domains_count: int
    ) -> Dict[str, float]:
        """Calculate quality metrics for discovered domains"""
        if domains_count == 0:
            return {
                "resolvable_rate": None,
                "live_on_discovery_rate": None,
                "ssl_certificate_rate": None,
                "avg_ssl_age_hours": None
            }

        # Get domains from this run (approximate by recent discoveries)
        cutoff = datetime.utcnow() - timedelta(hours=1)
        result = await db.execute(
            select(Domain)
            .where(Domain.discovered_at >= cutoff)
            .limit(domains_count)
        )
        domains = result.scalars().all()

        if not domains:
            return {
                "resolvable_rate": None,
                "live_on_discovery_rate": None,
                "ssl_certificate_rate": None,
                "avg_ssl_age_hours": None
            }

        # Calculate rates
        live_count = sum(1 for d in domains if d.is_live)
        ssl_count = sum(1 for d in domains if d.ssl_issuer is not None)

        # Calculate SSL age
        ssl_ages = []
        for d in domains:
            if d.ssl_issued_at:
                age_hours = (datetime.utcnow() - d.ssl_issued_at).total_seconds() / 3600
                ssl_ages.append(age_hours)

        return {
            "resolvable_rate": None,  # Would need DNS check tracking
            "live_on_discovery_rate": (live_count / len(domains) * 100),
            "ssl_certificate_rate": (ssl_count / len(domains) * 100),
            "avg_ssl_age_hours": sum(ssl_ages) / len(ssl_ages) if ssl_ages else None
        }

    async def record_daily_quality_metrics(
        self,
        db: AsyncSession,
        date: Optional[datetime] = None
    ) -> QualityMetrics:
        """
        Calculate and record daily quality metrics

        Args:
            db: Database session
            date: Date to calculate for (defaults to today)

        Returns:
            QualityMetrics instance
        """
        if date is None:
            date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

        # Get all domains discovered on this date
        next_date = date + timedelta(days=1)
        result = await db.execute(
            select(Domain)
            .where(and_(
                Domain.discovered_at >= date,
                Domain.discovered_at < next_date
            ))
        )
        domains = result.scalars().all()

        if not domains:
            logger.info("no_domains_for_quality_metrics", date=date)
            # Return empty metrics
            metrics = QualityMetrics(
                date=date,
                high_quality_count=0,
                medium_quality_count=0,
                grade_a_plus_count=0,
                viable_startups_count=0,
                total_domains=0,
                parking_rejected=0,
                for_sale_rejected=0
            )
            db.add(metrics)
            await db.commit()
            return metrics

        # Calculate startup discovery rates
        high_quality = [d for d in domains if d.quality_score and d.quality_score > 80]
        medium_quality = [d for d in domains if d.quality_score and 60 <= d.quality_score <= 80]
        grade_a_plus = [
            d for d in domains
            if d.quality_score and d.quality_score > 85
            # Note: confidence not tracked separately yet
        ]
        viable_startups = [
            d for d in domains
            if not d.is_parking and d.quality_score and d.quality_score > 50
        ]

        # Calculate score distribution
        score_dist = self._calculate_score_distribution(domains)

        # Calculate confidence metrics
        conf_metrics = self._calculate_confidence_metrics(domains)

        # Calculate category distribution
        category_dist = self._calculate_category_distribution(domains)

        # Calculate conversion funnel
        funnel = self._calculate_conversion_funnel(domains)

        # Count rejections
        parking_rejected = sum(1 for d in domains if d.is_parking)
        for_sale_rejected = sum(1 for d in domains if d.is_for_sale)

        metrics = QualityMetrics(
            date=date,
            high_quality_count=len(high_quality),
            medium_quality_count=len(medium_quality),
            grade_a_plus_count=len(grade_a_plus),
            viable_startups_count=len(viable_startups),
            score_distribution=score_dist,
            avg_confidence_score=conf_metrics.get("avg"),
            high_confidence_rate=conf_metrics.get("high_rate"),
            low_confidence_rate=conf_metrics.get("low_rate"),
            category_distribution=category_dist,
            conversion_funnel=funnel,
            total_domains=len(domains),
            parking_rejected=parking_rejected,
            for_sale_rejected=for_sale_rejected
        )

        db.add(metrics)
        await db.commit()
        await db.refresh(metrics)

        # Check for alerts
        await self._check_quality_alerts(db, metrics)

        logger.info(
            "quality_metrics_recorded",
            date=date.date(),
            high_quality=len(high_quality),
            parking_rate=parking_rejected / len(domains) * 100
        )

        return metrics

    def _calculate_score_distribution(self, domains: List[Domain]) -> Dict[str, int]:
        """Calculate score distribution by grade"""
        dist = {
            "A+ (85-100)": 0,
            "A (80-84)": 0,
            "B+ (70-79)": 0,
            "B (60-69)": 0,
            "C (50-59)": 0,
            "D (<50)": 0,
            "Insufficient Data": 0
        }

        for d in domains:
            if not d.quality_score:
                dist["Insufficient Data"] += 1
            elif d.quality_score >= 85:
                dist["A+ (85-100)"] += 1
            elif d.quality_score >= 80:
                dist["A (80-84)"] += 1
            elif d.quality_score >= 70:
                dist["B+ (70-79)"] += 1
            elif d.quality_score >= 60:
                dist["B (60-69)"] += 1
            elif d.quality_score >= 50:
                dist["C (50-59)"] += 1
            else:
                dist["D (<50)"] += 1

        return dist

    def _calculate_confidence_metrics(self, domains: List[Domain]) -> Dict[str, float]:
        """Calculate confidence metrics (placeholder for now)"""
        # Note: Confidence not stored in Domain model yet
        # Would need to add confidence field to Domain model
        return {
            "avg": None,
            "high_rate": None,
            "low_rate": None
        }

    def _calculate_category_distribution(self, domains: List[Domain]) -> Dict[str, int]:
        """Calculate category distribution"""
        dist = {}
        for d in domains:
            category = d.category or "UNKNOWN"
            dist[category] = dist.get(category, 0) + 1
        return dist

    def _calculate_conversion_funnel(self, domains: List[Domain]) -> Dict[str, Any]:
        """Calculate conversion funnel metrics"""
        total = len(domains)
        resolvable = sum(1 for d in domains if d.is_live or d.http_status_code)
        live = sum(1 for d in domains if d.is_live)
        non_parking = sum(1 for d in domains if d.is_live and not d.is_parking)
        scored_60_plus = sum(
            1 for d in domains
            if d.quality_score and d.quality_score > 60 and not d.is_parking
        )
        high_quality = sum(
            1 for d in domains
            if d.quality_score and d.quality_score > 80
        )

        return {
            "discovered": total,
            "discovered_pct": 100.0,
            "resolvable": resolvable,
            "resolvable_pct": (resolvable / total * 100) if total > 0 else 0,
            "live": live,
            "live_pct": (live / total * 100) if total > 0 else 0,
            "non_parking": non_parking,
            "non_parking_pct": (non_parking / total * 100) if total > 0 else 0,
            "scored_60_plus": scored_60_plus,
            "scored_60_plus_pct": (scored_60_plus / total * 100) if total > 0 else 0,
            "high_quality": high_quality,
            "high_quality_pct": (high_quality / total * 100) if total > 0 else 0
        }

    async def record_system_metrics(
        self,
        db: AsyncSession,
        ct_log_api_calls: int = 0
    ) -> SystemMetrics:
        """Record system health metrics"""
        # Get total domains count
        result = await db.execute(select(func.count(Domain.id)))
        total_domains = result.scalar() or 0

        # Get active domains count (being rechecked)
        now = datetime.utcnow()
        result = await db.execute(
            select(func.count(Domain.id))
            .where(Domain.next_recheck.isnot(None))
            .where(Domain.next_recheck > now)
        )
        active_domains = result.scalar() or 0

        # Get database size
        db_size = self._get_database_size()

        metrics = SystemMetrics(
            ct_log_api_calls=ct_log_api_calls,
            total_domains_stored=total_domains,
            active_domains_count=active_domains,
            database_size_mb=db_size
        )

        db.add(metrics)
        await db.commit()
        await db.refresh(metrics)

        logger.info(
            "system_metrics_recorded",
            total_domains=total_domains,
            active_domains=active_domains,
            db_size_mb=db_size
        )

        return metrics

    def _get_database_size(self) -> Optional[float]:
        """Get database file size in MB"""
        try:
            # Check for SQLite database file
            if os.path.exists("aidomains.db"):
                size_bytes = os.path.getsize("aidomains.db")
                return size_bytes / (1024 * 1024)  # Convert to MB
        except Exception as e:
            logger.warning("database_size_check_failed", error=str(e))
        return None

    async def _check_discovery_alerts(
        self,
        db: AsyncSession,
        metrics: DiscoveryMetrics
    ):
        """Check discovery metrics against alert thresholds"""
        # Zero discoveries
        if metrics.domains_discovered == 0:
            await self._create_alert(
                db,
                alert_type="discovery",
                severity="CRITICAL",
                alert_key="zero_discoveries_6h",
                message=DISCOVERY_ALERTS["zero_discoveries_6h"]["message"],
                metric_value=0.0
            )

        # Surge detection
        if metrics.domains_discovered > DISCOVERY_ALERTS["surge_100_domains"]["threshold"]:
            await self._create_alert(
                db,
                alert_type="discovery",
                severity="WARNING",
                alert_key="surge_100_domains",
                message=DISCOVERY_ALERTS["surge_100_domains"]["message"],
                metric_value=float(metrics.domains_discovered),
                threshold_value=float(DISCOVERY_ALERTS["surge_100_domains"]["threshold"])
            )

        # High duplicate rate
        if metrics.duplicate_rate > DISCOVERY_ALERTS["duplicate_rate_high"]["threshold"]:
            await self._create_alert(
                db,
                alert_type="discovery",
                severity="WARNING",
                alert_key="duplicate_rate_high",
                message=DISCOVERY_ALERTS["duplicate_rate_high"]["message"],
                metric_value=metrics.duplicate_rate,
                threshold_value=DISCOVERY_ALERTS["duplicate_rate_high"]["threshold"]
            )

    async def _check_quality_alerts(
        self,
        db: AsyncSession,
        metrics: QualityMetrics
    ):
        """Check quality metrics against alert thresholds"""
        # No high quality domains in 24h
        if metrics.high_quality_count == 0:
            await self._create_alert(
                db,
                alert_type="quality",
                severity="INFO",
                alert_key="no_high_quality_24h",
                message=QUALITY_ALERTS["no_high_quality_24h"]["message"],
                metric_value=0.0
            )

        # High parking rate
        if metrics.total_domains > 0:
            parking_rate = (metrics.parking_rejected / metrics.total_domains * 100)
            if parking_rate > QUALITY_ALERTS["high_parking_rate"]["threshold"]:
                await self._create_alert(
                    db,
                    alert_type="quality",
                    severity="WARNING",
                    alert_key="high_parking_rate",
                    message=QUALITY_ALERTS["high_parking_rate"]["message"],
                    metric_value=parking_rate,
                    threshold_value=QUALITY_ALERTS["high_parking_rate"]["threshold"]
                )

    async def _create_alert(
        self,
        db: AsyncSession,
        alert_type: str,
        severity: str,
        alert_key: str,
        message: str,
        metric_value: Optional[float] = None,
        threshold_value: Optional[float] = None
    ):
        """Create a metric alert"""
        alert = MetricAlert(
            alert_type=alert_type,
            severity=severity,
            alert_key=alert_key,
            message=message,
            metric_value=metric_value,
            threshold_value=threshold_value
        )

        db.add(alert)
        await db.commit()

        logger.warning(
            "metric_alert_triggered",
            alert_type=alert_type,
            severity=severity,
            alert_key=alert_key,
            message=message
        )

    async def get_recent_alerts(
        self,
        db: AsyncSession,
        hours: int = 24,
        severity: Optional[str] = None,
        unresolved_only: bool = True
    ) -> List[MetricAlert]:
        """Get recent metric alerts"""
        cutoff = datetime.utcnow() - timedelta(hours=hours)

        query = select(MetricAlert).where(MetricAlert.timestamp >= cutoff)

        if severity:
            query = query.where(MetricAlert.severity == severity)

        if unresolved_only:
            query = query.where(MetricAlert.resolved_at.is_(None))

        query = query.order_by(MetricAlert.timestamp.desc())

        result = await db.execute(query)
        return list(result.scalars().all())
