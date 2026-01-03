"""Database models for comprehensive metrics tracking"""
from sqlalchemy import Column, Integer, String, Float, DateTime, JSON, Index
from sqlalchemy.sql import func
from models.domain import Base


class DiscoveryMetrics(Base):
    """Track discovery performance metrics per run"""
    __tablename__ = "discovery_metrics"

    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, default=func.now())

    # Volume metrics
    domains_discovered = Column(Integer, default=0)
    domains_new = Column(Integer, default=0)
    domains_duplicate = Column(Integer, default=0)
    duplicate_rate = Column(Float, default=0.0)  # %

    # Latency metrics (hours)
    avg_ssl_age_hours = Column(Float)  # Avg hours since SSL issued
    discovery_latency_hours = Column(Float)  # CT log to discovery
    validation_start_latency_minutes = Column(Float)  # Discovery to validation
    full_pipeline_duration_minutes = Column(Float)  # Total duration

    # Data quality metrics
    resolvable_rate = Column(Float)  # % with valid DNS
    live_on_discovery_rate = Column(Float)  # % immediately accessible
    ssl_certificate_rate = Column(Float)  # % with SSL

    # Peak hours
    peak_discovery_hour = Column(Integer)  # Hour with most domains

    __table_args__ = (
        Index('idx_discovery_metrics_timestamp', 'timestamp'),
    )


class ValidationMetrics(Base):
    """Track validation accuracy metrics (daily aggregates)"""
    __tablename__ = "validation_metrics"

    id = Column(Integer, primary_key=True)
    date = Column(DateTime, nullable=False, index=True)

    # Classification accuracy (tracked via manual review)
    parking_detection_accuracy = Column(Float)  # %
    parking_false_positives = Column(Integer, default=0)
    parking_false_negatives = Column(Integer, default=0)
    for_sale_detection_accuracy = Column(Float)  # %

    # Validation completeness
    http_check_success_rate = Column(Float)  # %
    ssl_verification_rate = Column(Float)  # %
    content_extraction_rate = Column(Float)  # %

    # Recheck efficiency
    coming_soon_to_live_conversions = Column(Integer, default=0)
    avg_time_to_launch_days = Column(Float)
    avg_rechecks_before_live = Column(Float)
    abandoned_domains_count = Column(Integer, default=0)

    # Volume stats
    total_validated = Column(Integer, default=0)
    total_rechecked = Column(Integer, default=0)

    __table_args__ = (
        Index('idx_validation_metrics_date', 'date'),
    )


class QualityMetrics(Base):
    """Track quality and business metrics (daily aggregates)"""
    __tablename__ = "quality_metrics"

    id = Column(Integer, primary_key=True)
    date = Column(DateTime, nullable=False, index=True)

    # Startup discovery rates
    high_quality_count = Column(Integer, default=0)  # Score >80
    medium_quality_count = Column(Integer, default=0)  # Score 60-80
    grade_a_plus_count = Column(Integer, default=0)  # Score >85 + Confidence >80%
    viable_startups_count = Column(Integer, default=0)  # Non-parking, score >50

    # Score distribution (JSON)
    score_distribution = Column(JSON)  # {"A+": 5, "A": 10, ...}

    # Confidence metrics
    avg_confidence_score = Column(Float)
    high_confidence_rate = Column(Float)  # % with >80% confidence
    low_confidence_rate = Column(Float)  # % with <40% confidence

    # Category distribution (JSON)
    category_distribution = Column(JSON)  # {"LAUNCHING_NOW": 12, ...}

    # Conversion funnel (JSON)
    conversion_funnel = Column(JSON)  # {"discovered": 100, "resolvable": 70, ...}

    # Totals
    total_domains = Column(Integer, default=0)
    parking_rejected = Column(Integer, default=0)
    for_sale_rejected = Column(Integer, default=0)

    __table_args__ = (
        Index('idx_quality_metrics_date', 'date'),
    )


class SystemMetrics(Base):
    """Track system health metrics (hourly snapshots)"""
    __tablename__ = "system_metrics"

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, nullable=False, default=func.now(), index=True)

    # Operational metrics
    api_response_time_avg_ms = Column(Float)
    api_response_time_p95_ms = Column(Float)
    api_response_time_p99_ms = Column(Float)
    db_query_time_avg_ms = Column(Float)
    ct_log_api_calls = Column(Integer, default=0)
    error_rate = Column(Float)  # %

    # Data growth
    total_domains_stored = Column(Integer, default=0)
    active_domains_count = Column(Integer, default=0)  # Being rechecked
    database_size_mb = Column(Float)

    # Resource utilization (if available)
    cpu_usage_percent = Column(Float)
    memory_usage_mb = Column(Float)
    disk_usage_percent = Column(Float)

    __table_args__ = (
        Index('idx_system_metrics_timestamp', 'timestamp'),
    )


class MetricAlert(Base):
    """Track metric alerts triggered"""
    __tablename__ = "metric_alerts"

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, nullable=False, default=func.now(), index=True)
    alert_type = Column(String(50), nullable=False)  # discovery, validation, quality, system
    severity = Column(String(20), nullable=False)  # INFO, WARNING, CRITICAL
    alert_key = Column(String(100), nullable=False)  # e.g., "zero_discoveries_6h"
    message = Column(String(500), nullable=False)
    metric_value = Column(Float)  # The value that triggered alert
    threshold_value = Column(Float)  # The threshold that was exceeded
    resolved_at = Column(DateTime)

    __table_args__ = (
        Index('idx_metric_alerts_timestamp', 'timestamp'),
        Index('idx_metric_alerts_severity', 'severity'),
        Index('idx_metric_alerts_resolved', 'resolved_at'),
    )
