#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging

from . import docker, ghcr

logging = logging.getLogger(__name__)


def get_image_tags(imageName, imageUrl, registry, imageTagsUrl, imageTag):
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
