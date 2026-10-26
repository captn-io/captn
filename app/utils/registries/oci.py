#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""OCI Distribution API v2 registry support (GHCR, GitLab, Harbor, and other OCI registries)."""

import json
import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import requests

from ..config import config
from . import generic
from .auth import obtain_oci_auth_headers
from .generic import set_last_discovery_error

logger = logging.getLogger(__name__)


def update_url_with_page_size(url: str, page_size: int = config.ghcr.pageSize) -> str:
    parts = urlparse(url)
    query = parse_qs(parts.query)
    query["n"] = [str(page_size)]
    new_query = urlencode(query, doseq=True)
    return urlunparse(parts._replace(query=new_query))


def _parse_next_url(link_header: str, page_size: int, registry_api_url: str) -> Optional[str]:
    if not link_header:
        return None
    match = re.search(r'<([^>]+)>;\s*rel="next"', link_header)
    if not match:
        return None
    next_url = match.group(1)
    if not next_url.startswith("http"):
        registry_root = registry_api_url.removesuffix("/v2")
        next_url = f"{registry_root}{next_url}"
    return update_url_with_page_size(next_url, page_size)


def fetch_tag_details(imageUrl: str, tags: List[str], headers: Dict[str, str]) -> List[Dict]:
    manifest_headers = {
        **headers,
        "Accept": (
            "application/vnd.oci.image.index.v1+json,"
            "application/vnd.docker.distribution.manifest.list.v2+json,"
            "application/vnd.docker.distribution.manifest.v2+json"
        ),
    }

    detailed_tags = []

    for tag in tags:
        url = f"{imageUrl}/manifests/{tag}"
        created = None

        try:
            response = requests.get(url, headers=manifest_headers, timeout=30)
            response.raise_for_status()
            manifest = response.json()
            media_type = manifest.get("mediaType")
            header_digest = response.headers.get("Docker-Content-Digest")

            created = manifest.get("annotations", {}).get("org.opencontainers.image.created")
            if not created:
                created = manifest.get("created")

            if not created and media_type == "application/vnd.docker.distribution.manifest.v2+json":
                config_digest = manifest.get("config", {}).get("digest")
                if config_digest:
                    config_response = requests.get(
                        f"{imageUrl}/blobs/{config_digest}",
                        headers=headers,
                        timeout=30,
                    )
                    if config_response.ok:
                        created = config_response.json().get("created")

            if not created:
                for entry in manifest.get("history", []):
                    try:
                        v1 = json.loads(entry.get("v1Compatibility", "{}"))
                    except (TypeError, json.JSONDecodeError):
                        continue
                    created = v1.get("created")
                    if created:
                        break

            tag_info = {
                "name": tag,
                "last_updated": created,
                "digest": header_digest,
                "media_type": media_type,
            }
        except requests.RequestException as e:
            logger.warning(f"Failed to fetch manifest for tag {tag}: {e}", extra={"indent": 4})
            tag_info = {"name": tag, "last_updated": None, "digest": None}

        detailed_tags.append(tag_info)

    return detailed_tags


def get_image_tags(
    imageName: str,
    imageUrl: str,
    imageTagsUrl: str,
    imageTag: str,
    registry_api_url: str,
    max_pages=config.ghcr.pageCrawlLimit,
) -> Optional[List[Any]]:
    """
    Retrieve and process image tags from an OCI Distribution v2 compatible registry.

    Authentication uses the standard Bearer challenge flow (shared for GHCR, GitLab,
    Harbor, ...). See :func:`obtain_oci_auth_headers`.

    Returns:
        list | None: Filtered tag metadata, ``[]`` when discovery completed with no
        relevant tags, or ``None`` when auth/tag fetch aborted (incomplete).
    """
    tags: List[str] = []
    page_size = int(config.ghcr.pageSize)
    next_url = update_url_with_page_size(imageTagsUrl, page_size)

    headers = obtain_oci_auth_headers(
        registry_api_url=registry_api_url,
        repository_name=imageName,
        probe_url=next_url,
    )
    if headers is None:
        cause = generic.get_last_discovery_error() or (
            f"Failed to authenticate against OCI registry {registry_api_url} "
            f"for repository '{imageName}'"
        )
        logger.error(cause, extra={"indent": 2})
        set_last_discovery_error(cause)
        return None

    if headers:
        logger.debug(f"Using OCI Bearer authentication for {registry_api_url}", extra={"indent": 2})
    else:
        logger.debug(f"Using anonymous access for OCI registry {registry_api_url}", extra={"indent": 2})

    for _ in range(int(max_pages)):
        if not next_url:
            break

        try:
            logger.debug(f"Making request to: {next_url}", extra={"indent": 2})
            response = requests.get(next_url, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            tags.extend(data.get("tags", []) or [])
            next_url = _parse_next_url(response.headers.get("Link", ""), page_size, registry_api_url)
        except requests.RequestException as e:
            cause = str(e)
            if getattr(getattr(e, "response", None), "status_code", None) == 429:
                cause = f"Registry rate limit exceeded (HTTP 429) while fetching tags from {next_url}"
            logger.error(f"Error fetching tags from {next_url}: {e}", extra={"indent": 2})
            set_last_discovery_error(cause)
            return None

    logger.debug(f"tags:\n{json.dumps(tags, indent=4)}", extra={"indent": 2})
    filtered_tags = generic.filter_image_tags(tags, imageTag)
    logger.debug(f"filtered_tags:\n{json.dumps(filtered_tags, indent=4)}", extra={"indent": 2})
    sorted_tags = generic.sort_tags(filtered_tags)
    logger.debug(f"sorted_filtered_tags:\n{json.dumps(sorted_tags, indent=4)}", extra={"indent": 2})
    truncated_tags = generic.truncate_tags(sorted_tags, imageTag)
    logger.debug(f"truncated_tags:\n{json.dumps(truncated_tags, indent=4)}", extra={"indent": 2})
    return fetch_tag_details(imageUrl, truncated_tags, headers)
