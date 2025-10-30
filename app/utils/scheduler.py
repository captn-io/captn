#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import time
import threading
import subprocess
import sys
from datetime import datetime, timedelta
from croniter import croniter

from .config import config

logger = logging.getLogger(__name__)


class CaptnScheduler:
    """
    A scheduler that runs captn at specified intervals using cron expressions.

    This class provides a thread-safe scheduler that can run captn automatically
    based on cron expressions. It supports runtime configuration changes and
    graceful shutdown handling.
    """

    def __init__(self):
        """
        Initialize the scheduler.

        Sets up the internal state for managing the scheduler thread and
        configuration changes.
        """
        self.running = False
        self.thread = None
        self.current_schedule = None
        self._lock = threading.Lock()

    def start(self):
        """
        Start the scheduler in a background thread.

        This method creates and starts a daemon thread that will run the
        scheduler loop. The scheduler will continue running until stopped.
        """
        if self.running:
            logger.warning("Scheduler is already running")
            return

        self.running = True
        self.thread = threading.Thread(target=self.run_scheduler, daemon=True)
        self.thread.start()
        logger.info("captn scheduler started")

    def stop(self):
        """
        Stop the scheduler.

        This method gracefully stops the scheduler by setting the running flag
        to False and waiting for the scheduler thread to complete.
        """
        with self._lock:
            self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("captn scheduler stopped")

    def run_scheduler(self):
        """
        Main scheduler loop.

        This method contains the main scheduling logic that calculates the next
        run time based on the cron expression and executes captn when appropriate.
        It also handles configuration reloading and schedule changes.
        """
        while self.running:
            try:
                # Reload configuration to detect changes
                config.reload()

                # Get current cron expression from config
                cron_expression = getattr(config.general, 'cronSchedule', '30 2 * * *')

                # Check if schedule has changed
                if cron_expression != self.current_schedule:
                    logger.info(f"Scheduler schedule changed to: {cron_expression}")
                    self.current_schedule = cron_expression

                # Calculate next run time
                now = datetime.now()
                try:
                    cron = croniter(cron_expression, now)
                    next_run = cron.get_next(datetime)

                    # Calculate sleep time
                    sleep_seconds = (next_run - now).total_seconds()

                    if sleep_seconds > 0:
                        logger.info(f"Next captn run scheduled for: {next_run.strftime('%Y-%m-%d %H:%M:%S')}")

                        # Sleep in smaller intervals to allow for graceful shutdown and config changes
                        while sleep_seconds > 0 and self.running:
                            # Check for config changes every 10 seconds
                            sleep_interval = min(sleep_seconds, 10)
                            time.sleep(sleep_interval)
                            sleep_seconds -= sleep_interval

                            # Reload config and check if schedule changed during sleep
                            config.reload()
                            current_cron = getattr(config.general, 'cronSchedule', '30 2 * * *')
                            if current_cron != self.current_schedule:
                                logger.info(f"Schedule changed during sleep to: {current_cron}")
                                self.current_schedule = current_cron
                                break  # Exit sleep loop to recalculate

                    if self.running:
                        # Execute captn
                        logger.info("Executing scheduled captn run")
                        self.execute_captn()

                except ValueError as e:
                    logger.error(f"Invalid cron expression '{cron_expression}': {e}")
                    # Sleep for 5 minutes before retrying
                    time.sleep(300)

            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")
                # Sleep for 1 minute before retrying
                time.sleep(60)

    def execute_captn(self):
        """
        Execute the captn command using subprocess to avoid signal handler issues.

        This method runs captn as a separate subprocess to avoid issues with
        signal handlers in threaded environments. It uses a timeout to prevent
        the scheduler from hanging indefinitely.
        """
        try:
            # Use subprocess to run captn in a separate process
            # This avoids signal handler issues in threads
            logger.info("Starting captn execution")

            # Run captn using the shell script to ensure proper locking
            result = subprocess.run([
                '/app/cli/captn.sh'
            ], timeout=18000)  # 5 hours timeout

            if result.returncode == 0:
                logger.info("captn execution completed successfully")
            else:
                logger.error(f"captn execution failed with return code {result.returncode}")

        except subprocess.TimeoutExpired:
            logger.error("captn execution timed out after 5 hours")
        except Exception as e:
            logger.error(f"Error executing captn: {e}")

    def get_next_run(self):
        """
        Get the next scheduled run time.

        This method calculates the next time captn will run based on the
        current cron schedule configuration.

        Returns:
            datetime or None: Next scheduled run time, or None if calculation fails
        """
        try:
            cron_expression = getattr(config.general, 'cronSchedule', '30 2 * * *')
            cron = croniter(cron_expression, datetime.now())
            return cron.get_next(datetime)
        except Exception as e:
            logger.error(f"Error calculating next run time: {e}")
            return None


# Global scheduler instance
_scheduler = None


def get_scheduler():
    """
    Get the global scheduler instance.

    This function implements a singleton pattern for the scheduler,
    ensuring only one scheduler instance exists throughout the application.

    Returns:
        CaptnScheduler: The global scheduler instance
    """
    global _scheduler
    if _scheduler is None:
        _scheduler = CaptnScheduler()
    return _scheduler


def start_scheduler():
    """
    Start the global scheduler.

    This function starts the global scheduler instance, which will begin
    running captn according to the configured cron schedule.
    """
    scheduler = get_scheduler()
    scheduler.start()


def stop_scheduler():
    """
    Stop the global scheduler.

    This function gracefully stops the global scheduler and cleans up
    the scheduler instance.
    """
    global _scheduler
    if _scheduler:
        _scheduler.stop()
        _scheduler = None


def is_scheduler_running():
    """
    Check if the scheduler is running.

    Returns:
        bool: True if the scheduler is currently running, False otherwise
    """
    return _scheduler is not None and _scheduler.running