"""
Async job management for long-running commands.

Allows commands to run in background threads and query their status.
"""

import uuid
import time
import logging
from threading import Thread, Lock
from typing import Dict, Any, Optional, Callable, List
from enum import Enum

logger = logging.getLogger(__name__)


class JobStatus(Enum):
    """Job execution status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class JobManager:
    """
    Manage async background jobs for long-running commands
    """

    def __init__(
        self,
        max_jobs: int = 100,
        cleanup_interval: int = 3600
    ):
        """
        Initialize job manager

        Args:
            max_jobs: Maximum concurrent/stored jobs
            cleanup_interval: Seconds before completed jobs are auto-removed
        """
        self.jobs: Dict[str, Dict[str, Any]] = {}
        self.lock = Lock()
        self.max_jobs = max_jobs
        self.cleanup_interval = cleanup_interval

        # Start cleanup thread
        self.cleanup_thread = Thread(
            target=self._cleanup_old_jobs,
            daemon=True,
            name="job-cleanup"
        )
        self.cleanup_thread.start()

        logger.info(
            f"Job manager initialized: max_jobs={max_jobs}, "
            f"cleanup_interval={cleanup_interval}s"
        )

    def create_job(
        self,
        executor_fn: Callable[[Dict[str, Any]], Dict[str, Any]],
        params: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Create and start async job

        Args:
            executor_fn: Function to execute (should accept params dict)
            params: Parameters to pass to executor
            metadata: Optional metadata (tool name, user, etc.)

        Returns:
            job_id: Unique job identifier

        Raises:
            RuntimeError: If max jobs limit reached
        """
        with self.lock:
            if len(self.jobs) >= self.max_jobs:
                logger.error(f"Max jobs limit reached: {self.max_jobs}")
                raise RuntimeError(
                    f"Maximum concurrent jobs ({self.max_jobs}) reached. "
                    "Try again later or wait for existing jobs to complete."
                )

            job_id = str(uuid.uuid4())
            self.jobs[job_id] = {
                "id": job_id,
                "status": JobStatus.PENDING.value,
                "created_at": time.time(),
                "started_at": None,
                "completed_at": None,
                "result": None,
                "error": None,
                "metadata": metadata or {}
            }

        logger.info(f"Job created: {job_id}")

        # Start job in background thread
        thread = Thread(
            target=self._run_job,
            args=(job_id, executor_fn, params),
            daemon=True,
            name=f"job-{job_id[:8]}"
        )
        thread.start()

        return job_id

    def _run_job(
        self,
        job_id: str,
        executor_fn: Callable,
        params: Dict[str, Any]
    ):
        """
        Execute job in background thread

        Args:
            job_id: Job identifier
            executor_fn: Function to execute
            params: Parameters for function
        """
        # Mark as running
        with self.lock:
            if job_id not in self.jobs:
                logger.error(f"Job {job_id} disappeared before execution")
                return

            self.jobs[job_id]["status"] = JobStatus.RUNNING.value
            self.jobs[job_id]["started_at"] = time.time()

        logger.info(f"Job {job_id} started")

        try:
            # Execute the function
            result = executor_fn(params)

            # Mark as completed
            with self.lock:
                if job_id in self.jobs:
                    self.jobs[job_id]["status"] = JobStatus.COMPLETED.value
                    self.jobs[job_id]["completed_at"] = time.time()
                    self.jobs[job_id]["result"] = result

            logger.info(f"Job {job_id} completed successfully")

        except Exception as e:
            # Mark as failed
            error_msg = str(e)
            with self.lock:
                if job_id in self.jobs:
                    self.jobs[job_id]["status"] = JobStatus.FAILED.value
                    self.jobs[job_id]["completed_at"] = time.time()
                    self.jobs[job_id]["error"] = error_msg

            logger.error(f"Job {job_id} failed: {error_msg}")

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get job status and result

        Args:
            job_id: Job identifier

        Returns:
            Job data dictionary or None if not found
        """
        with self.lock:
            job = self.jobs.get(job_id)
            if job:
                # Calculate duration if applicable
                job_copy = job.copy()
                if job_copy["started_at"]:
                    end_time = job_copy["completed_at"] or time.time()
                    job_copy["duration_seconds"] = round(
                        end_time - job_copy["started_at"], 3
                    )
                return job_copy
            return None

    def list_jobs(
        self,
        status: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        List jobs, optionally filtered by status

        Args:
            status: Optional status filter (pending, running, completed, failed)
            limit: Maximum number of jobs to return

        Returns:
            List of job dictionaries
        """
        with self.lock:
            jobs = list(self.jobs.values())

            # Filter by status if requested
            if status:
                jobs = [j for j in jobs if j["status"] == status]

            # Sort by creation time (newest first)
            jobs.sort(key=lambda j: j["created_at"], reverse=True)

            # Apply limit
            return jobs[:limit]

    def delete_job(self, job_id: str) -> bool:
        """
        Delete job from manager

        Note: Does not cancel running jobs, just removes from tracking

        Args:
            job_id: Job identifier

        Returns:
            True if job was found and deleted, False otherwise
        """
        with self.lock:
            if job_id in self.jobs:
                status = self.jobs[job_id]["status"]
                del self.jobs[job_id]
                logger.info(f"Job {job_id} deleted (was {status})")
                return True
            return False

    def _cleanup_old_jobs(self):
        """Background thread to remove old completed jobs"""
        while True:
            try:
                time.sleep(300)  # Check every 5 minutes
                now = time.time()

                with self.lock:
                    to_delete = []

                    for job_id, job in self.jobs.items():
                        completed_at = job.get("completed_at")

                        # Remove jobs completed more than cleanup_interval ago
                        if completed_at and (now - completed_at) > self.cleanup_interval:
                            to_delete.append(job_id)

                    for job_id in to_delete:
                        status = self.jobs[job_id]["status"]
                        del self.jobs[job_id]
                        logger.debug(
                            f"Cleaned up old job: {job_id} (status={status})"
                        )

                    if to_delete:
                        logger.info(f"Cleaned up {len(to_delete)} old jobs")

            except Exception as e:
                logger.error(f"Error in job cleanup thread: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """
        Get job manager statistics

        Returns:
            Dictionary with current stats
        """
        with self.lock:
            status_counts = {}
            for job in self.jobs.values():
                status = job["status"]
                status_counts[status] = status_counts.get(status, 0) + 1

            return {
                "total_jobs": len(self.jobs),
                "max_jobs": self.max_jobs,
                "by_status": status_counts,
                "cleanup_interval": self.cleanup_interval
            }
