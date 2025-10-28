import requests
import logging
import json
import os
from .base import BaseNotifier
from typing import List, Dict, Any
from datetime import datetime

TELEGRAM_MAX_LENGTH = 4096

class TelegramNotifier(BaseNotifier):
    def __init__(self, token: str, chatId: str, enabled: bool = True):
        """
        Initialize the Telegram notifier.

        Parameters:
            token (str): Telegram bot token
            chatId (str): Telegram chat ID to send messages to
            enabled (bool): Whether the notifier is enabled
        """
        super().__init__(enabled)
        self.token = token
        self.chatId = chatId
        self._profile_initialized = False
        self._state_file = "/app/conf/telegram-bot-state.json"

    def send(self, messages: List[str]):
        """
        Send messages via Telegram Bot API.

        This method sends notification messages to a Telegram chat using the
        Telegram Bot API. It handles message splitting for long messages
        and ensures the bot description is set.

        Parameters:
            messages (List[str]): List of messages to send
        """
        if not self.enabled:
            return

        if not messages:
            logging.debug("No messages to send via Telegram")
            return

        # Try to set bot description once per version
        self._ensure_bot_description_set()

        text = "\n".join(messages)
        for chunk in self._split_message(text):
            self._send_chunk(chunk)

    def _ensure_bot_description_set(self):
        """
        Ensure the bot description is set for the current captn version.

        This method checks if the bot description has been set for the current
        captn version and sets it if necessary. It uses a state file to track
        which versions have already been configured.
        """
        try:
            from app import __version__
            current_version = __version__
        except ImportError:
            logging.debug("Could not import captn version, skipping bot description setup")
            return

        # Check if description was already set for this version
        if self._is_description_set_for_version(current_version):
            return

        # Set the bot description
        if self._set_bot_description():
            self._mark_description_set_for_version(current_version)
            logging.info(f"Telegram bot description set for captn version {current_version}")
        else:
            logging.warning("Failed to set Telegram bot description")

    def ensure_bot_description_set(self) -> bool:
        """
        Manually ensure the bot description is set for the current captn version.

        Returns:
            bool: True if description was set or already set, False if failed
        """
        try:
            from app import __version__
            current_version = __version__
        except ImportError:
            logging.warning("Could not import captn version, cannot set bot description")
            return False

        # Check if description was already set for this version
        if self._is_description_set_for_version(current_version):
            logging.debug(f"Bot description already set for captn version {current_version}")
            return True

        # Set the bot description
        if self._set_bot_description():
            self._mark_description_set_for_version(current_version)
            logging.info(f"Telegram bot description set for captn version {current_version}")
            return True
        else:
            logging.warning("Failed to set Telegram bot description")
            return False

    def _is_description_set_for_version(self, version: str) -> bool:
        """Check if bot description was already set for the given version."""
        try:
            if not os.path.exists(self._state_file):
                return False

            with open(self._state_file, 'r') as f:
                state = json.load(f)

            return state.get("description_set_versions", {}).get(version, False)
        except (json.JSONDecodeError, IOError) as e:
            logging.debug(f"Error reading bot state file: {e}")
            return False

    def _mark_description_set_for_version(self, version: str):
        """Mark that bot description was set for the given version."""
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self._state_file), exist_ok=True)

            # Load existing state or create new
            state = {}
            if os.path.exists(self._state_file):
                try:
                    with open(self._state_file, 'r') as f:
                        state = json.load(f)
                except (json.JSONDecodeError, IOError):
                    state = {}

            # Initialize description_set_versions if not present
            if "description_set_versions" not in state:
                state["description_set_versions"] = {}

            # Mark this version as set
            state["description_set_versions"][version] = True

            # Write back to file
            with open(self._state_file, 'w') as f:
                json.dump(state, f, indent=2)

        except (json.JSONDecodeError, IOError) as e:
            logging.warning(f"Error writing bot state file: {e}")

    def set_bot_description(self, description: str = None) -> bool:
        """
        Set the bot description via Telegram Bot API.

        Args:
            description (str, optional): Description to set. If None, uses default description with version.

        Returns:
            bool: True if successful, False otherwise
        """
        if description is None:
            try:
                from app import __version__
                version = __version__
                description = f"Keeps you updated about performed container updates (v{version})"
            except ImportError:
                description = "Keeps you updated about performed container updates"

        url = f"https://api.telegram.org/bot{self.token}/setMyDescription"
        payload = {
            "description": description
        }

        try:
            resp = requests.post(url, json=payload, timeout=10)
            resp.raise_for_status()

            response_data = resp.json()
            if response_data.get("ok"):
                logging.debug("Telegram bot description set successfully")
                return True
            else:
                logging.error(f"Telegram API error setting description: {response_data.get('description', 'Unknown error')}")
                return False

        except requests.exceptions.Timeout:
            logging.error("Telegram set description failed: Request timeout")
            return False
        except requests.exceptions.RequestException as e:
            logging.error(f"Telegram set description failed: {e}")
            return False
        except Exception as e:
            logging.error(f"Telegram set description failed with unexpected error: {e}")
            return False

    def _set_bot_description(self, description: str = None) -> bool:
        """Internal method to set the bot description via Telegram Bot API."""
        return self.set_bot_description(description)

    def get_bot_info(self) -> Dict[str, Any]:
        """
        Get current bot information from Telegram Bot API.

        Returns:
            Dict containing bot information or empty dict if failed
        """
        url = f"https://api.telegram.org/bot{self.token}/getMe"

        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()

            response_data = resp.json()
            if response_data.get("ok"):
                return response_data.get("result", {})
            else:
                logging.error(f"Telegram API error getting bot info: {response_data.get('description', 'Unknown error')}")
                return {}

        except requests.exceptions.Timeout:
            logging.error("Telegram get bot info failed: Request timeout")
            return {}
        except requests.exceptions.RequestException as e:
            logging.error(f"Telegram get bot info failed: {e}")
            return {}
        except Exception as e:
            logging.error(f"Telegram get bot info failed with unexpected error: {e}")
            return {}

    def _split_message(self, text: str) -> List[str]:
        """
        Split text into chunks <= TELEGRAM_MAX_LENGTH.

        This method splits long messages into smaller chunks that fit within
        Telegram's message length limits.

        Parameters:
            text (str): Text to split

        Returns:
            List[str]: List of message chunks
        """
        return [text[i:i+TELEGRAM_MAX_LENGTH] for i in range(0, len(text), TELEGRAM_MAX_LENGTH)]

    def _send_chunk(self, chunk: str):
        """
        Send a single message chunk via Telegram Bot API.

        This method sends a single message chunk to the configured Telegram chat
        using the Telegram Bot API.

        Parameters:
            chunk (str): Message chunk to send
        """
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {
            "chat_id": self.chatId,
            "text": chunk,
            "parse_mode": "HTML"  # Use HTML for better formatting
        }

        try:
            resp = requests.post(url, json=payload, timeout=10)
            resp.raise_for_status()

            response_data = resp.json()
            if response_data.get("ok"):
                logging.debug(f"Telegram message sent successfully to chat {self.chatId}")
            else:
                logging.error(f"Telegram API error: {response_data.get('description', 'Unknown error')}")

        except requests.exceptions.Timeout:
            logging.error("Telegram notification failed: Request timeout")
        except requests.exceptions.RequestException as e:
            logging.error(f"Telegram notification failed: {e}")
        except Exception as e:
            logging.error(f"Telegram notification failed with unexpected error: {e}")

    def format_update_report(self, update_data: Dict[str, Any]) -> str:
        """
        Format update report for Telegram with essential information.

        Args:
            update_data: Dictionary containing update information with keys:
                - hostname: str
                - timestamp: datetime
                - dry_run: bool
                - containers_processed: int
                - containers_updated: int
                - containers_failed: int
                - containers_skipped: int
                - update_details: List[Dict] with container update details
                - errors: List[str] (optional)
                - warnings: List[str] (optional)

        Returns:
            Formatted HTML message for Telegram
        """
        hostname = update_data.get("hostname", "Unknown")
        timestamp = update_data.get("timestamp", datetime.now())
        dry_run = update_data.get("dry_run", False)
        containers_processed = update_data.get("containers_processed", 0)
        containers_updated = update_data.get("containers_updated", 0)
        containers_failed = update_data.get("containers_failed", 0)
        containers_skipped = update_data.get("containers_skipped", 0)
        update_details = update_data.get("update_details", [])
        errors = update_data.get("errors", [])
        warnings = update_data.get("warnings", [])
        start_time = update_data.get("start_time")
        end_time = update_data.get("end_time")

        # Format timestamp
        if isinstance(timestamp, datetime):
            timestamp_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
        else:
            timestamp_str = str(timestamp)

        # Build message
        lines = []

        # Header
        mode_indicator = "🩺 DRY RUN - " if dry_run else ""
        lines.append(f"<b>{mode_indicator}captn Report</b>")
        # lines.append(f"📅 {timestamp_str}")
        lines.append(f"🖥️ {hostname}")
        lines.append("")

        # Summary
        lines.append("<b>📊 Summary:</b>")
        lines.append(f"• Processed: {containers_processed}")
        lines.append(f"• Updated: {containers_updated}")
        lines.append(f"• Failed: {containers_failed}")
        lines.append(f"• Skipped: {containers_skipped}")

        # Add total duration if available
        if start_time and end_time:
            total_duration = (end_time - start_time).total_seconds()
            if total_duration < 60:
                duration_str = f"{total_duration:.1f}s"
            elif total_duration < 3600:
                duration_str = f"{total_duration / 60:.1f}m"
            else:
                duration_str = f"{total_duration / 3600:.1f}h"
            lines.append(f"• Duration: {duration_str}")

        lines.append("")

        # Separate successful and failed updates
        successful_updates = [detail for detail in update_details if detail.get("status") == "succeeded"]
        failed_updates = [detail for detail in update_details if detail.get("status") == "failed"]

        # Successful updates
        if successful_updates:
            lines.append("<b>✅ Successful Updates:</b>")
            for detail in successful_updates[:10]:  # Limit to first 10 successful updates
                container_name = detail.get("container_name", "Unknown")
                old_version = detail.get("old_version", "Unknown")
                new_version = detail.get("new_version", "Unknown")
                update_type = detail.get("update_type", "Unknown")
                duration = detail.get("duration")

                # Use emoji based on update type
                type_emoji = {
                    "major": "🚀",
                    "minor": "✨",
                    "patch": "🐞",
                    "build": "🏗️",
                    "digest": "📦"
                }.get(update_type, "⚪")

                # Add duration if available
                if duration is not None:
                    if duration < 60:
                        duration_str = f"{duration:.1f}s"
                    elif duration < 3600:
                        duration_str = f"{duration / 60:.1f}m"
                    else:
                        duration_str = f"{duration / 3600:.1f}h"
                else:
                    duration_str = "N/A"

                lines.append(f"")
                lines.append(f"<b>{container_name}</b>")
                lines.append(f"<code>{old_version} → {new_version}</code>")
                lines.append(f"<code>   {type_emoji} {update_type}</code>")
                lines.append(f"<code>   ⏱️ {duration_str}</code>")

            if len(successful_updates) > 10:
                lines.append(f"... and {len(successful_updates) - 10} more")
            lines.append("")

        # Failed updates
        if failed_updates:
            lines.append("<b>❌ Failed Updates:</b>")
            for detail in failed_updates[:10]:  # Limit to first 10 failed updates
                container_name = detail.get("container_name", "Unknown")
                old_version = detail.get("old_version", "Unknown")
                new_version = detail.get("new_version", "Unknown")
                update_type = detail.get("update_type", "Unknown")
                duration = detail.get("duration")

                # Use emoji based on update type
                type_emoji = {
                    "major": "🚀",
                    "minor": "✨",
                    "patch": "🐞",
                    "build": "🏗️",
                    "digest": "📦"
                }.get(update_type, "⚪")

                # Add duration if available
                if duration is not None:
                    if duration < 60:
                        duration_str = f"{duration:.1f}s"
                    elif duration < 3600:
                        duration_str = f"{duration / 60:.1f}m"
                    else:
                        duration_str = f"{duration / 3600:.1f}h"
                else:
                    duration_str = "N/A"

                lines.append(f"")
                lines.append(f"<b>{container_name}</b>")
                lines.append(f"<code>{old_version} → {new_version}</code>")
                lines.append(f"<code>   {type_emoji} {update_type}</code>")
                lines.append(f"<code>   ⏱️ {duration_str}</code>")

            if len(failed_updates) > 10:
                lines.append(f"... and {len(failed_updates) - 10} more")
            lines.append("")

        # Errors
        if errors:
            lines.append("<b>❌ Errors:</b>")
            for error in errors[:5]:  # Limit to first 5 errors
                lines.append(f"• {error}")
            if len(errors) > 5:
                lines.append(f"   ... and {len(errors) - 5} more")
            lines.append("")

        # Warnings
        if warnings:
            lines.append("<b>⚠️ Warnings:</b>")
            for warning in warnings[:3]:  # Limit to first 3 warnings
                lines.append(f"• {warning}")
            if len(warnings) > 3:
                lines.append(f"   ... and {len(warnings) - 3} more")
            lines.append("")

        # Footer
        if dry_run:
            lines.append("<i>This was a dry run - no actual changes were made.</i>")

        return "\n".join(lines)
