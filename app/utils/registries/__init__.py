#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging

from . import docker, ghcr, oci

logger = logging.getLogger(__name__)


def get_image_tags(imageName, imageUrl, registry, imageTagsUrl, imageTag):
    """
    Retrieve available image tags from a container registry.

    Routing:
    - ``docker.io`` -> Docker Hub REST API (Hub-specific auth + pagination)
    - everything else (``ghcr.io``, GitLab, Harbor, ...) -> OCI Distribution API
      with shared Bearer challenge authentication

    Returns:
        list | None: List of available image tags with metadata, an empty list when
        discovery completed with no relevant tags, or None when discovery failed /
        was incomplete (caller must not treat this as "no updates").
    """
    logger.debug(f"Retrieving available image tags from '{registry}'", extra={"indent": 2})
    if registry in ["docker.io"]:
        tags = docker.get_image_tags(imageTagsUrl, imageTag)
    elif registry in ["ghcr.io"]:
        tags = ghcr.get_image_tags(imageName, imageUrl, imageTagsUrl, imageTag)
    else:
        tags = oci.get_image_tags(
            imageName,
            imageUrl,
            imageTagsUrl,
            imageTag,
            registry_api_url=f"https://{registry}/v2",
        )

    if tags is None:
        logger.debug(
            f"Image tag discovery from '{registry}' failed or was incomplete",
            extra={"indent": 2},
        )
        return None

    logger.debug(
        f"A total of {len(tags)} image tags relevant for update processing have been retrieved from '{registry}'",
        extra={"indent": 2},
    )
    return tags
