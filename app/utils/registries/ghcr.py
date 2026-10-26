#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
GitHub Container Registry (GHCR) support.

GHCR speaks the OCI Distribution API. Tag discovery is delegated to the shared
OCI client, which performs the standard Bearer auth challenge (also used for
GitLab and other private registries).
"""

from typing import Any, List, Optional

from ..config import config
from . import oci

# Re-export helpers historically imported from this module
update_url_with_page_size = oci.update_url_with_page_size
fetch_ghcr_tag_details = oci.fetch_tag_details


def get_image_tags(
    imageName: str,
    imageUrl: str,
    imageTagsUrl: str,
    imageTag: str,
    max_pages=config.ghcr.pageCrawlLimit,
) -> Optional[List[Any]]:
    """
    Retrieve and process available image tags for a GHCR image via the shared OCI path.
    """
    registry_api_url = config.ghcr.apiUrl or "https://ghcr.io/v2"
    return oci.get_image_tags(
        imageName=imageName,
        imageUrl=imageUrl,
        imageTagsUrl=imageTagsUrl,
        imageTag=imageTag,
        registry_api_url=registry_api_url,
        max_pages=max_pages,
    )
