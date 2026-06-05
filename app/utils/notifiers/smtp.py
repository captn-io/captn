import smtplib
import logging
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from .base import BaseNotifier
from .report import resolve_status_banner, format_duration
from typing import List, Dict, Any
from datetime import datetime
from app import __version__

CAPTN_PRIMARY = "#0066cc"
CAPTN_ACCENT = "#0db7ed"
CAPTN_HEADER_BG = "#f0f8fc"

_MAIL_ICONS = {
    "summary": (
        '<rect x="2" y="9" width="3" height="5" rx="0.5" fill="currentColor"/>'
        '<rect x="6.5" y="5" width="3" height="9" rx="0.5" fill="currentColor"/>'
        '<rect x="11" y="2" width="3" height="12" rx="0.5" fill="currentColor"/>'
    ),
    "package": (
        '<path d="M2 5l6-3 6 3v6l-6 3-6-3V5z" stroke="currentColor" stroke-width="1.5" fill="none" stroke-linejoin="round"/>'
        '<path d="M8 8v6M2 5l6 3 6-3" stroke="currentColor" stroke-width="1.5" fill="none" stroke-linejoin="round"/>'
    ),
    "check-circle": (
        '<circle cx="8" cy="8" r="6.25" stroke="currentColor" stroke-width="1.5" fill="none"/>'
        '<path d="M5.5 8l1.75 1.75L10.5 6.25" stroke="currentColor" stroke-width="1.5" fill="none" stroke-linecap="round" stroke-linejoin="round"/>'
    ),
    "x-circle": (
        '<circle cx="8" cy="8" r="6.25" stroke="currentColor" stroke-width="1.5" fill="none"/>'
        '<path d="M6 6l4 4M10 6l-4 4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>'
    ),
    "skip": (
        '<g transform="matrix(-1 0 0 -1 16 16)">'
        '<path d="M3 4h7a3 3 0 0 1 0 6H6" stroke="currentColor" stroke-width="1.5" fill="none" stroke-linecap="round" stroke-linejoin="round"/>'
        '<path d="M6 7L3 4l3-3" stroke="currentColor" stroke-width="1.5" fill="none" stroke-linecap="round" stroke-linejoin="round"/>'
        '<path d="M11 10h2v4h-2" stroke="currentColor" stroke-width="1.5" fill="none" stroke-linecap="round"/>'
        '</g>'
    ),
    "alert": (
        '<path d="M8 2.5L14 13.5H2L8 2.5z" stroke="currentColor" stroke-width="1.5" fill="none" stroke-linejoin="round"/>'
        '<path d="M8 6.5v3.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>'
        '<circle cx="8" cy="11.75" r="0.75" fill="currentColor"/>'
    ),
    "info": (
        '<circle cx="8" cy="8" r="6.25" stroke="currentColor" stroke-width="1.5" fill="none"/>'
        '<path d="M8 7v4.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>'
        '<circle cx="8" cy="5.25" r="0.75" fill="currentColor"/>'
    ),
    "clock": (
        '<circle cx="8" cy="8" r="6.25" stroke="currentColor" stroke-width="1.5" fill="none"/>'
        '<path d="M8 4.5V8l2.5 2" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>'
    ),
    "test": (
        '<path d="M5.5 3.5h5l1 3H4.5l1-3z" stroke="currentColor" stroke-width="1.5" fill="none" stroke-linejoin="round"/>'
        '<path d="M4.5 6.5h7v5a1.5 1.5 0 0 1-1.5 1.5H6a1.5 1.5 0 0 1-1.5-1.5v-5z" stroke="currentColor" stroke-width="1.5" fill="none" stroke-linejoin="round"/>'
        '<path d="M6.5 9.5h3" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>'
    ),
}

_STATUS_ICON_KEY = {
    "Issues Detected": "alert",
    "Updates Successful": "check-circle",
    "Containers Skipped": "skip",
    "No Containers Checked": "info",
}


def _mail_icon(name: str, size: int = 16) -> str:
    """Render a monotone inline SVG icon for HTML email."""
    paths = _MAIL_ICONS.get(name)
    if not paths:
        return ""
    return (
        f'<span class="mail-icon" style="display:inline-block;vertical-align:-2px;margin-right:6px;line-height:0;">'
        f'<svg width="{size}" height="{size}" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
        f"{paths}</svg></span>"
    )


