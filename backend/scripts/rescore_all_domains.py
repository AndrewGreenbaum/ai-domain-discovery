#!/usr/bin/env python3
"""
Re-score all existing domains with new Phase 1 & Phase 2 detection rules:
- Phase 1: Redirect detection (cap at 20/100)
- Phase 2: Parent company, company age, established signals (cap at 20/100)
"""
import asyncio
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from models.domain import Domain, Base
from agents.validation import ValidationAgent
from agents.scoring import ScoringAgent
from utils.logger import logger
from datetime import datetime

DATABASE_URL = "sqlite:///./aidomains.db"

async def rescore_all_domains():
    """Re-score all domains in database with new detection rules"""

    print("\n" + "="*80)
    print(" 🔄 RE-SCORING ALL DOMAINS - Phase 1 & 2 Detection")
    print("="*80 + "\n")

    # Setup database
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    # Initialize agents
    validator = ValidationAgent()
    scorer = ScoringAgent()

    try:
        # Get all domains
        stmt = select(Domain).where(Domain.status != 'deleted')
        result = db.execute(stmt)
        domains = result.scalars().all()

        print(f"📊 Found {len(domains)} domains to re-score\n")

        # Track changes
        total_rescored = 0
        total_penalized = 0
        changes = []

        for i, domain_record in enumerate(domains, 1):
            domain = domain_record.domain
            old_score = domain_record.quality_score

            print(f"[{i}/{len(domains)}] Processing: {domain}")
            print(f"   Old Score: {old_score}/100")

            try:
                # Re-validate domain
                validation = await validator.validate_domain(domain)

                # Re-score with new rules
                score_result = await scorer.calculate_scores(domain, validation)
                new_score = score_result.quality_score

                # Detect what changed
                penalty_reason = None
                if validation.is_redirect and new_score <= 20:
                    penalty_reason = f"Redirect to {validation.final_domain}"
                elif old_score > 20 and new_score <= 20:
                    # Check which Phase 2 detection triggered
                    page_content = validation.content_sample or ""
                    title = validation.title or ""

                    parent_company = scorer.investigator.extract_parent_company(page_content, title)
                    is_established, signals = scorer.investigator.detect_established_signals(page_content)
                    founding_year = scorer.investigator.extract_founding_year(page_content)
                    company_age = scorer.investigator.calculate_company_age(founded_year=founding_year)

                    if parent_company:
                        penalty_reason = f"Parent company: {parent_company}"
                    elif company_age and company_age > 3:
                        penalty_reason = f"Company age: {company_age} years"
                    elif is_established:
                        penalty_reason = f"Established signals: {', '.join(signals)}"

                # Update database
                domain_record.quality_score = new_score
                domain_record.domain_quality_score = score_result.domain_quality_score
                domain_record.launch_readiness_score = score_result.launch_readiness_score
                domain_record.content_originality_score = score_result.content_originality_score
                domain_record.professional_setup_score = score_result.professional_setup_score
                domain_record.early_signals_score = score_result.early_signals_score

                # Update redirect info
                domain_record.is_redirect = validation.is_redirect
                domain_record.final_url = validation.final_url
                domain_record.redirect_target = validation.final_domain

                # Commit changes
                db.commit()

                total_rescored += 1

                score_change = new_score - old_score
                print(f"   New Score: {new_score}/100 ({score_change:+d})")

                if penalty_reason:
                    print(f"   ⚠️  PENALTY: {penalty_reason}")
                    total_penalized += 1
                    changes.append({
                        'domain': domain,
                        'old_score': old_score,
                        'new_score': new_score,
                        'reason': penalty_reason
                    })
                elif abs(score_change) >= 10:
                    changes.append({
                        'domain': domain,
                        'old_score': old_score,
                        'new_score': new_score,
                        'reason': f"Score changed by {score_change:+d}"
                    })

                print()

            except Exception as e:
                logger.error("rescore_failed", domain=domain, error=str(e))
                print(f"   ❌ ERROR: {str(e)}\n")
                continue

        # Print summary
        print("=" * 80)
        print(" 📊 RE-SCORING SUMMARY")
        print("=" * 80)
        print(f" Total Domains: {len(domains)}")
        print(f" Successfully Re-scored: {total_rescored}")
        print(f" Penalized (Phase 1 & 2): {total_penalized}")
        print()

        if changes:
            print(" 🔍 SIGNIFICANT CHANGES:")
            print()
            for change in sorted(changes, key=lambda x: x['old_score'] - x['new_score'], reverse=True):
                score_diff = change['new_score'] - change['old_score']
                print(f"  {change['domain']}")
                print(f"    {change['old_score']} → {change['new_score']} ({score_diff:+d})")
                print(f"    Reason: {change['reason']}")
                print()

        print("=" * 80)
        print(" ✅ RE-SCORING COMPLETE")
        print("=" * 80 + "\n")

    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(rescore_all_domains())
