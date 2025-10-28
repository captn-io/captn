#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import logging
import os
import re
import socket
import subprocess
import sys
import docker
from datetime import datetime
from fnmatch import fnmatch
from logging.handlers import RotatingFileHandler
from typing import Dict, List, Optional, Tuple, Union

from .config import config


def setup_logging(log_level: str = "info", log_file_path: str = "/app/logs/captn.log", dry_run: bool = False) -> None:
    """
    Set up global logging configuration for the application.

    This function configures:
    - Console output (stdout) with optional indentation
    - Rotating file logging
    - Dynamic formatting with module/function location (DEBUG only)
    - Optional suppression of noisy third-party logs (Docker, urllib3)

    The formatter supports an `indent` field in log records, which can be used
    to visually indent multiline output or hierarchical logs.

    Parameters:
        log_level (str): Logging level as string ("debug", "info", "warning", etc.).
                         Defaults to "info". If invalid, falls back to INFO.
        log_file_path (str): Absolute path to the log file. Default is
                             "/app/logs/captn.log".
    """
    log_level = getattr(logging, log_level.upper(), logging.INFO)

    class IndentFormatter(logging.Formatter):
        def format(self, record):
            # Handle indentation (optional extra field)
            indent_spaces = " " * getattr(record, "indent", 0)
            record.msg = indent_spaces + str(record.msg).replace("\n", "\n" + indent_spaces)

            # Build relative module path + function name
            rel_path = os.path.relpath(record.pathname).replace(os.sep, ".")
            if rel_path.endswith(".py"):
                rel_path = rel_path[:-3]  # Remove .py extension

            location = f"{rel_path}.{record.funcName}"

            # Pad or truncate to 64
            location_padded = f"{f'[{location}]':<64}"
            record.location = location_padded
            return super().format(record)

    if log_level == logging.DEBUG:
        formatter = (
            IndentFormatter("%(asctime)s %(levelname)-8s %(location)s %(message)s")
            if not dry_run
            else IndentFormatter("%(asctime)s %(levelname)-8s [DRY_RUN] %(location)s %(message)s")
        )
    else:
        formatter = (
            IndentFormatter("%(asctime)s %(levelname)-8s %(message)s")
            if not dry_run
            else IndentFormatter("%(asctime)s %(levelname)-8s [DRY_RUN] %(message)s")
        )

    logger = logging.getLogger()
    logger.setLevel(log_level)
    logger.handlers.clear()

    # StreamHandler for console (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Ensure log directory exists
    log_dir = os.path.dirname(log_file_path)

    # If we can't write to the default directory, use a local one
    if log_dir and not os.access(log_dir, os.W_OK):
        log_dir = "./logs"
        log_file_path = os.path.join(log_dir, "captn.log")

    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)

    # RotatingFileHandler for log file
    file_handler = RotatingFileHandler(
        log_file_path,
        maxBytes=(20 * 1024 * 1024) if log_level == logging.DEBUG else (5 * 1024 * 1024),  # 20 MB in debug mode, 5 MB in others
        backupCount=(20 if log_level == logging.DEBUG else 10),  # Keep up to 20 log files in debug mode, 10 in others
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Suppress verbose Docker/urllib3 logs unless explicitly debugging
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("docker").setLevel(logging.WARNING)


def detect_version_scheme(version: str) -> str:
    """
    Detects the versioning scheme used by a version string.

    This function analyzes version strings to determine their format:
    - 'date': Date-based versioning (e.g., "2021.10.08", "2023.12.25")
    - 'semantic': Standard semantic versioning (e.g., "1.2.3", "2.15.3")
    - 'numeric': Simple numeric versioning (e.g., "1", "2", "10")
    - 'unknown': Unable to determine scheme

    Parameters:
        version (str): Version string to analyze

    Returns:
        str: Detected versioning scheme
    """
    version = ".".join(str(p) for p in normalize_version(version)) # convert tuple from normalize_version back to string

    # Check for date-based versioning schemes
    #
    # This pattern matches versions in the format:
    # - YYYY.MM.DD.X
    #
    # Where:
    # - YYYY: 4-digit year starting with "20" (2000-2099)
    # - MM: Month (01-12)
    # - DD: Day (01-31)
    # - X: Patch/build numbers (any number of digits, can be empty)
    #
    # The X placeholder represents patch and build numbers that are always appended by normalize_version
    date_pattern = r'^(20)\d{2}\.(0[1-9]|1[0-2])\.(0[1-9]|[12]\d|3[01])\.([0-9]*)$'
    if re.match(date_pattern, version):
        return 'date'

    # Check for semantic versioning (X.Y.Z where X, Y, Z are numbers)
    semantic_pattern = r'^\d+\.\d+\.\d+'
    if re.match(semantic_pattern, version):
        return 'semantic'

    # Check for simple numeric versioning
    numeric_pattern = r'^\d+$'
    if re.match(numeric_pattern, version):
        return 'numeric'

    return 'unknown'


def compare_versions(old_version: str, new_version: str) -> Tuple[str, str]:
    """
    Intelligently compares two version strings that may use different versioning schemes.

    This function detects the versioning schemes of both versions and provides
    appropriate comparison logic to avoid false positives when schemes change.

    Parameters:
        old_version (str): Current version string
        new_version (str): New version string

    Returns:
        Tuple[str, str]: (update_type, reason)
            update_type: 'major', 'minor', 'patch', 'build', 'digest', 'unknown', 'scheme_change'
            reason: Explanation of the comparison result
    """
    old_scheme = detect_version_scheme(old_version)
    new_scheme = detect_version_scheme(new_version)

    # If schemes are different, this might be a versioning scheme change
    if old_scheme != new_scheme:
        logging.warning(
            f"Version scheme change detected: {old_version} ({old_scheme}) -> {new_version} ({new_scheme})",
            extra={"indent": 4}
        )

        # Special handling for common scheme changes
        if old_scheme == 'semantic' and new_scheme == 'date':
            # This is likely a switch from semantic to date-based versioning
            # We should be very cautious about this update
            return 'scheme_change', f"Versioning scheme changed from {old_scheme} to {new_scheme}"

        if old_scheme == 'date' and new_scheme == 'semantic':
            # This is likely a switch from date-based to semantic versioning
            # We should be very cautious about this update
            return 'scheme_change', f"Versioning scheme changed from {old_scheme} to {new_scheme}"

        # For other scheme changes, treat as scheme_change
        return 'scheme_change', f"Versioning scheme changed from {old_scheme} to {new_scheme}"

    # If schemes are the same, use normal comparison
    if old_scheme == 'semantic':
        return compare_semantic_versions(old_version, new_version)
    elif old_scheme == 'date':
        return compare_date_versions(old_version, new_version)
    elif old_scheme == 'numeric':
        return compare_numeric_versions(old_version, new_version)
    else:
        return 'unknown', f"Unknown versioning scheme: {old_scheme}"


def compare_semantic_versions(old_version: str, new_version: str) -> Tuple[str, str]:
    """
    Compare semantic versions and determine the type of update.

    Follows semantic versioning (SemVer) principles to compare version strings
    in the format X.Y.Z or X.Y.Z.BUILD, where each component is compared
    hierarchically to determine the significance of the update.

    Args:
        old_version (str): The current/old version string in semantic format
        new_version (str): The new version string in semantic format

    Returns:
        Tuple[str, str]: A tuple containing:
            - Update type: 'major', 'minor', 'patch', 'build', 'digest', or 'unknown'
            - Description: Human-readable explanation of the comparison result

    Update Types:
        - 'major': Major version number increased (X.Y.Z -> X+1.Y.Z)
        - 'minor': Minor version number increased (X.Y.Z -> X.Y+1.Z)
        - 'patch': Patch version number increased (X.Y.Z -> X.Y.Z+1)
        - 'build': Build number increased (X.Y.Z.B -> X.Y.Z.B+1)
        - 'digest': Same version, likely digest-only change
        - 'unknown': Invalid format or no clear version relationship
    """
    old_parts = normalize_version(old_version)
    new_parts = normalize_version(new_version)

    if old_parts == (-1, -1, -1, -1) or new_parts == (-1, -1, -1, -1):
        return 'unknown', "Invalid semantic version format"

    old_major, old_minor, old_patch, old_build = old_parts
    new_major, new_minor, new_patch, new_build = new_parts

    if new_major > old_major:
        return 'major', f"Major version increase: {old_major} -> {new_major}"
    elif new_minor > old_minor:
        return 'minor', f"Minor version increase: {old_minor} -> {new_minor}"
    elif new_patch > old_patch:
        return 'patch', f"Patch version increase: {old_patch} -> {new_patch}"
    elif new_build > old_build:
        return 'build', f"Build version increase: {old_build} -> {new_build}"
    elif old_version == new_version:
        return 'digest', "Same version, digest change only"
    else:
        return 'unknown', "No clear version relationship"


def compare_date_versions(old_version: str, new_version: str) -> Tuple[str, str]:
    """
    Compare date-based versions and determine the type of update.

    Supports multiple date formats:
    - ISO format with leading zeroes: YYYY-MM-DD (e.g., "2025-10-09")
    - ISO format without leading zeroes: YYYY-M-D (e.g., "2025-8-1")
    - ISO format mixed: YYYY-MM-D, YYYY-M-DD (e.g., "2025-10-9", "2025-8-09")
    - Dot format with leading zeroes: YYYY.MM.DD (e.g., "2025.10.09")
    - Dot format without leading zeroes: YYYY.M.D (e.g., "2025.8.1")
    - Dot format mixed: YYYY.MM.D, YYYY.M.DD (e.g., "2025.10.9", "2025.8.09")

    Args:
        old_version (str): The current/old version string in date format
        new_version (str): The new version string in date format

    Returns:
        Tuple[str, str]: A tuple containing:
            - Update type: 'major', 'minor', 'patch', 'digest', or 'unknown'
            - Description: Human-readable explanation of the comparison result

    Update Types:
        - 'major': More than 365 days difference
        - 'minor': Between 30-365 days difference
        - 'patch': Less than 30 days difference
        - 'digest': Same date, likely digest-only change
        - 'unknown': Invalid format or newer date is older than current
    """
    def parse_date(date_str: str) -> datetime:
        """Parse date string in various formats:
        - YYYY-MM-DD (ISO format with leading zeroes)
        - YYYY.MM.DD (dot format with leading zeroes)
        - YYYY-M-D (ISO format without leading zeroes)
        - YYYY.M.D (dot format without leading zeroes)
        - YYYY-MM-D, YYYY-M-DD (ISO format mixed)
        - YYYY.MM.D, YYYY.M.DD (dot format mixed)
        """

        logging.debug(f"Trying to parse date {date_str} from version/tag name", extra={"indent": 1})

        # First try standard formats with leading zeroes
        formats_with_zeroes = [
            "%Y-%m-%d",  # YYYY-MM-DD (ISO with leading zeroes)
            "%Y.%m.%d",  # YYYY.MM.DD (dot with leading zeroes)
        ]

        for fmt in formats_with_zeroes:
            try:
                parsed_date = datetime.strptime(date_str, fmt)
                logging.debug(f"Successfully parsed date with standard format {fmt}: {parsed_date}", extra={"indent": 2})
                return parsed_date
            except ValueError:
                logging.debug(f"Failed to parse with format {fmt}: {date_str}", extra={"indent": 2})
                continue

        # For formats without leading zeroes, manually parse and normalize
        import re

        # Check if it matches patterns with mixed leading zeroes
        # These patterns handle all combinations: YYYY-MM-D, YYYY-M-DD, YYYY-M-D, etc.
        # Note: We use more restrictive patterns to ensure valid dates (months 1-12, days 1-31)
        iso_pattern = r'^(\d{4})-([1-9]|0[1-9]|1[0-2])-([1-9]|0[1-9]|[12]\d|3[01])$'
        dot_pattern = r'^(\d{4})\.([1-9]|0[1-9]|1[0-2])\.([1-9]|0[1-9]|[12]\d|3[01])$'

        for pattern, separator in [(iso_pattern, '-'), (dot_pattern, '.')]:
            match = re.match(pattern, date_str)
            if match:
                year, month, day = match.groups()
                logging.debug(f"Date pattern matched: {date_str} -> year={year}, month={month}, day={day}", extra={"indent": 2})
                # Normalize by adding leading zeroes
                normalized_date = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                logging.debug(f"Normalized date: {normalized_date}", extra={"indent": 2})
                try:
                    parsed_date = datetime.strptime(normalized_date, "%Y-%m-%d")
                    logging.debug(f"Successfully parsed date: {parsed_date}", extra={"indent": 2})
                    return parsed_date
                except ValueError as e:
                    logging.debug(f"Failed to parse normalized date {normalized_date}: {e}", extra={"indent": 2})
                    continue

        logging.debug(f"No valid date pattern matched for: {date_str}", extra={"indent": 2})
        raise ValueError(f"Invalid date format: {date_str}. Supported formats: YYYY-MM-DD, YYYY.MM.DD, YYYY-M-D, YYYY.M.D, YYYY-MM-D, YYYY-M-DD, YYYY.MM.D, YYYY.M.DD")

    try:
        # Parse dates
        old_date = parse_date(old_version)
        new_date = parse_date(new_version)

        logging.debug(f"Comparing dates from version/tag name: new({new_date}) old({old_date})", extra={"indent": 2})

        if new_date > old_date:
            # For date versions, we consider this a "minor" update unless it's a very old date
            days_diff = (new_date - old_date).days
            if days_diff >= 365:  # More than a year difference
                return 'major', f"Major date difference: {days_diff} days"
            elif days_diff > 30:  # More than a month difference
                return 'minor', f"Minor date difference: {days_diff} days"
            else:
                return 'patch', f"Patch date difference: {days_diff} days"
        elif old_date == new_date:
            return 'digest', "Same date version, digest change only"
        else:
            return 'unknown', "Newer date is older than current date"
    except ValueError:
        return 'unknown', "Invalid date version format"


def get_docker_host_hostname() -> str:
    """
    Get the hostname of the Docker host from within a container.

    This function attempts multiple methods to determine the Docker host hostname:
    1. Docker daemon info API to get the host system name
    2. Environment variables (HOSTNAME, DOCKER_HOST_HOSTNAME)
    3. Fallback to container hostname

    Returns:
        str: The hostname of the Docker host, or container hostname as fallback
    """
    logging.debug(f"Trying to determine hostname", extra={"indent": 0})

    # Method 1: Try to get hostname from Docker daemon info
    try:
        client = docker.from_env()
        info = client.info()
        hostname = info.get('Name')
        if hostname == "docker-desktop":
            logging.debug(f"Ignoring hostname from daemon: {hostname}", extra={"indent": 2})
        if hostname and hostname != "docker-desktop":
            logging.debug(f"Found Docker host hostname from daemon info: {hostname}", extra={"indent": 2})
            return hostname
    except Exception as e:
        logging.debug(f"Could not get hostname from Docker daemon info: {e}", extra={"indent": 2})

    # Method 2: Check environment variables
    hostname = os.environ.get('HOSTNAME') or os.environ.get('DOCKER_HOST_HOSTNAME', extra={"indent": 2})
    if hostname:
        logging.debug(f"Found Docker host hostname from environment: {hostname}", extra={"indent": 2})
        return hostname

    # Fallback: return container hostname
    fallback_hostname = socket.gethostname()
    logging.debug(f"Using fallback hostname: {fallback_hostname}", extra={"indent": 2})
    return fallback_hostname


def compare_numeric_versions(old_version: str, new_version: str) -> Tuple[str, str]:
    """
    Compare simple numeric versions and determine the type of update.

    Converts version strings to integers and compares them to determine
    the significance of the version change based on the numeric difference.

    Args:
        old_version (str): The current/old version string (must be numeric)
        new_version (str): The new version string (must be numeric)

    Returns:
        Tuple[str, str]: A tuple containing:
            - Update type: 'major', 'minor', 'patch', 'digest', or 'unknown'
            - Description: Human-readable explanation of the comparison result

    Update Types:
        - 'major': Numeric difference > 10 (large jump)
        - 'minor': Numeric difference 2-10 (medium jump)
        - 'patch': Numeric difference of 1 (small increment)
        - 'digest': Same numeric value, likely digest-only change
        - 'unknown': Invalid format or newer version is smaller than current
    """
    try:
        old_num = int(old_version)
        new_num = int(new_version)

        if new_num > old_num:
            if new_num - old_num > 10:  # Large jump
                return 'major', f"Major numeric increase: {old_num} -> {new_num}"
            elif new_num - old_num > 1:  # Medium jump
                return 'minor', f"Minor numeric increase: {old_num} -> {new_num}"
            else:
                return 'patch', f"Patch numeric increase: {old_num} -> {new_num}"
        elif old_num == new_num:
            return 'digest', "Same numeric version, digest change only"
        else:
            return 'unknown', "Newer version is smaller than current version"
    except ValueError:
        return 'unknown', "Invalid numeric version format"


def normalize_version(version: str) -> Tuple[int, int, int, int]:
    """
    Cleans a version string and returns a 4-part numeric tuple (major, minor, patch, build).

    This function normalizes version strings by removing non-numeric characters and
    converting them into a standardized 4-part tuple format for comparison.

    Parameters:
        version (str): Version string to normalize (e.g., "1.2.3", "v2.0.1-beta")

    Returns:
        Tuple[int, int, int, int]: Normalized version as (major, minor, patch, build).
                                  Returns (-1, -1, -1, -1) for invalid formats.
    """
    version = version.lower().strip()

    # Replace any non-digit separator (except dots) with a dot
    version = re.sub(r"[^0-9\.]+", ".", version)

    # Reduce multiple consecutive dots
    version = re.sub(r"\.+", ".", version).strip(".")

    parts = version.split(".")

    if not all(p.isdigit() for p in parts[:4]):
        return (-1, -1, -1, -1)

    parts = [int(p) for p in parts[:4]]  # type: ignore[misc]
    while len(parts) < 4:
        parts.append(0)

    return tuple(parts[:4])  # type: ignore[return-value]


def parse_duration(duration_str, return_unit="m"):
    """
    Converts duration strings like '10m', '2h', '1d' into desired unit.

    This function parses human-readable duration strings and converts them to
    the specified unit for use in configuration and timing calculations.

    Parameters:
        duration_str (str): Duration string (e.g., "10m", "2h", "1d")
        return_unit (str): Target unit for conversion ("s", "m", "h", "d")

    Returns:
        float: Duration converted to the specified unit

    Raises:
        ValueError: If the duration string format is invalid
    """
    match = re.match(r"^(\d+)([smhd])$", duration_str)
    if not match:
        raise ValueError(f"Invalid duration format: {duration_str}")

    value, unit = match.groups()
    value = int(value)

    # duration in seconds
    seconds = {"s": value, "m": value * 60, "h": value * 3600, "d": value * 86400}[unit]

    # convert to requested unit
    return {"s": seconds, "m": seconds / 60, "h": seconds / 3600, "d": seconds / 86400}[return_unit]


def get_update_type(old_version, new_version, local_digests, remote_digest):
    """
    Determines the type of update between two image versions and digests.

    This function analyzes version differences and digest changes to categorize
    the type of update available. It's used to determine update permissions
    based on configured rules.

    Returns one of the following strings:
        - 'major': Major version difference (X.0.0 → Y.0.0)
        - 'minor': Minor version difference (X.Y.0 → X.Z.0)
        - 'patch': Patch version difference (X.Y.Z → X.Y.W)
        - 'build': Build metadata difference (e.g., additional fourth version component)
        - 'digest': Version is the same, but the image digest has changed
        - 'scheme_change': Versioning scheme has changed (e.g., semantic to date-based)
        - 'unknown': Version format invalid or change type undetermined
        - None: No update detected (versions and digests are identical)

    Parameters:
        old_version (str): The currently used version string.
        new_version (str): The latest available version string.
        local_digests (list[str]): List of local image digests.
        remote_digest (str): Digest from the remote registry.

    Returns:
        str or None: Update type string or None if no update is available
    """

    logging.debug(f"Determining update type for remote tag {new_version}", extra={"indent": 2})
    logging.debug(f"func_params:\n{json.dumps({k: v for k, v in locals().items()}, indent=4)}", extra={"indent": 4})

    # Remove prefixes like "ghcr.io/immich-app/immich-server@sha256:" or "sha256:"
    remote_digest = remote_digest.rsplit(":", 1)[-1] if remote_digest and ":" in remote_digest else remote_digest
    local_digests = [
        local_digest.rsplit(":", 1)[-1] if local_digest and ":" in local_digest else local_digest
        for local_digest in local_digests
    ]

    logging.debug(f"remote_digest (normalized): {remote_digest}", extra={"indent": 4})
    logging.debug(f"local_digests (normalized): {local_digests}", extra={"indent": 4})

    # Use intelligent version comparison to handle different versioning schemes
    update_type, reason = compare_versions(old_version, new_version)
    if update_type in ["digest", "unknown"]:
        if remote_digest not in local_digests:
            update_type = "digest"
            reason = reason
        elif remote_digest in local_digests:
            update_type = None
            reason = "No digests changed"
    logging.debug(f"Comparison result: {update_type} - {reason}", extra={"indent": 4})

    return update_type


def get_update_permit( container_name=None, image_reference=None, update_type=None, age=None, old_version=None, new_version=None, latest_version=None, pre_check=False, ) -> Tuple[bool, str, str, str, str]:
    """
    Determine whether an update of a specific type is permitted for a given container.

    This function evaluates update permissions based on configured rules, considering
    container assignments, image references, and various conditions like age requirements
    and lag policies.

    Rules are resolved in the following priority:
    1. Assignment by container name
    2. Assignment by image reference (with fnmatch support)
    3. Assignment by image ID (if configured)
    4. Fallback to the "default" rule

    Each rule can:
    - Explicitly allow or deny update types via the "allow" section
    - Optionally define "conditions" for specific update types (e.g., allow major updates
      only if newer patch or build versions exist)
    - Optionally define a "lagPolicy" that restricts updates from being too recent;
      for example, a lag of 3 means updates are allowed only if the target version is
      at least 3 versions behind the latest known version

    Parameters:
        container_name (str):   Name of the container (used for rule assignment)
        image_reference (str):  Full image reference (e.g., "nginx:1.23.4")
        update_type (str):      Type of update (e.g., "patch", "minor", "major", "digest", "build")
        age (int):              Image age in minutes
        old_version (str):      Current version of the image
        new_version (str):      Proposed version to update to
        latest_version (str):   Latest available version in the registry
        pre_check (bool):       If True, only check basic permissions without conditions

    Returns:
        Tuple[bool, str, str, str, str]:
            - is_update_allowed (bool): Whether the update is permitted
            - effective_rule_name (str): Name of the rule used for final decision
            - originally_assigned_rule_name (str): Name of the rule assigned before fallback (if any)
            - reject_reason (str): Reason for rejection if update is not allowed
            - new_image_reference (str): Full image reference for the update
    """
    # Remove tag and digest from image reference
    image_reference = (
        image_reference.split(":", 1)[0].split("@", 1)[0]
        if image_reference
        else image_reference
    )
    old_major, old_minor, old_patch, old_build = normalize_version(old_version)
    new_major, new_minor, new_patch, new_build = normalize_version(new_version)
    latest_major, latest_minor, latest_patch, latest_build = normalize_version(latest_version)

    update_info = f"{old_version} -> {new_version}" if update_type != "digest" else f"{old_version}"
    logging.debug( f"{'Pre-checking' if pre_check else 'Checking'} update permission of '{container_name}' for update type {update_type} ({update_info})", extra={"indent": 2}, )
    logging.debug( f"func_params:\n{json.dumps({k: v for k, v in locals().items()}, indent=4)}", extra={"indent": 4}, )

    # Load rules
    raw_rules = config.rules
    rules = {}
    for key in raw_rules._values:
        try:
            rules[key] = json.loads(raw_rules._values[key])
        except Exception as e:
            logging.error( f"Failed to parse rule '{key}': invalid JSON format {e}", extra={"indent": 4}, )
            logging.error(f"{e}", extra={"indent": 4})
            continue

    # Assignment helper
    def get_assignment_section(name):
        section = getattr(config, name, None)
        if hasattr(section, "_values"):
            return section._values
        elif isinstance(section, dict):
            return section
        return {}

    assignments = {
        "by_name": get_assignment_section("assignmentsByName"),
        "by_image": get_assignment_section("assignmentsByImage"),
        "by_id": get_assignment_section("assignmentsById"),
    }

    # Rule name assignment logic
    rule_name_original = (
        assignments["by_name"].get(container_name)
        or next(
            (
                r
                for p, r in assignments["by_image"].items()
                if fnmatch(image_reference, p)
            ),
            None,
        )
        or next(
            (r for p, r in assignments["by_id"].items() if fnmatch(image_reference, p)),
            None,
        )
        or "default"
    )

    # Fallback to default if not defined
    rule_name = rule_name_original
    if rule_name not in rules:
        logging.warning( f"Rule '{rule_name}' not found, falling back to 'default'", extra={"indent": 4}, )
        rule_name = "default"

    rule = rules.get(rule_name, {})
    logging.debug(f"rule_name: {rule_name}", extra={"indent": 4})
    logging.debug(f"rule:\n{json.dumps(rule, indent=4)}", extra={"indent": 4})

    allowed = rule.get("allow", {}).get(update_type, False)
    logging.debug( f"[General{', Pre-Check' if pre_check else ''}] {update_type.capitalize()} updates are generally{' not' if not allowed else ''} allowed for {container_name}", extra={"indent": 4}, )

    # Check additional conditions
    conditions = rule.get("conditions", {}).get(update_type)
    (
        logging.debug( f"[Conditions{', Pre-Check' if pre_check else ''}] conditions:\n{json.dumps(conditions, indent=4)}", extra={"indent": 4}, )
        if conditions
        else None
    )

    if allowed and conditions:
        satisfied = False
        for required in conditions.get("require", []):
            if required == "major" and new_major > 0:
                satisfied = True
            elif required == "minor" and new_minor > 0:
                satisfied = True
            elif required == "patch" and new_patch > 0:
                satisfied = True
            elif required == "build" and new_build > 0:
                satisfied = True

        if not satisfied:
            logging.debug( f"[Conditions{', Pre-Check' if pre_check else ''}] Required conditions for {update_type} updates not satisfied", extra={"indent": 4}, )
            return (
                False,
                rule_name,
                rule_name_original,
                "Conditions",
                f"{image_reference}:{new_version}",
            )

        logging.debug( f"[Conditions{', Pre-Check' if pre_check else ''}] Required conditions for {update_type} updates have been satisfied", extra={"indent": 4}, )

    # Check update lag policy
    configured_lag = rule.get("lagPolicy", {}).get(update_type)
    (
        logging.debug( f"[LagPolicy{', Pre-Check' if pre_check else ''}] Configured policy requires staying always {configured_lag} version{'s' if configured_lag and configured_lag > 1 else ''} behind for {update_type} updates", extra={"indent": 4}, )
        if configured_lag
        else logging.debug(
            f"[LagPolicy{', Pre-Check' if pre_check else ''}] Not configured",
            extra={"indent": 4},
        )
    )

    if allowed and configured_lag and latest_version and new_version:
        lag = 0
        if update_type == "major":
            lag = (latest_major - new_major) + 1
        elif update_type == "minor":
            lag = (latest_minor - new_minor) + 1
        elif update_type == "patch":
            lag = (latest_patch - new_patch) + 1
        elif update_type == "build":
            lag = (latest_build - new_build) + 1

        logging.debug( f"[LagPolicy{', Pre-Check' if pre_check else ''}] Calculated lag for this {update_type} update from {old_version} to {new_version}: {lag} (required: > {configured_lag})", extra={"indent": 4}, )

        if lag <= configured_lag:
            logging.debug( f"[LagPolicy{', Pre-Check' if pre_check else ''}] Insufficient version lag for {update_type} update from {old_version} to {new_version} according to policy", extra={"indent": 4}, )
            return (
                False,
                rule_name,
                rule_name_original,
                "LagPolicy",
                f"{image_reference}:{new_version}",
            )

        logging.debug( f"[LagPolicy{', Pre-Check' if pre_check else ''}] Version lag requirement satisfied for {update_type} update from {old_version} to {new_version}", extra={"indent": 4}, )

    # Check minimum image age
    min_age_default = "30m"
    min_age_config = rule.get("minImageAge", min_age_default)
    (
        logging.debug( f"[MinImageAge{', Pre-Check' if pre_check else ''}] Not configured, using default of '{min_age_default}'", extra={"indent": 4}, )
        if not rule.get("minImageAge")
        else None
    )

    if allowed and min_age_config and age:
        try:
            min_age_minutes = parse_duration(min_age_config)
            if age < min_age_minutes:
                logging.debug( f"[MinImageAge{', Pre-Check' if pre_check else ''}] Insufficient image age of {int(age)} min (required: >= {int(min_age_minutes)} min)", extra={"indent": 4}, )
                return (
                    False,
                    rule_name,
                    rule_name_original,
                    "MinImageAge",
                    f"{image_reference}:{new_version}",
                )
            else:
                logging.debug( f"[MinImageAge{', Pre-Check' if pre_check else ''}] Image age requirement satisfied ({int(age)} min >= {int(min_age_minutes)} min)", extra={"indent": 4}, )
        except Exception as e:
            logging.warning( f"[MinImageAge{', Pre-Check' if pre_check else ''}] Failed to evaluate image age: {e}", extra={"indent": 4}, )
    elif not age:
        logging.warning( f"[MinImageAge{', Pre-Check' if pre_check else ''}] Unable to determine image creation timestamp - Skipping minimum age policy evaluation", extra={"indent": 4}, )

    return (
        allowed,
        rule_name,
        rule_name_original,
        "General",
        f"{image_reference}:{new_version}",
    )


def get_container_backup_name(original_name):
    """
    Generates a backup container name with timestamp.

    This function creates a unique backup container name by appending a timestamp
    to the original container name. The format follows the pattern:
    <container_name>_bak_cu_<timestamp>

    Parameters:
        original_name (str): Name of the original container

    Returns:
        str: Backup container name with timestamp (e.g., "nginx_bak_cu_20231201-143022")
    """
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    return f"{original_name}_bak_cu_{timestamp}"


def get_container_allowed_update_types( container_name, image_reference=None ) -> Tuple[set, str, str]:
    """
    Efficiently determine which update types are allowed for a container.

    This function performs a lightweight pre-check to determine which update types
    are allowed for a container based on its assigned rule. It doesn't require
    version or age data, making it useful for early filtering.

    Parameters:
        container_name (str): Name of the container
        image_reference (str): Full image reference (optional, for image-based rule assignment)

    Returns:
        Tuple[set, str, str]:
            - allowed_types (set): Set of allowed update types ('major', 'minor', 'patch', 'build', 'digest')
            - effective_rule_name (str): Name of the rule used for decision
            - originally_assigned_rule_name (str): Name of the rule assigned before fallback
    """
    image_reference = (
        image_reference.split(":", 1)[0]
        if image_reference and ":" in image_reference
        else image_reference
    )

    # Load rules
    raw_rules = config.rules
    rules = {}
    for key in raw_rules._values:
        try:
            rules[key] = json.loads(raw_rules._values[key])
        except Exception as e:
            logging.error(
                f"Failed to parse rule '{key}': invalid JSON format {e}",
                extra={"indent": 4},
            )
            continue

    # Assignment helper
    def get_assignment_section(name):
        section = getattr(config, name, None)
        if hasattr(section, "_values"):
            return section._values
        elif isinstance(section, dict):
            return section
        return {}

    assignments = {
        "by_name": get_assignment_section("assignmentsByName"),
        "by_image": get_assignment_section("assignmentsByImage"),
        "by_id": get_assignment_section("assignmentsById"),
    }

    # Rule name assignment logic
    rule_name_original = (
        assignments["by_name"].get(container_name)
        or next(
            (
                r
                for p, r in assignments["by_image"].items()
                if fnmatch(image_reference, p)
            ),
            None,
        )
        or next(
            (r for p, r in assignments["by_id"].items() if fnmatch(image_reference, p)),
            None,
        )
        or "default"
    )

    # Fallback to default if not defined
    rule_name = rule_name_original
    if rule_name not in rules:
        logging.warning(
            f"Rule '{rule_name}' not found, falling back to 'default'",
            extra={"indent": 4},
        )
        rule_name = "default"

    rule = rules.get(rule_name, {})
    allowed_config = rule.get("allow", {})

    # Extract allowed update types
    allowed_types = set()
    for update_type, is_allowed in allowed_config.items():
        if is_allowed:
            allowed_types.add(update_type)

    return allowed_types, rule_name, rule_name_original
