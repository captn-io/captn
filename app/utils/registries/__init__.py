#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging

from . import docker, ghcr

logging = logging.getLogger(__name__)


def get_image_tags(imageName, imageUrl, registry, imageTagsUrl, imageTag):
    """
    Retrieve available image tags from a container registry.

    This function provides a unified interface to get image tags from different
    registry types. It currently supports Docker Hub and GitHub Container Registry (GHCR).
    The returned tags are filtered to include only relevant updates and are sorted
    with the newest versions first.

    Parameters:
        imageName (str): Name of the image
        imageUrl (str): URL for the image API endpoint
        registry (str): Registry type (e.g., "docker.io", "ghcr.io")
        imageTagsUrl (str): URL for the tags API endpoint
        imageTag (str): Current image tag for filtering

    Returns:
        list: List of available image tags with metadata
    """
    logging.debug(f"Retrieving available image tags from '{registry}'", extra={"indent": 2})
    if registry in ["docker.io"]:
        tags = docker.get_image_tags(imageTagsUrl, imageTag)  # filtered by similar tags, sorted and truncated so only the current tag and newer are listed
    elif registry in ["ghcr.io"]:
        tags = ghcr.get_image_tags(imageName, imageUrl, imageTagsUrl, imageTag)  # filtered by similar tags, sorted and truncated so only the current tag and newer are listed

    logging.debug(
        f"A total of {len(tags)} image tags relevant for update processing have been retrieved from '{registry}'",
        extra={"indent": 2},
    )
    return tags
