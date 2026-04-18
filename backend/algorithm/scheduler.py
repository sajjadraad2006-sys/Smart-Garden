"""Time-based task scheduler using APScheduler.

B-04: Enhanced with daily scheduling, one-shot jobs, and job listing.
"""
import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger("agrimaster.scheduler")


class TaskScheduler:
    def __init__(self):
        self.scheduler = BackgroundScheduler(daemon=True)
        self._jobs = {}

    def start(self):
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("Scheduler started")

    def stop(self):
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            logger.info("Scheduler stopped")

    def add_interval_job(self, job_id: str, func, seconds: int, **kwargs):
        if job_id in self._jobs:
            self.scheduler.remove_job(job_id)
        job = self.scheduler.add_job(
            func, IntervalTrigger(seconds=seconds),
            id=job_id, replace_existing=True, **kwargs
        )
        self._jobs[job_id] = job
        logger.info(f"Scheduled job '{job_id}' every {seconds}s")

    # B-04: One-shot delayed job
    def schedule_once(self, func, delay_seconds: int,
                      job_id: str = None, **kwargs):
        """Schedule a function to run once after delay."""
        run_at = datetime.now() + timedelta(seconds=delay_seconds)
        job = self.scheduler.add_job(
            func, DateTrigger(run_date=run_at),
            id=job_id, replace_existing=True, kwargs=kwargs
        )
        if job_id:
            self._jobs[job_id] = job
        logger.info(f"[SCHEDULER] Job {job_id} scheduled in {delay_seconds}s")

    # B-04: Daily cron job
    def schedule_daily(self, func, hour: int, minute: int = 0,
                       job_id: str = None, **kwargs):
        """Schedule a function to run daily at specific time."""
        job = self.scheduler.add_job(
            func, CronTrigger(hour=hour, minute=minute),
            id=job_id, replace_existing=True, kwargs=kwargs
        )
        if job_id:
            self._jobs[job_id] = job
        logger.info(f"[SCHEDULER] Daily job {job_id} at {hour:02d}:{minute:02d}")

    def cancel(self, job_id: str):
        try:
            self.scheduler.remove_job(job_id)
            self._jobs.pop(job_id, None)
        except Exception:
            pass

    def remove_job(self, job_id: str):
        self.cancel(job_id)

    def get_jobs(self) -> list:
        return [{"id": j.id, "next_run": str(j.next_run_time)}
                for j in self.scheduler.get_jobs()]

    def get_pending_jobs(self) -> list:
        return self.get_jobs()
