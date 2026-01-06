#!/usr/bin/env python3
"""
Daily Domain Discovery Orchestration Script

Can be run:
1. Manually: python daily_discovery.py
2. With scheduler: python daily_discovery.py --schedule
3. One-time run: python daily_discovery.py --once
"""
import asyncio
import argparse
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from agents.planner import PlannerAgent
from agents.implementer import ImplementerAgent
from services.database import get_db_session, init_db
from utils.logger import logger


class DailyDiscoveryOrchestrator:
    """Orchestrates daily discovery operations"""

    def __init__(self):
        self.planner = PlannerAgent()
        self.implementer = ImplementerAgent()

    async def run_once(self, hours_back: int = 24):
        """Run discovery once"""
        logger.info("running_discovery_once", hours_back=hours_back)

        try:
            # Initialize database
            await init_db()

            # Run discovery
            async with get_db_session() as db:
                result = await self.implementer.orchestrate_discovery_run(db, hours_back)

            logger.info("discovery_run_completed", **result)

            # Generate report
            async with get_db_session() as db:
                report = await self.implementer.generate_daily_report(db)

            logger.info("daily_report", **report)

            print("\n" + "="*70)
            print("DAILY DISCOVERY COMPLETE")
            print("="*70)
            print(f"Domains Found: {result['domains_found']}")
            print(f"New Domains: {result['domains_new']}")
            print(f"Validated: {result['domains_validated']}")
            print(f"Duration: {result['duration_seconds']:.2f}s")
            print("\nPromising Startups:")
            for startup in report.get('promising_startups', [])[:5]:
                print(f"  • {startup['domain']} (score: {startup['quality_score']})")
            print("="*70)

            return result

        except Exception as e:
            logger.error("discovery_run_failed", error=str(e))
            raise

    async def run_scheduled(self):
        """Run with scheduler (3x daily)"""
        logger.info("starting_scheduled_discovery")

        try:
            # Initialize database
            await init_db()

            async def discovery_job():
                """Job to run on schedule"""
                try:
                    async with get_db_session() as db:
                        await self.implementer.orchestrate_discovery_run(db, hours_back=24)
                except Exception as e:
                    logger.error("scheduled_discovery_failed", error=str(e))

            async def recheck_job():
                """Job to recheck pending domains"""
                try:
                    async with get_db_session() as db:
                        await self.implementer.recheck_pending_domains(db, limit=50)
                except Exception as e:
                    logger.error("scheduled_recheck_failed", error=str(e))

            # Schedule jobs
            self.planner.schedule_daily_jobs(discovery_job)
            self.planner.schedule_recheck_jobs(recheck_job)

            # Start scheduler
            self.planner.start()

            logger.info("scheduler_started")
            print("\n" + "="*70)
            print("SCHEDULER STARTED")
            print("="*70)
            print("Discovery will run at: 9 AM, 2 PM, 8 PM UTC")
            print("Rechecks will run: Every hour")
            print("\nScheduled jobs:")
            for job in self.planner.get_scheduled_jobs():
                print(f"  • {job['name']}: {job['next_run']}")
            print("\nPress Ctrl+C to stop")
            print("="*70 + "\n")

            # Keep running
            try:
                while True:
                    await asyncio.sleep(60)
            except KeyboardInterrupt:
                logger.info("shutdown_requested")
                self.planner.shutdown()
                print("\nScheduler stopped.")

        except Exception as e:
            logger.error("scheduler_error", error=str(e))
            raise


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="AI Domain Discovery System")
    parser.add_argument(
        '--schedule',
        action='store_true',
        help='Run with scheduler (3x daily + hourly rechecks)'
    )
    parser.add_argument(
        '--once',
        action='store_true',
        help='Run discovery once and exit'
    )
    parser.add_argument(
        '--hours',
        type=int,
        default=24,
        help='Hours to look back (default: 24)'
    )

    args = parser.parse_args()

    orchestrator = DailyDiscoveryOrchestrator()

    if args.schedule:
        # Run with scheduler
        await orchestrator.run_scheduled()
    else:
        # Run once (default)
        await orchestrator.run_once(hours_back=args.hours)


if __name__ == "__main__":
    print("""
    ╔══════════════════════════════════════════════════════════╗
    ║                                                          ║
    ║          AI DOMAIN DISCOVERY SYSTEM                      ║
    ║                                                          ║
    ║   Discovers NEW .ai domains from Certificate            ║
    ║   Transparency logs in last 24-48 hours                 ║
    ║                                                          ║
    ╚══════════════════════════════════════════════════════════╝
    """)

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nShutdown requested. Goodbye!")
        sys.exit(0)
    except Exception as e:
        logger.error("fatal_error", error=str(e))
        print(f"\n\nFATAL ERROR: {e}")
        sys.exit(1)
