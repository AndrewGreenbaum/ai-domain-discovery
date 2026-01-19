#!/usr/bin/env python3
"""
Emergency Fix: Re-validate all domains with improved marketplace detection
This will catch domains like botbot.ai that slipped through
"""
import asyncio
import sqlite3
from agents.validation import ValidationAgent
from agents.scoring import ScoringAgent
from utils.logger import logger

DATABASE_PATH = "./aidomains.db"

async def revalidate_all_domains():
    """Re-validate ALL domains with improved detection"""

    print("\n" + "="*100)
    print(" 🔧 EMERGENCY FIX: Re-validating All Domains with Improved Detection")
    print("="*100 + "\n")

    # Connect to database
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # Initialize agents with NEW improved detection
    validator = ValidationAgent()
    scorer = ScoringAgent()

    try:
        # Get all domains
        cursor.execute("""
            SELECT id, domain, quality_score, is_parking, is_for_sale
            FROM domains
            ORDER BY quality_score DESC
        """)
        domains = cursor.fetchall()

        print(f"📊 Found {len(domains)} domains to re-validate\n")
        print("="*100)

        # Track statistics
        total_validated = 0
        newly_detected_for_sale = 0
        newly_detected_parking = 0
        score_decreased = []
        score_increased = []

        for i, (domain_id, domain, old_score, old_parking, old_for_sale) in enumerate(domains, 1):
            print(f"\n[{i}/{len(domains)}] {domain}")
            print(f"   Old Score: {old_score or 'N/A'}/100  |  Parking: {bool(old_parking)}  |  For Sale: {bool(old_for_sale)}")

            try:
                # Re-validate with NEW detection
                validation = await validator.validate_domain(domain)

                # Re-score with NEW penalties
                scoring = await scorer.calculate_scores(domain, validation)
                new_score = scoring.quality_score

                # Get final category
                final_category = scorer.categorize_domain(new_score, validation)

                # Check what changed
                newly_for_sale = validation.is_for_sale and not old_for_sale
                newly_parking = validation.is_parking and not old_parking

                if newly_for_sale:
                    print(f"   🚨 NOW DETECTED AS FOR-SALE! (was: {bool(old_for_sale)})")
                    newly_detected_for_sale += 1

                if newly_parking:
                    print(f"   🚨 NOW DETECTED AS PARKING! (was: {bool(old_parking)})")
                    newly_detected_parking += 1

                # Update database
                cursor.execute("""
                    UPDATE domains SET
                        quality_score = ?,
                        category = ?,
                        is_parking = ?,
                        is_for_sale = ?,
                        parking_confidence = ?,
                        is_redirect = ?,
                        redirect_target = ?,
                        title = ?,
                        meta_description = ?,
                        page_content_sample = ?,
                        is_live = ?,
                        http_status_code = ?
                    WHERE id = ?
                """, (
                    new_score,
                    final_category,
                    1 if validation.is_parking else 0,
                    1 if validation.is_for_sale else 0,
                    validation.parking_confidence,
                    1 if validation.is_redirect else 0,
                    validation.final_domain if hasattr(validation, 'final_domain') else None,
                    validation.title,
                    validation.meta_description,
                    validation.content_sample[:2000] if validation.content_sample else None,
                    1 if validation.is_live else 0,
                    validation.http_status_code,
                    domain_id
                ))

                conn.commit()
                total_validated += 1

                # Track score changes
                score_change = new_score - (old_score or 0)
                print(f"   New Score: {new_score}/100 ({score_change:+d})")

                if abs(score_change) >= 10:
                    change_info = {
                        'domain': domain,
                        'old_score': old_score or 0,
                        'new_score': new_score,
                        'change': score_change,
                        'for_sale': validation.is_for_sale,
                        'parking': validation.is_parking
                    }

                    if score_change < 0:
                        score_decreased.append(change_info)
                    else:
                        score_increased.append(change_info)

                # Show status
                status_parts = []
                if validation.is_live:
                    status_parts.append("✓ LIVE")
                else:
                    status_parts.append("✗ DOWN")

                if validation.is_for_sale:
                    status_parts.append("💰 FOR SALE")
                if validation.is_parking:
                    status_parts.append("🅿️ PARKING")
                if validation.is_redirect:
                    status_parts.append(f"→ {validation.final_domain}")

                print(f"   Status: {' | '.join(status_parts)}")

            except Exception as e:
                logger.error("revalidation_failed", domain=domain, error=str(e))
                print(f"   ❌ ERROR: {str(e)}")
                continue

        # Print Summary
        print("\n" + "="*100)
        print(" 📊 RE-VALIDATION SUMMARY")
        print("="*100)
        print(f" Total Domains: {len(domains)}")
        print(f" Successfully Re-validated: {total_validated}")
        print(f" Newly Detected FOR-SALE: {Colors.RED}{newly_detected_for_sale}{Colors.END}")
        print(f" Newly Detected PARKING: {Colors.YELLOW}{newly_detected_parking}{Colors.END}")
        print()

        if score_decreased:
            print(" 🔻 SCORES DECREASED (Fixed False Positives):")
            print()
            for item in sorted(score_decreased, key=lambda x: x['change']):
                marker = "💰" if item['for_sale'] else "🅿️" if item['parking'] else "⚠️"
                print(f"  {marker} {item['domain']}")
                print(f"     {item['old_score']} → {item['new_score']} ({item['change']:+d})")
                if item['for_sale']:
                    print(f"     Reason: Detected as FOR SALE")
                elif item['parking']:
                    print(f"     Reason: Detected as PARKING")
                else:
                    print(f"     Reason: Penalty applied")
                print()

        if score_increased:
            print(" 🔺 SCORES INCREASED:")
            print()
            for item in sorted(score_increased, key=lambda x: x['change'], reverse=True)[:5]:
                print(f"  {item['domain']}: {item['old_score']} → {item['new_score']} ({item['change']:+d})")

        print("="*100)
        print(" ✅ RE-VALIDATION COMPLETE")
        print("="*100 + "\n")

    finally:
        conn.close()

class Colors:
    RED = '\033[91m'
    YELLOW = '\033[93m'
    GREEN = '\033[92m'
    END = '\033[0m'

if __name__ == "__main__":
    asyncio.run(revalidate_all_domains())