def _section_heading(level: int, icon: str, title: str, color: str = None, extra_style: str = None) -> str:
    tag = f"h{level}"
    styles = []
    if color:
        styles.append(f"color: {color}")
    if extra_style:
        styles.append(extra_style)
    style_attr = f' style="{"; ".join(styles)}"' if styles else ""
    return f"<{tag}{style_attr}>{_mail_icon(icon)}{title}</{tag}>"


class SMTPNotifier(BaseNotifier):
    """
    SMTP-based email notifier for captn update reports.

    This notifier sends detailed HTML email reports about container updates
    with professional formatting, embedded logo, and comprehensive statistics.
    """

    def __init__(self, smtp_server: str, smtp_port: int, username: str, password: str,
                 from_addr: str, to_addr: str, enabled: bool = True, timeout: int = 30):
        """
        Initialize the SMTP notifier.

        Parameters:
            smtp_server (str): SMTP server address
            smtp_port (int): SMTP server port
            username (str): SMTP username
            password (str): SMTP password
            from_addr (str): Sender email address
            to_addr (str): Recipient email address
            enabled (bool): Whether the notifier is enabled
            timeout (int): Connection timeout in seconds
        """
        super().__init__(enabled)
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.from_addr = from_addr
        self.to_addr = to_addr
        self.timeout = timeout
        self.logo_path = "/app/assets/icons/favicon.png"

    def send(self, messages: List[str]):
        """
        Send email notification via SMTP.

        Parameters:
            messages (List[str]): List of messages to send (typically one HTML message)
        """
        if not self.enabled:
            return

        if not messages:
            logging.debug("No messages to send via SMTP")
            return

        try:
            # Create message
            msg = MIMEMultipart('related')
            msg['From'] = self.from_addr
            msg['To'] = self.to_addr
            msg['Subject'] = messages[0].split('<title>')[1].split('</title>')[0] if '<title>' in messages[0] else "captn Update Report"

            # Create alternative container for HTML and text
            msg_alternative = MIMEMultipart('alternative')
            msg.attach(msg_alternative)

            # Add HTML content
            html_content = messages[0]
            msg_alternative.attach(MIMEText(html_content, 'html', 'utf-8'))

            # Try to add logo as attachment if it exists (optional)
            self._attach_logo(msg)

            # Send email
            self._send_email(msg)

        except Exception as e:
            logging.error(f"Failed to send email notification: {e}")

    def _attach_logo(self, msg):
        """Attach logo to email message if available."""
        if not os.path.exists(self.logo_path):
            return

        try:
            with open(self.logo_path, 'rb') as f:
                logo_data = f.read()

            logo_attachment = MIMEImage(logo_data)
            logo_attachment.add_header('Content-ID', '<logo>')
            logo_attachment.add_header('Content-Disposition', 'inline', filename='captn-logo.png')
            msg.attach(logo_attachment)
            logging.debug("Logo attached successfully to email")
        except Exception as e:
            logging.warning(f"Could not attach logo: {e}")
            # Continue without logo rather than failing

    def _send_email(self, msg):
        """Send email via SMTP with proper error handling."""
        try:
            # Handle SSL (port 465) and TLS (port 587) differently
            if self.smtp_port == 465:  # SSL
                logging.debug(f"Connecting to {self.smtp_server}:{self.smtp_port} using SSL (timeout: {self.timeout}s)")
                with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port, timeout=self.timeout) as server:
                    logging.debug("SSL connection established")
                    if self.username and self.password:
                        logging.debug("Authenticating with SMTP server")
                        server.login(self.username, self.password)
                        logging.debug("Authentication successful")
                    logging.debug("Sending email message")
                    server.send_message(msg)
                    logging.debug(f"Email sent successfully to {self.to_addr}")
            else:  # TLS (port 587) or other ports
                logging.debug(f"Connecting to {self.smtp_server}:{self.smtp_port} using TLS (timeout: {self.timeout}s)")
                with smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=self.timeout) as server:
                    logging.debug("SMTP connection established")
                    if self.smtp_port == 587:  # TLS
                        logging.debug("Starting TLS connection")
                        server.starttls()
                        logging.debug("TLS connection established")
                    if self.username and self.password:
                        logging.debug("Authenticating with SMTP server")
                        server.login(self.username, self.password)
                        logging.debug("Authentication successful")
                    logging.debug("Sending email message")
                    server.send_message(msg)
                    logging.debug(f"Email sent successfully to {self.to_addr}")
        except smtplib.SMTPAuthenticationError as e:
            logging.error(f"SMTP authentication failed: {e}")
            raise
        except smtplib.SMTPRecipientsRefused as e:
            logging.error(f"SMTP recipients refused: {e}")
            raise
        except smtplib.SMTPServerDisconnected as e:
            logging.error(f"SMTP server disconnected: {e}")
            raise
        except smtplib.SMTPConnectError as e:
            logging.error(f"SMTP connection error: {e}")
            raise
        except smtplib.SMTPException as e:
            logging.error(f"SMTP error sending email: {e}")
            raise
        except Exception as e:
            logging.error(f"Unexpected error sending email: {e}")
            raise

    def format_update_report(self, update_data: Dict[str, Any]) -> str:
        """
        Format update report as HTML email with detailed layout.

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
                - start_time: datetime (optional)
                - end_time: datetime (optional)

        Returns:
            Formatted HTML email content
        """
        hostname = update_data.get("hostname", "Unknown")
        timestamp = update_data.get("timestamp", datetime.now())
        dry_run = update_data.get("dry_run", False)
        containers_processed = update_data.get("containers_processed", 0)
        containers_updated = update_data.get("containers_updated", 0)
        containers_failed = update_data.get("containers_failed", 0)
        containers_skipped = update_data.get("containers_skipped", 0)
        update_details = update_data.get("update_details", [])
        skip_details = update_data.get("skip_details", [])
        errors = update_data.get("errors", [])
        warnings = update_data.get("warnings", [])
        start_time = update_data.get("start_time")
        end_time = update_data.get("end_time")

        # Format timestamp
        if isinstance(timestamp, datetime):
            timestamp_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
        else:
            timestamp_str = str(timestamp)

        duration_str = format_duration(start_time, end_time)

        # Separate successful and failed updates
        successful_updates = [detail for detail in update_details if detail.get("status") == "succeeded"]
        failed_updates = [detail for detail in update_details if detail.get("status") == "failed"]

        stats = {
            "containers_processed": containers_processed,
            "containers_updated": containers_updated,
            "containers_failed": containers_failed,
            "containers_skipped": containers_skipped,
            "errors": errors,
        }
        status_banner = resolve_status_banner(stats)
        if status_banner:
            status_text, status_icon, status_color = status_banner
        else:
            status_text = status_icon = status_color = None

        # Build HTML content
        html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>captn v{__version__} Update Report - {hostname}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f8f9fa;
        }}
        .container {{
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            overflow: hidden;
        }}
        .header {{
            background: {CAPTN_HEADER_BG};
            color: #212529;
            padding: 30px;
            text-align: center;
            border-bottom: 1px solid #c5e0f5;
        }}
        .logo {{
            width: 48px;
            height: 48px;
            margin-bottom: 15px;
        }}
        .header h1 {{
            margin: 0;
            font-size: 28px;
            font-weight: 600;
            color: #212529;
        }}
        .header .subtitle {{
            margin: 5px 0 0 0;
            font-size: 16px;
            color: #495057;
        }}
        .header .meta {{
            margin: 10px 0 0 0;
            font-size: 14px;
            color: #6c757d;
        }}
        .status-banner {{
            background: {status_color};
            color: white;
            padding: 15px 30px;
            text-align: center;
            font-size: 18px;
            font-weight: 600;
        }}
        .content {{
            padding: 30px;
        }}
        .summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        .stat-card {{
            background: #f8f9fa;
            border-radius: 8px;
            padding: 20px;
            text-align: center;
            border-left: 4px solid {CAPTN_PRIMARY};
        }}
        .stat-number {{
            font-size: 32px;
            font-weight: 700;
            color: {CAPTN_PRIMARY};
            margin: 0;
        }}
        .stat-label {{
            font-size: 14px;
            color: #6c757d;
            margin: 5px 0 0 0;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .section {{
            margin-bottom: 30px;
        }}
        .section h2 {{
            color: #495057;
            border-bottom: 2px solid #e9ecef;
            padding-bottom: 10px;
            margin-bottom: 20px;
            font-size: 20px;
        }}
        .section h3 {{
            color: #495057;
            font-size: 16px;
            margin-bottom: 15px;
        }}
        .mail-icon {{
            color: inherit;
        }}
        .list-marker {{
            display: inline-block;
            width: 6px;
            height: 6px;
            background: currentColor;
            border-radius: 1px;
            margin-right: 10px;
            vertical-align: middle;
            opacity: 0.55;
        }}
        .update-item {{
            background: #f8f9fa;
            border-radius: 6px;
            padding: 15px;
            margin-bottom: 10px;
            border-left: 4px solid #28a745;
        }}
        .update-item.failed {{
            border-left-color: #dc3545;
            background: #fff5f5;
        }}
        .update-item.skipped {{
            border-left-color: #ffc107;
            background: #fffbf0;
        }}
        .container-name {{
            font-weight: 600;
            font-size: 16px;
            color: #495057;
            margin-bottom: 5px;
        }}
        .version-info {{
            font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
            background: #e9ecef;
            padding: 8px 12px;
            border-radius: 4px;
            margin: 5px 0;
            font-size: 14px;
        }}
        .update-meta {{
            display: flex;
            gap: 15px;
            margin-top: 8px;
            font-size: 14px;
            color: #6c757d;
        }}
        .update-type {{
            background: {CAPTN_PRIMARY};
            color: white;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 500;
        }}
        .update-type.major {{ background: #dc3545; }}
        .update-type.minor {{ background: #fd7e14; }}
        .update-type.patch {{ background: #28a745; }}
        .update-type.build {{ background: #17a2b8; }}
        .update-type.digest {{ background: {CAPTN_ACCENT}; }}
        .error-list, .warning-list {{
            background: #fff5f5;
            border: 1px solid #f5c6cb;
            border-radius: 6px;
            padding: 15px;
            margin-top: 10px;
        }}
        .warning-list {{
            background: #fffbf0;
            border-color: #ffeaa7;
        }}
        .error-item, .warning-item {{
            padding: 8px 0;
            border-bottom: 1px solid #f5c6cb;
        }}
        .error-item:last-child, .warning-item:last-child {{
            border-bottom: none;
        }}
        .footer {{
            background: #f8f9fa;
            padding: 20px 30px;
            text-align: center;
            color: #6c757d;
            font-size: 14px;
            border-top: 1px solid #e9ecef;
        }}
        .dry-run-notice {{
            background: #e6f4fc;
            border: 1px solid #99d6f5;
            border-radius: 6px;
            padding: 15px;
            margin: 20px 0;
            text-align: center;
            color: {CAPTN_PRIMARY};
        }}
        .no-updates {{
            text-align: center;
            color: #6c757d;
            font-style: italic;
            padding: 40px 20px;
        }}
        @media (max-width: 600px) {{
            .summary {{
                grid-template-columns: repeat(2, 1fr);
            }}
            .update-meta {{
                flex-direction: column;
                gap: 5px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <img src="cid:logo" alt="captn Logo" class="logo" onerror="this.style.display='none'">
            <h1>captn</h1>
            <p class="subtitle">Container Update Report</p>
            <p class="meta">{hostname} • {timestamp_str}</p>
        </div>

        {self._generate_status_banner(status_icon, status_text, status_color)}

        <div class="content">
            {self._generate_dry_run_notice(dry_run)}

            <div class="section">
                <h2>{_mail_icon("summary")}Summary</h2>
                <div class="summary">
                    <div class="stat-card">
                        <div class="stat-number">{containers_processed}</div>
                        <div class="stat-label">Checked</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number" style="color: #28a745;">{containers_updated}</div>
                        <div class="stat-label">Updated</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number" style="color: #dc3545;">{containers_failed}</div>
                        <div class="stat-label">Failed</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number" style="color: #ffc107;">{containers_skipped}</div>
                        <div class="stat-label">Skipped</div>
                    </div>
                    {f'<div class="stat-card"><div class="stat-number" style="color: #17a2b8;">{duration_str}</div><div class="stat-label">Duration</div></div>' if duration_str else ''}
                </div>
            </div>

            {self._generate_updates_section(successful_updates, failed_updates)}
            {self._generate_skipped_section(skip_details)}
            {self._generate_errors_section(errors)}
            {self._generate_warnings_section(warnings)}
        </div>

        <div class="footer">
            <p>Generated by captn v{__version__} • {timestamp_str}</p>
            <p style="margin: 5px 0 0 0; font-size: 12px; opacity: 0.8;">
                This is an automated report. Please do not reply to this email.
            </p>
        </div>
    </div>
</body>
</html>
"""

        return html

    def _generate_status_banner(self, status_icon: str, status_text: str, status_color: str) -> str:
        """Generate status banner HTML, or empty string when omitted."""
        del status_icon  # email uses monotone SVG icons, not shared emoji labels
        if not status_text:
            return ""
        icon_key = _STATUS_ICON_KEY.get(status_text, "info")
        return f"""
        <div class="status-banner">
            {_mail_icon(icon_key, size=18)}{status_text}
        </div>
        """

    def _generate_dry_run_notice(self, dry_run: bool) -> str:
        """Generate dry run notice if applicable."""
        if dry_run:
            return f"""
            <div class="dry-run-notice">
                <strong>{_mail_icon("test")}DRY RUN MODE</strong><br>
                This was a test run - no actual changes were made to containers.
            </div>
            """
        return ""

    def _generate_updates_section(self, successful_updates: List[Dict], failed_updates: List[Dict]) -> str:
        """Generate the updates section with successful and failed updates."""
        if not successful_updates and not failed_updates:
            return f"""
            <div class="section">
                <h2>{_mail_icon("package")}Container Updates</h2>
                <div class="no-updates">
                    No container updates were performed.
                </div>
            </div>
            """

        html = f'<div class="section"><h2>{_mail_icon("package")}Container Updates</h2>'

        # Successful updates
        if successful_updates:
            html += _section_heading(3, "check-circle", "Successful Updates", "#28a745")
            for detail in successful_updates:
                html += self._format_update_item(detail, "success")

        # Failed updates
        if failed_updates:
            html += _section_heading(3, "x-circle", "Failed Updates", "#dc3545", "margin: 30px 0 15px 0")
            for detail in failed_updates:
                html += self._format_update_item(detail, "failed")

        html += '</div>'
        return html

    def _generate_skipped_section(self, skip_details: List[Dict]) -> str:
        """Generate skipped containers section if there are any."""
        if not skip_details:
            return ""

        items = ""
        for detail in skip_details:
            container_name = detail.get("container_name", "Unknown")
            reason = detail.get("reason", "Unknown")
            items += f"""
        <div class="update-item skipped">
            <div class="container-name">{container_name}</div>
            <div class="version-info">{reason}</div>
        </div>
        """

        return f"""
        <div class="section">
            <h2>{_mail_icon("skip")}Skipped Containers</h2>
            {items}
        </div>
        """

    def _format_update_item(self, detail: Dict, status: str) -> str:
        """Format a single update item."""
        container_name = detail.get("container_name", "Unknown")
        old_version = detail.get("old_version", "Unknown")
        new_version = detail.get("new_version", "Unknown")
        update_type = detail.get("update_type", "unknown")
        duration = detail.get("duration")

        # Format duration
        if duration is not None:
            if duration < 60:
                duration_str = f"{duration:.1f}s"
            elif duration < 3600:
                duration_str = f"{duration / 60:.1f}m"
            else:
                duration_str = f"{duration / 3600:.1f}h"
        else:
            duration_str = "N/A"

        return f"""
        <div class="update-item {'failed' if status == 'failed' else ''}">
            <div class="container-name">{container_name}</div>
            <div class="version-info">{old_version} → {new_version}</div>
            <div class="update-meta">
                <span class="update-type {update_type}">{update_type}</span>
                <span>{_mail_icon("clock", size=14)}{duration_str}</span>
            </div>
        </div>
        """

    def _generate_errors_section(self, errors: List[str]) -> str:
        """Generate errors section if there are any."""
        if not errors:
            return ""

        error_items = ""
        for error in errors:
            error_items += f'<div class="error-item"><span class="list-marker"></span>{error}</div>'

        return f"""
        <div class="section">
            <h2>{_mail_icon("x-circle")}Errors</h2>
            <div class="error-list">
                {error_items}
            </div>
        </div>
        """

    def _generate_warnings_section(self, warnings: List[str]) -> str:
        """Generate warnings section if there are any."""
        if not warnings:
            return ""

        warning_items = ""
        for warning in warnings:
            warning_items += f'<div class="warning-item"><span class="list-marker"></span>{warning}</div>'

        return f"""
        <div class="section">
            <h2>{_mail_icon("alert")}Warnings</h2>
            <div class="warning-list">
                {warning_items}
            </div>
        </div>
        """
