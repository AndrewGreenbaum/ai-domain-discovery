"""PLANNER - Schedules and plans daily discovery operations"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, timezone, timedelta
from typing import Optional, Callable
import pytz
from utils.logger import logger
from config.settings import settings


class PlannerAgent:
    """Agent responsible for scheduling and planning daily discovery operations"""

    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone=pytz.UTC)
        self.discovery_schedule = settings.discovery_schedule
        self.is_running = False

    def schedule_daily_jobs(self, discovery_func: Callable):
        """
        Schedule discovery jobs to run 3 times daily (9 AM, 2 PM, 8 PM UTC)

        Args:
            discovery_func: Async function to call for discovery
        """
        logger.info("scheduling_daily_jobs", schedule=self.discovery_schedule)

        try:
            # Parse cron schedule (default: "0 9,14,20 * * *")
            # This means: minute=0, hour=9,14,20 (9 AM, 2 PM, 8 PM UTC)

            self.scheduler.add_job(
                discovery_func,
                trigger=CronTrigger.from_crontab(self.discovery_schedule, timezone=pytz.UTC),
                id='daily_discovery',
                name='Daily Domain Discovery',
                replace_existing=True,
                misfire_grace_time=3600,  # 1 hour grace period
            )

            logger.info("daily_jobs_scheduled")

        except Exception as e:
            logger.error("schedule_daily_jobs_failed", error=str(e))
            raise

    def schedule_recheck_jobs(self, recheck_func: Callable):
        """
        Schedule hourly recheck jobs for pending domains

        Args:
            recheck_func: Async function to call for rechecks
        """
        logger.info("scheduling_recheck_jobs")

        try:
            # Run every hour
            self.scheduler.add_job(
                recheck_func,
                trigger=CronTrigger(minute=0, timezone=pytz.UTC),  # Every hour at minute 0
                id='hourly_recheck',
                name='Hourly Domain Recheck',
                replace_existing=True,
                misfire_grace_time=600,  # 10 minute grace period
            )

            logger.info("recheck_jobs_scheduled")

        except Exception as e:
            logger.error("schedule_recheck_jobs_failed", error=str(e))
            raise

    def schedule_one_time_job(
        self,
        func: Callable,
        run_date: datetime,
        job_id: str,
        job_name: str
    ):
        """
        Schedule a one-time job

        Args:
            func: Function to execute
            run_date: When to run the job
            job_id: Unique job ID
            job_name: Human-readable name
        """
        try:
            self.scheduler.add_job(
                func,
                trigger='date',
                run_date=run_date,
                id=job_id,
                name=job_name,
                replace_existing=True,
            )

            logger.info(
                "one_time_job_scheduled",
                job_id=job_id,
                run_date=run_date.isoformat()
            )

        except Exception as e:
            logger.error("schedule_one_time_job_failed", error=str(e))
            raise

    def plan_recheck_schedule(self, domain_status: str) -> datetime:
        """
        Plan next recheck time based on domain status

        Args:
            domain_status: Current status of domain

        Returns:
            Datetime for next recheck
        """
        intervals = {
            "not_live_yet": timedelta(hours=6),
            "coming_soon": timedelta(hours=24),
            "under_construction": timedelta(hours=48),
            "soft_launch": timedelta(hours=24),
            "pending": timedelta(hours=12),
        }

        interval = intervals.get(domain_status, timedelta(hours=24))
        next_check = datetime.utcnow() + interval  # Use naive datetime for DB

        logger.debug(
            "recheck_planned",
            status=domain_status,
            next_check=next_check.isoformat()
        )

        return next_check

    def start(self):
        """Start the scheduler"""
        if not self.is_running:
            self.scheduler.start()
            self.is_running = True
            logger.info("scheduler_started")

    def shutdown(self):
        """Shutdown the scheduler"""
        if self.is_running:
            self.scheduler.shutdown(wait=True)
            self.is_running = False
            logger.info("scheduler_shutdown")

    def get_scheduled_jobs(self) -> list:
        """Get list of currently scheduled jobs"""
        return [
            {
                "id": job.id,
                "name": job.name,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger),
            }
            for job in self.scheduler.get_jobs()
        ]

    def remove_job(self, job_id: str):
        """Remove a scheduled job"""
        try:
            self.scheduler.remove_job(job_id)
            logger.info("job_removed", job_id=job_id)
        except Exception as e:
            logger.error("remove_job_failed", job_id=job_id, error=str(e))
