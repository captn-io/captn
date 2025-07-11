#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import logging
import os
import re
import sys
from datetime import datetime
from fnmatch import fnmatch
from logging.handlers import RotatingFileHandler
from typing import Tuple

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
                             "/app/logs/container-updater.log".
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


def normalize_version(version: str) -> Tuple[int, int, int, int]:
    """
    Cleans a version string and returns a 4-part numeric tuple (major, minor, patch, build)
    Non-numeric parts are ignored or defaulted to 0. Invalid formats return (-1, -1, -1, -1)
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
    Supported suffixes in input: s (seconds), m (minutes), h (hours), d (days)
    Supported return units: s, m, h, d
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

    Returns one of the following strings:
        - 'major': Major version difference (X.0.0 → Y.0.0)
        - 'minor': Minor version difference (X.Y.0 → X.Z.0)
        - 'patch': Patch version difference (X.Y.Z → X.Y.W)
        - 'build': Build metadata difference (e.g., additional fourth version component)
        - 'digest': Version is the same, but the image digest has changed
        - 'unknown': Version format invalid or change type undetermined
        - None: No update detected (versions and digests are identical)

    Parameters:
        old_version (str): The currently used version string.
        new_version (str): The latest available version string.
        local_digests (list[str]): List of local image digests.
        remote_digest (str): Digest from the remote registry.
    """

    logging.debug(f"Determining update type for remote tag {new_version}", extra={"indent": 2})
    logging.debug(f"func_params:\n{json.dumps({k: v for k, v in locals().items()}, indent=4)}", extra={"indent": 4})

    # Remove prefixes like "ghcr.io/immich-app/immich-server@sha256:" or "sha256:"
    remote_digest = remote_digest.rsplit(":", 1)[-1] if ":" in remote_digest else remote_digest
    local_digests = [
        local_digest.rsplit(":", 1)[-1] if ":" in local_digest else local_digest
        for local_digest in local_digests
    ]

    logging.debug(f"remote_digest (normalized): {remote_digest}", extra={"indent": 4})
    logging.debug(f"local_digests (normalized): {local_digests}", extra={"indent": 4})

    old_major, old_minor, old_patch, old_build = normalize_version(old_version)
    new_major, new_minor, new_patch, new_build = normalize_version(new_version)

    if new_major != old_major:
        return "major"
    if new_minor != old_minor:
        return "minor"
    if new_patch != old_patch:
        return "patch"
    if new_build != old_build:
        return "build"

    if old_version == new_version:
        if remote_digest not in local_digests:
            return "digest"

    if old_version == new_version and remote_digest in local_digests:
        return None

    return "unknown"


def get_update_permit( container_name=None, image_reference=None, update_type=None, age=None, old_version=None, new_version=None, latest_version=None, pre_check=False, ) -> Tuple[bool, str, str, str, str]:
    """
    Determine whether an update of a specific type (e.g., patch, minor, major, etc.)
    is permitted for a given container based on configured rules and optional conditions.

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

    Returns:
        Tuple[bool, str, str]:
            - is_update_allowed (bool): Whether the update is permitted
            - effective_rule_name (str): Name of the rule used for final decision
            - originally_assigned_rule_name (str): Name of the rule assigned before fallback (if any)
    """
    image_reference = (
        image_reference.split(":", 1)[0]
        if image_reference and ":" in image_reference
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
            if required == "major" and new_major > old_major:
                satisfied = True
            elif required == "minor" and new_minor > old_minor:
                satisfied = True
            elif required == "patch" and new_patch > old_patch:
                satisfied = True
            elif required == "build" and new_build > old_build:
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
    Generates a backup container name in the format:
    <container_name>_bak_cu_<timestamp>

    Parameters:
        original_name (str): Name of the original container

    Returns:
        str: Backup container name
    """
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    return f"{original_name}_bak_cu_{timestamp}"


def get_container_allowed_update_types( container_name, image_reference=None ) -> Tuple[set, str, str]:
    """
    Efficiently determine which update types are allowed for a container based on its assigned rule.
    This is a lightweight pre-check that doesn't require version or age data.

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
