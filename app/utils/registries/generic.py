#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import re

from packaging.version import parse as parse_version

logging = logging.getLogger(__name__)


def _extract_tag_name(tag):
    """Extract tag name from a string or dict."""
    if isinstance(tag, dict):
        return tag.get("name", "")
    return tag


def _generate_tag_regex(template):
    regex = ""
    last_char_type = None

    logging.debug(f"Generating tag regex for {template}", extra={"indent": 2})

    for i, char in enumerate(template):
        if char.isdigit():
            if last_char_type != "digit":
                regex += r"[0-9]+"
                last_char_type = "digit"
        else:
            regex += re.escape(char)
            last_char_type = "alpha"

    logging.debug(f"-> tag_regex: ^{regex}$", extra={"indent": 2})

    return re.compile(f"^{regex}$")


def _filter_image_tags(tags, imageTag):
    pattern = _generate_tag_regex(imageTag)
    logging.debug("Filtering retrieved tags", extra={"indent": 2})
    return [tag for tag in tags if pattern.match(_extract_tag_name(tag))]


def _sort_tags(tags):
    def sort_key(tag):
        tag = _extract_tag_name(tag)

        # Try to parse as a version
        try:
            return (0, parse_version(tag))
        except Exception:  # nosec B110
            pass
        # Try to parse as integer
        try:
            return (1, int(tag))
        except Exception:  # nosec B110
            pass
        # Try to parse as float
        try:
            return (2, float(tag))
        except Exception:  # nosec B110
            pass
        # Fallback: string comparison
        return (3, tag.lower())

    return sorted(tags, key=sort_key, reverse=True)  # reverse=True for descending order


def _truncate_tags(tags, imageTag):
    """
    Truncate the list of sorted tags to only include tags from (and including) the given imageTag upward.
    Assumes tags are already sorted in descending order.
    """
    truncated = []
    for tag in tags:
        truncated.append(tag)
        if _extract_tag_name(tag) == imageTag:
            break
    return truncated
