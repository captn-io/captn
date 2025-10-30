import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from .base import NotificationCollector
from .telegram import TelegramNotifier
from .smtp import SMTPNotifier
from ..config import config
from ..common import get_docker_host_hostname

class NotificationManager:
    """
    Manages all notification channels and provides a unified interface for sending notifications.
    """

    def __init__(self):
        self.collector = NotificationCollector()
        self.notifiers = []
        self.update_stats = {
            "containers_processed": 0,
            "containers_updated": 0,
            "containers_failed": 0,
            "containers_skipped": 0,
            "update_details": [],
            "errors": [],
            "warnings": [],
            "start_time": None,
            "end_time": None
        }

        self._setup_notifiers()

    def _setup_notifiers(self):
        """Initialize configured notifiers."""
        if not config.notifiers.enabled:
            logging.debug("Notifications are disabled globally")
            return

        # Setup Telegram notifier
        if hasattr(config, "notifiers") and hasattr(config.notifiers, "telegram"):
            telegram_config = config.notifiers.telegram
            if telegram_config.enabled and telegram_config.token and telegram_config.chatId:
                telegram_notifier = TelegramNotifier(
                    token=telegram_config.token,
                    chatId=telegram_config.chatId,
                    enabled=telegram_config.enabled
                )
                self.notifiers.append(telegram_notifier)
                logging.debug("Telegram notifier initialized")
            elif telegram_config.enabled:
                logging.warning("Telegram notifications enabled but token or chatId not configured")

        # Setup SMTP notifier
        if hasattr(config, "notifiers") and hasattr(config.notifiers, "email"):
            email_config = config.notifiers.email
            if email_config.enabled and email_config.smtpServer and email_config.fromAddr and email_config.toAddr:
                smtp_notifier = SMTPNotifier(
                    smtp_server=email_config.smtpServer,
                    smtp_port=int(email_config.smtpPort),
                    username=email_config.username,
                    password=email_config.password,
                    from_addr=email_config.fromAddr,
                    to_addr=email_config.toAddr,
                    enabled=email_config.enabled,
                    timeout=int(email_config.timeout)
                )
                self.notifiers.append(smtp_notifier)
                logging.debug("SMTP notifier initialized")
            elif email_config.enabled:
                logging.warning("Email notifications enabled but smtpServer, fromAddr, or toAddr not configured")

    def add_update_detail(self, container_name: str, old_version: str, new_version: str, update_type: str, duration: float = None, status: str = "succeeded"):
        """Add an update to the statistics."""
        self.update_stats["update_details"].append({
            "container_name": container_name,
            "old_version": old_version,
            "new_version": new_version,
            "update_type": update_type,
            "duration": duration,
            "status": status
        })

        # Only increment containers_updated for successful updates
        if status == "succeeded":
            self.update_stats["containers_updated"] += 1

    def add_error(self, error_message: str):
        """Add an error to the statistics."""
        self.update_stats["errors"].append(error_message)
        self.update_stats["containers_failed"] += 1

    def add_warning(self, warning_message: str):
        """Add a warning to the statistics."""
        self.update_stats["warnings"].append(warning_message)

    def increment_processed(self):
        """Increment the processed containers counter."""
        self.update_stats["containers_processed"] += 1

    def increment_skipped(self):
        """Increment the skipped containers counter."""
        self.update_stats["containers_skipped"] += 1

    def set_start_time(self):
        """Set the start time of the update process."""
        self.update_stats["start_time"] = datetime.now()

    def set_end_time(self):
        """Set the end time of the update process."""
        self.update_stats["end_time"] = datetime.now()

    def send_update_report(self, dry_run: bool = False):
        """Send update report to all configured notifiers."""
        if not self.notifiers:
            logging.debug("No notifiers configured, skipping report")
            return

        # Set end time before sending report
        self.set_end_time()

        # Prepare update data
        update_data = {
            "hostname": get_docker_host_hostname(),
            "timestamp": datetime.now(),
            "dry_run": dry_run,
            **self.update_stats
        }

        # Send to each notifier
        for notifier in self.notifiers:
            try:
                if isinstance(notifier, TelegramNotifier):
                    message = notifier.format_update_report(update_data)
                    notifier.send([message])
                elif isinstance(notifier, SMTPNotifier):
                    message = notifier.format_update_report(update_data)
                    notifier.send([message])
                else:
                    # Generic fallback for other notifiers
                    notifier.send([f"Update report: {update_data}"])

            except Exception as e:
                logging.error(f"Failed to send notification via {type(notifier).__name__}: {e}")

    def reset_stats(self):
        """Reset update statistics."""
        self.update_stats = {
            "containers_processed": 0,
            "containers_updated": 0,
            "containers_failed": 0,
            "containers_skipped": 0,
            "update_details": [],
            "errors": [],
            "warnings": [],
            "start_time": None,
            "end_time": None
        }

# Global notification manager instance
notification_manager = NotificationManager()
