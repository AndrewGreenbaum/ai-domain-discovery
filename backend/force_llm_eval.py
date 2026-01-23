#!/usr/bin/env python3
"""Force LLM evaluation on existing live domains."""
import asyncio
import os
from sqlalchemy import create_engine, text
from services.llm_service import llm_service
from datetime import datetime

async def force_llm_evaluations():
    print("=== FORCING LLM EVALUATION ON 5 LIVE DOMAINS ===")
    print(f"LLM enabled: {llm_service.enabled}")
    print(f"LLM provider: {llm_service.provider}")
    print(f"Score range: {llm_service.UNCERTAIN_SCORE_MIN}-{llm_service.UNCERTAIN_SCORE_MAX}")
    print()

    # Use PostgreSQL from environment or default to docker connection
    db_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@db:5432/aidomains")
    # Convert async URL to sync for this script
    if "+asyncpg" in db_url:
        db_url = db_url.replace("+asyncpg", "")
    e = create_engine(db_url)
    print(f"Using database: {db_url[:50]}...")

    # Get 5 live domains that have not been LLM evaluated
    with e.connect() as c:
        result = c.execute(text("""
            SELECT domain, title, page_content_sample, quality_score
            FROM domains
            WHERE is_live = TRUE
            AND page_content_sample IS NOT NULL
            AND llm_evaluated_at IS NULL
            AND domain != 'aiai.ai'
            LIMIT 5
        """))
        domains = list(result)

    if not domains:
        print("No unevaluated live domains found!")
        return

    print(f"Found {len(domains)} domains to evaluate:")
    for d in domains:
        print(f"  - {d[0]} (score: {d[3]})")
    print()

    evaluated = 0
    for domain_row in domains:
        domain, title, content, score = domain_row
        print(f"Evaluating: {domain}...")

        try:
            result = await llm_service.evaluate_domain(
                domain=domain,
                title=title or "Unknown",
                description="",
                content_sample=content[:2000] if content else "",
                rule_based_score=score or 50,
                validation_data={"is_live": True, "has_ssl": True, "is_parking": False, "is_for_sale": False}
            )

            if result:
                print(f"  is_legitimate={result.get('is_legitimate_startup')}")
                print(f"  category={result.get('category')}")
                print(f"  suggested_score={result.get('suggested_score')}")
                print(f"  confidence={result.get('confidence')}")

                # Save to database
                with e.connect() as c:
                    c.execute(text("""
                        UPDATE domains SET
                            llm_evaluated_at = :eval_at,
                            llm_category = :category,
                            llm_is_legitimate = :is_legit,
                            llm_confidence = :confidence,
                            llm_suggested_score = :score
                        WHERE domain = :domain
                    """), {
                        "eval_at": datetime.utcnow().isoformat(),
                        "category": result.get("category"),
                        "is_legit": result.get("is_legitimate_startup"),
                        "confidence": result.get("confidence"),
                        "score": result.get("suggested_score"),
                        "domain": domain
                    })
                    c.commit()
                evaluated += 1
                print(f"  SAVED!")
            else:
                print(f"  ERROR: No result")
        except Exception as ex:
            print(f"  ERROR: {ex}")

    print(f"\n=== COMPLETED: {evaluated}/{len(domains)} domains evaluated ===")

    # Verify
    with e.connect() as c:
        result = c.execute(text("SELECT COUNT(*) FROM domains WHERE llm_evaluated_at IS NOT NULL"))
        total = result.fetchone()[0]
        print(f"Total LLM evaluations in database: {total}")

if __name__ == "__main__":
    asyncio.run(force_llm_evaluations())
