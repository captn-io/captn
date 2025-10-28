#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import re

from packaging.version import Version
from ..common import normalize_version

logging = logging.getLogger(__name__)


def extract_tag_name(tag):
    """
    Extract tag name from a string or dict.

    This function extracts the tag name from various tag representations,
    handling both string and dictionary formats.

    Parameters:
        tag: Tag object (string or dict with 'name' field)

    Returns:
        str: Extracted tag name
    """
    if isinstance(tag, dict):
        return tag.get("name", "")
    return tag


def generate_tag_regex(template):
    """
    Generate a regex pattern from a tag template.

    This function creates a regular expression pattern that matches tags
    following the same format as the template tag, with digits being
    treated as variable parts.

    Parameters:
        template (str): Tag template to generate regex from

    Returns:
        re.Pattern: Compiled regex pattern for matching similar tags
    """
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


def filter_image_tags(tags, imageTag):
    """
    Filter image tags based on a template pattern.

    This function filters a list of tags to only include those that match
    the pattern of the provided image tag template.

    Parameters:
        tags (list): List of tag objects to filter
        imageTag (str): Template tag to match against

    Returns:
        list: Filtered list of tags matching the template pattern
    """
    pattern = generate_tag_regex(imageTag)
    logging.debug("Filtering retrieved tags", extra={"indent": 2})
    return [tag for tag in tags if pattern.match(extract_tag_name(tag))]


def sort_tags(tags):
    """
    Sort a list of tags in descending order using normalized version comparison.
    
    This function sorts tags by first attempting to normalize them as version strings
    using the normalize_version() function from common.py. Tags that can be normalized
    as versions are sorted by their version tuple (major, minor, patch, build).
    Non-version tags fall back to string comparison.
    
    Parameters:
        tags (list): List of tag objects (dicts with 'name' field) or tag strings
        
    Returns:
        list: Sorted list of tags in descending order (newest versions first)
    """
    def sort_key(tag):
        tag = extract_tag_name(tag)

        # Use normalize_version to normalize the version string
        normalized_version = normalize_version(tag)
        
        # If normalize_version returns valid version tuple, use it for sorting
        if normalized_version != (-1, -1, -1, -1):
            return (0, normalized_version)

        # Fallback: string comparison for non-version tags
        return (1, tag.lower())

    return sorted(tags, key=sort_key, reverse=True)  # reverse=True for descending order


def truncate_tags(tags, imageTag):
    """
    Truncate the list of sorted tags to only include tags from (and including) the given imageTag upward.
    
    This function filters the tag list to only include tags that are at or above
    the specified image tag in the version hierarchy. Assumes tags are already
    sorted in descending order.

    Parameters:
        tags (list): List of sorted tags in descending order
        imageTag (str): Tag to truncate from (inclusive)

    Returns:
        list: Truncated list of tags from the specified tag upward
    """
    truncated = []
    for tag in tags:
        truncated.append(tag)
        if extract_tag_name(tag) == imageTag:
            break
    return truncated
