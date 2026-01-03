"""Pydantic schemas for API request/response validation"""
from pydantic import BaseModel, Field, ConfigDict, model_validator
from datetime import datetime, timezone
from typing import Optional, Dict, Any


class DomainBase(BaseModel):
    """Base domain schema"""
    domain: str
    status: str = "pending"


class DomainCreate(DomainBase):
    """Schema for creating a new domain"""
    first_seen_ct: Optional[datetime] = None
    ssl_issued_at: Optional[datetime] = None


class DomainUpdate(BaseModel):
    """Schema for updating a domain"""
    status: Optional[str] = None
    is_live: Optional[bool] = None
    http_status_code: Optional[int] = None
    title: Optional[str] = None
    meta_description: Optional[str] = None
    page_content_sample: Optional[str] = None
    category: Optional[str] = None
    is_parking: Optional[bool] = None
    is_for_sale: Optional[bool] = None
    parking_confidence: Optional[float] = None
    quality_score: Optional[int] = None
    last_checked: Optional[datetime] = None
    next_recheck: Optional[datetime] = None


class DomainResponse(DomainBase):
    """Schema for domain API response"""
    id: int
    discovered_at: datetime
    first_seen_ct: Optional[datetime] = None
    ssl_issued_at: Optional[datetime] = None
    last_checked: Optional[datetime] = None
    is_live: bool
    http_status_code: Optional[int] = None
    title: Optional[str] = None
    meta_description: Optional[str] = None
    page_content_sample: Optional[str] = None
    category: Optional[str] = None
    quality_score: Optional[int] = None
    domain_quality_score: Optional[float] = None
    launch_readiness_score: Optional[float] = None
    content_originality_score: Optional[float] = None
    professional_setup_score: Optional[float] = None
    early_signals_score: Optional[float] = None
    registrar: Optional[str] = None
    ssl_issuer: Optional[str] = None

    # Domain registration date (from WHOIS)
    created_date: Optional[datetime] = None
    domain_age_days: Optional[int] = None  # Calculated field

    # Parking and redirect detection
    is_parking: Optional[bool] = None
    is_for_sale: Optional[bool] = None
    is_redirect: Optional[bool] = None
    redirect_target: Optional[str] = None
    final_url: Optional[str] = None

    # Company age and parent company detection (Phase 2)
    parent_company: Optional[str] = None
    company_founded_year: Optional[int] = None
    company_age_years: Optional[int] = None
    is_established_company: Optional[bool] = None
    is_subdomain_product: Optional[bool] = None

    # LLM Analysis (AI-powered evaluation)
    llm_evaluated_at: Optional[datetime] = None
    llm_category: Optional[str] = None
    llm_subcategory: Optional[str] = None
    llm_business_model: Optional[str] = None
    llm_target_audience: Optional[str] = None
    llm_product_description: Optional[str] = None
    llm_quality_assessment: Optional[str] = None
    llm_is_legitimate: Optional[bool] = None
    llm_confidence: Optional[float] = None
    llm_suggested_score: Optional[int] = None
    llm_red_flags: Optional[list] = None
    llm_positive_signals: Optional[list] = None

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode='after')
    def calculate_domain_age(self):
        """Calculate domain_age_days from created_date if available"""
        if self.created_date and self.domain_age_days is None:
            # Handle both datetime and date objects
            if hasattr(self.created_date, 'date'):
                created = self.created_date.date()
            else:
                created = self.created_date
            today = datetime.utcnow().date()  # Use naive datetime
            self.domain_age_days = (today - created).days
        return self


class ValidationResult(BaseModel):
    """Result of domain validation"""
    domain: str
    is_live: bool
    http_status_code: Optional[int] = None
    has_ssl: bool = False
    title: Optional[str] = None
    meta_description: Optional[str] = None
    content_sample: Optional[str] = None
    is_parking: bool = False
    is_for_sale: bool = False
    parking_confidence: float = 0.0
    # NEW - Phase 1: Redirect detection
    is_redirect: bool = False
    final_url: Optional[str] = None
    final_domain: Optional[str] = None
    # NEW - Phase 3: Domain age filtering (WHOIS data)
    domain_created_date: Optional[str] = None  # WHOIS creation date
    domain_age_days: Optional[int] = None      # Age in days
    registrar: Optional[str] = None            # Domain registrar


class ScoringResult(BaseModel):
    """Result of domain scoring"""
    domain: str
    quality_score: int
    domain_quality_score: float
    launch_readiness_score: float
    content_originality_score: float
    professional_setup_score: float
    early_signals_score: float


