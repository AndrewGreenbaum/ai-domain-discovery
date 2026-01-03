"""Database models for domains and discovery runs"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime, Text, JSON, ForeignKey, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class Domain(Base):
    """Main domains table storing all discovered .ai domains"""
    __tablename__ = "domains"

    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    domain = Column(String(255), unique=True, nullable=False, index=True)

    # Discovery timestamps
    discovered_at = Column(DateTime, nullable=False, default=func.now(), index=True)
    first_seen_ct = Column(DateTime)
    ssl_issued_at = Column(DateTime)

    # Validation status
    status = Column(String(50), nullable=False, default='pending', index=True)
    last_checked = Column(DateTime)
    next_recheck = Column(DateTime, index=True)

    # Domain info
    is_live = Column(Boolean, default=False)
    http_status_code = Column(Integer)
    title = Column(String(500))
    meta_description = Column(Text)
    page_content_sample = Column(Text)

    # Classification
    category = Column(String(100), index=True)
    is_parking = Column(Boolean, default=False)
    is_for_sale = Column(Boolean, default=False)
    parking_confidence = Column(Float)

    # Scoring
    quality_score = Column(Integer, index=True)
    domain_quality_score = Column(Float)
    launch_readiness_score = Column(Float)
    content_originality_score = Column(Float)
    professional_setup_score = Column(Float)
    early_signals_score = Column(Float)

    # Metadata
    registrar = Column(String(255))
    created_date = Column(DateTime)
    ssl_issuer = Column(String(255))
    dns_records = Column(JSON)
    whois_data = Column(JSON)

    # Tracking
    recheck_count = Column(Integer, default=0)
    validation_errors = Column(JSON)
    notes = Column(Text)

    # Redirect detection (NEW - Phase 1)
    is_redirect = Column(Boolean, default=False, index=True)
    final_url = Column(String(500))
    redirect_target = Column(String(255), index=True)  # The domain it redirects to

    # Investigation data (from Investigator Agent) - COMMENTED OUT - NOT IN DB YET
    # investigated_at = Column(DateTime)
    # company_description = Column(Text)
    # company_tagline = Column(String(500))
    # product_category = Column(String(100))
    # business_model = Column(String(100))
    # target_market = Column(String(100))
    # team_members = Column(JSON)  # List of TeamMember objects
    # funding_info = Column(JSON)  # FundingInfo object
    # tech_stack = Column(JSON)    # TechStack object
    # social_proof = Column(JSON)  # SocialProof object
    # competitors = Column(JSON)   # List of competitor domains
    # investigation_confidence = Column(Float)

    # Parent company & age detection (NEW - Phase 2)
    parent_company = Column(String(255), index=True)  # If subdomain/product of larger company
    company_founded_year = Column(Integer)  # Extracted founding year
    company_age_years = Column(Integer)  # Calculated age
    is_established_company = Column(Boolean, default=False, index=True)  # Age > 3 years
    is_subdomain_product = Column(Boolean, default=False)  # Product of parent company

    # LLM Analysis (NEW - AI-powered evaluation)
    llm_evaluated_at = Column(DateTime)  # When LLM last evaluated
    llm_category = Column(String(100))  # AI-classified category
    llm_subcategory = Column(String(100))  # More specific classification
    llm_business_model = Column(String(100))  # B2B SaaS, B2C, etc.
    llm_target_audience = Column(String(255))  # Who they sell to
    llm_product_description = Column(Text)  # AI-generated description
    llm_quality_assessment = Column(String(20))  # high/medium/low
    llm_is_legitimate = Column(Boolean)  # AI verdict: real startup?
    llm_confidence = Column(Float)  # AI confidence score (0-1)
    llm_suggested_score = Column(Integer)  # Score suggested by AI
    llm_red_flags = Column(JSON)  # List of concerns
    llm_positive_signals = Column(JSON)  # List of good signs
    llm_reasoning = Column(Text)  # LLM reasoning explanation
    llm_cost_usd = Column(Float)  # Cost of LLM evaluation
    llm_raw_response = Column(JSON)  # Full LLM response for debugging

    # Enrichment data (from Enrichment Agent) - COMMENTED OUT - NOT IN DB YET
    # enriched_at = Column(DateTime)
    # screenshot_url = Column(String(500))  # S3 URL
    # screenshot_path = Column(String(500))  # S3 key
    # screenshot_status = Column(String(50))  # 'pending', 'captured', 'failed'
    # visual_analysis = Column(JSON)  # Visual analysis results
    # enrichment_confidence = Column(Float)

    # Timestamps
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class DiscoveryRun(Base):
    """Track each discovery job execution"""
    __tablename__ = "discovery_runs"

    id = Column(Integer, primary_key=True, index=True)
    run_at = Column(DateTime, nullable=False, default=func.now())
    domains_found = Column(Integer, default=0)
    domains_new = Column(Integer, default=0)
    domains_updated = Column(Integer, default=0)
    errors = Column(Integer, default=0)
    status = Column(String(50))  # 'running', 'completed', 'failed'
    duration_seconds = Column(Float)
    notes = Column(Text)
    created_at = Column(DateTime, default=func.now())


class Alert(Base):
    """Track sent alerts for high-quality domain launches"""
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    domain_id = Column(Integer, ForeignKey('domains.id'))
    alert_type = Column(String(100))  # 'high_quality_launch', 'surge_detection', etc.
    message = Column(Text)
    sent_at = Column(DateTime, default=func.now())