class DiscoveryRunResponse(BaseModel):
    """Schema for discovery run response"""
    id: int
    run_at: datetime
    domains_found: int
    domains_new: int
    domains_updated: int
    errors: int
    status: str
    duration_seconds: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class DailyReportResponse(BaseModel):
    """Schema for daily report"""
    date: str
    total_discovered: int
    launching_now: int
    coming_soon: int
    just_registered: int
    rejected_parking: int
    promising_startups: list[DomainResponse]


class StatsResponse(BaseModel):
    """Today's statistics"""
    today_count: int
    live_count: int
    parking_count: int


# ============================================================================
# METRICS SCHEMAS
# ============================================================================

class DiscoveryMetricsResponse(BaseModel):
    """Discovery performance metrics"""
    run_id: int
    timestamp: datetime
    domains_discovered: int
    domains_new: int
    duplicate_rate: float
    avg_ssl_age_hours: Optional[float] = None
    discovery_latency_hours: Optional[float] = None
    validation_start_latency_minutes: Optional[float] = None
    full_pipeline_duration_minutes: Optional[float] = None
    resolvable_rate: Optional[float] = None
    live_on_discovery_rate: Optional[float] = None
    ssl_certificate_rate: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class ValidationMetricsResponse(BaseModel):
    """Validation accuracy metrics"""
    date: datetime
    parking_detection_accuracy: Optional[float] = None
    http_check_success_rate: Optional[float] = None
    ssl_verification_rate: Optional[float] = None
    content_extraction_rate: Optional[float] = None
    coming_soon_to_live_conversions: int
    avg_time_to_launch_days: Optional[float] = None
    total_validated: int

    model_config = ConfigDict(from_attributes=True)


class QualityMetricsResponse(BaseModel):
    """Quality and business metrics"""
    date: datetime
    high_quality_count: int
    medium_quality_count: int
    grade_a_plus_count: int
    viable_startups_count: int
    score_distribution: Optional[Dict[str, int]] = None
    avg_confidence_score: Optional[float] = None
    high_confidence_rate: Optional[float] = None
    category_distribution: Optional[Dict[str, int]] = None
    conversion_funnel: Optional[Dict[str, Any]] = None
    total_domains: int
    parking_rejected: int

    model_config = ConfigDict(from_attributes=True)


class SystemMetricsResponse(BaseModel):
    """System health metrics"""
    timestamp: datetime
    api_response_time_avg_ms: Optional[float] = None
    db_query_time_avg_ms: Optional[float] = None
    ct_log_api_calls: int
    error_rate: Optional[float] = None
    total_domains_stored: int
    active_domains_count: int
    database_size_mb: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class MetricAlertResponse(BaseModel):
    """Metric alert"""
    id: int
    timestamp: datetime
    alert_type: str
    severity: str
    alert_key: str
    message: str
    metric_value: Optional[float] = None
    threshold_value: Optional[float] = None
    resolved_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ComprehensiveDailyReport(BaseModel):
    """Enhanced daily report with all metrics"""
    date: str
    summary: Dict[str, Any]
    top_discoveries: list[DomainResponse]
    pipeline_performance: Dict[str, float]
    alerts_triggered: list[str]
    trends: Dict[str, str]
    quality_metrics: Optional[QualityMetricsResponse] = None
    validation_metrics: Optional[ValidationMetricsResponse] = None
    score_distribution: Optional[Dict[str, int]] = None
    category_distribution: Optional[Dict[str, int]] = None
    conversion_funnel: Optional[Dict[str, Any]] = None


# ============================================================================
# INVESTIGATOR AGENT SCHEMAS
# ============================================================================

class TeamMember(BaseModel):
    """Team member information"""
    name: str
    role: str
    linkedin_url: Optional[str] = None
    github_url: Optional[str] = None
    twitter_url: Optional[str] = None
    bio: Optional[str] = None


class FundingInfo(BaseModel):
    """Funding information"""
    has_funding: bool = False
    funding_stage: Optional[str] = None  # Seed, Series A, B, C, etc.
    funding_amount: Optional[str] = None  # "$5M", "$50M", etc.
    investors: list[str] = []
    funding_date: Optional[datetime] = None
    valuation: Optional[str] = None


class TechStack(BaseModel):
    """Technology stack information"""
    frontend: list[str] = []
    backend: list[str] = []
    analytics: list[str] = []
    infrastructure: list[str] = []
    ai_ml: list[str] = []
    hosting: Optional[str] = None


class SocialProof(BaseModel):
    """Social proof metrics"""
    twitter_followers: int = 0
    twitter_url: Optional[str] = None
    github_stars: int = 0
    github_url: Optional[str] = None
    product_hunt_votes: int = 0
    product_hunt_url: Optional[str] = None
    linkedin_followers: int = 0
    linkedin_url: Optional[str] = None
    app_store_rating: Optional[float] = None
    has_mobile_app: bool = False


class InvestigationResult(BaseModel):
    """Comprehensive investigation result"""
    domain: str
    investigated_at: datetime

    # Company information
    company_description: Optional[str] = None
    company_tagline: Optional[str] = None
    product_category: Optional[str] = None
    business_model: Optional[str] = None
    target_market: Optional[str] = None

    # Team information
    team_members: list[TeamMember] = []

    # Funding information
    funding_info: Optional[FundingInfo] = None

    # Technology stack
    tech_stack: Dict[str, list[str]] = {}

    # Social proof
    social_proof: Dict[str, Any] = {}

    # Competitors
    competitors: list[str] = []

    # Investigation metadata
    investigation_confidence: float = 0.0  # 0-100
    investigation_duration_seconds: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class InvestigationResponse(BaseModel):
    """API response for investigation"""
    domain: str
    investigation: InvestigationResult
    status: str = "completed"


# ============================================================================
# ENRICHMENT AGENT SCHEMAS
# ============================================================================

class SEOData(BaseModel):
    """SEO metadata"""
    meta_title: Optional[str] = None
    meta_title_length: int = 0
    meta_description: Optional[str] = None
    meta_description_length: int = 0
    h1_tags: list[str] = []
    h1_count: int = 0
    canonical_url: Optional[str] = None
    robots_meta: Optional[str] = None
    og_title: Optional[str] = None
    og_description: Optional[str] = None
    og_image: Optional[str] = None
    twitter_card: Optional[str] = None
    structured_data_types: list[str] = []
    has_sitemap: bool = False


class ContactInfo(BaseModel):
    """Contact information"""
    emails: list[str] = []
    phone_numbers: list[str] = []
    contact_form_url: Optional[str] = None
    has_live_chat: bool = False
    physical_address: Optional[str] = None
    support_email: Optional[str] = None


class ContentStructure(BaseModel):
    """Page content structure"""
    word_count: int = 0
    internal_links_count: int = 0
    external_links_count: int = 0
    images_count: int = 0
    videos_count: int = 0
    has_blog: bool = False
    language: Optional[str] = None
    cta_buttons: list[str] = []
    forms_count: int = 0


class PricingInfo(BaseModel):
    """Pricing intelligence"""
    has_pricing_page: bool = False
    pricing_page_url: Optional[str] = None
    pricing_tiers: list[str] = []
    has_free_trial: bool = False
    has_free_tier: bool = False
    pricing_model: Optional[str] = None  # SaaS, one-time, freemium, enterprise
    currency: Optional[str] = None
    starting_price: Optional[str] = None


class IntegrationData(BaseModel):
    """Third-party integrations detected"""
    payment_processors: list[str] = []
    analytics_platforms: list[str] = []
    marketing_tools: list[str] = []
    crm_tools: list[str] = []
    social_integrations: list[str] = []
    apis_mentioned: list[str] = []


class BrandAssets(BaseModel):
    """Brand assets and identity"""
    logo_url: Optional[str] = None
    favicon_url: Optional[str] = None
    primary_color: Optional[str] = None
    secondary_color: Optional[str] = None
    fonts: list[str] = []
    tagline: Optional[str] = None
    brand_keywords: list[str] = []


class PerformanceMetrics(BaseModel):
    """Page performance metrics"""
    page_load_time_ms: Optional[int] = None
    time_to_first_byte_ms: Optional[int] = None
    total_page_size_kb: Optional[int] = None
    requests_count: Optional[int] = None
    is_mobile_friendly: bool = False
    has_https: bool = False
    has_http2: bool = False


class EnrichmentResult(BaseModel):
    """Comprehensive enrichment result"""
    domain: str
    enriched_at: datetime

    # Screenshot
    screenshot_url: Optional[str] = None
    screenshot_path: Optional[str] = None
    screenshot_status: Optional[str] = None  # 'pending', 'captured', 'failed', 'disabled', 'error'
    visual_analysis: Optional[Dict[str, Any]] = None  # Visual analysis results

    # SEO Data
    seo_data: SEOData = SEOData()

    # Contact Info
    contact_info: ContactInfo = ContactInfo()

    # Content Structure
    content_structure: ContentStructure = ContentStructure()

    # Pricing Info
    pricing_info: PricingInfo = PricingInfo()

    # Integrations
    integrations: IntegrationData = IntegrationData()

    # Brand Assets
    brand_assets: BrandAssets = BrandAssets()

    # Performance
    performance_metrics: PerformanceMetrics = PerformanceMetrics()

    # Enrichment metadata
    enrichment_confidence: float = 0.0  # 0-100
    enrichment_duration_seconds: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class EnrichmentResponse(BaseModel):
    """API response for enrichment"""
    domain: str
    enrichment: EnrichmentResult
    status: str = "completed"
