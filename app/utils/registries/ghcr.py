#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import logging
import re
from typing import Any, Dict, List
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import requests

from ..config import config
from . import generic
from .auth import get_auth_headers, is_authenticated

logging = logging.getLogger(__name__)


def update_url_with_page_size(url: str, page_size: int = config.ghcr.pageSize) -> str:
    """
    Ensure the URL includes or overrides the 'n' query parameter (page size).

    This function modifies a URL to include or update the 'n' parameter
    for GHCR API requests, ensuring consistent pagination behavior.

    Parameters:
        url (str): The original URL
        page_size (int): Desired page size for the request

    Returns:
        str: Modified URL with 'n' parameter
    """
    parts = urlparse(url)
    query = parse_qs(parts.query)
    query["n"] = [str(page_size)]
    new_query = urlencode(query, doseq=True)
    return urlunparse(parts._replace(query=new_query))


def fetch_ghcr_tag_details(imageUrl: str, tags: List[str], token: str) -> List[Dict]:
    """
    Retrieve detailed metadata for each tag in a GitHub Container Registry (GHCR) image.

    This function performs the following operations for each tag:
    - Sends a GET request to fetch the tag's manifest from GHCR.
    - Determines the media type (multi-arch index or single-arch manifest).
    - Extracts metadata such as digest, created timestamp, and architecture/os/platform info.
    - Falls back to config blob, annotations, and manifest history for 'created' timestamp.
    - Handles both multi-arch and single-arch images.
    - Handles request failures gracefully by returning minimal tag metadata.

    Parameters:
        imageUrl (str): GHCR base URL
        tags (List[str]): Tag names to inspect
        token (str): Bearer token

    Returns:
        List[Dict]: Detailed tag metadata
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": (
            "application/vnd.oci.image.index.v1+json,"
            "application/vnd.docker.distribution.manifest.list.v2+json,"
            "application/vnd.docker.distribution.manifest.v2+json"
        ),
    }

    detailed_tags = []

    for tag in tags:
        url = f"{imageUrl}/manifests/{tag}"
        tag_info = {}
        created = None

        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            manifest = response.json()
            media_type = manifest.get("mediaType")

            logging.debug( f"Raw manifest data for tag {tag}: {json.dumps(manifest, indent=4)}", extra={"indent": 4}, )
            header_digest = response.headers.get("Docker-Content-Digest")

            # Fallbacks for created
            created = manifest.get("annotations", {}).get( "org.opencontainers.image.created" )
            if not created:
                created = manifest.get("created")

            if (
                not created
                and media_type == "application/vnd.docker.distribution.manifest.v2+json"
            ):
                config_digest = manifest.get("config", {}).get("digest")
                if config_digest:
                    config_url = f"{imageUrl}/blobs/{config_digest}"
                    config_response = requests.get(
                        config_url, headers=headers, timeout=30
                    )
                    if config_response.ok:
                        config_data = config_response.json()
                        created = config_data.get("created")

            if not created:
                for entry in manifest.get("history", []):
                    v1 = json.loads(entry.get("v1Compatibility", "{}"))
                    created = v1.get("created")
                    if created:
                        break

            # digest = manifest.get("config", {}).get("digest") or manifest.get("digest")

            tag_info = {
                "creator": None,
                "id": None,
                "images": [],
                "last_updated": created,
                "last_updater": None,
                "last_updater_username": None,
                "name": tag,
                "repository": None,
                "full_size": None,
                "v2": None,
                "tag_status": None,
                "tag_last_pulled": None,
                "tag_last_pushed": created,
                "media_type": media_type,
                "content_type": None,
                "digest": header_digest,
            }

            if media_type in [
                "application/vnd.oci.image.index.v1+json",
                "application/vnd.docker.distribution.manifest.list.v2+json",
            ]:
                for image in manifest.get("manifests", []):
                    platform = image.get("platform", {})
                    tag_info["images"].append(
                        {
                            "architecture": platform.get("architecture"),
                            "features": None,
                            "variant": platform.get("variant"),
                            "digest": image.get("digest"),
                            "os": platform.get("os"),
                            "os_features": None,
                            "os_version": None,
                            "size": image.get("size"),
                            "status": None,
                            "last_pulled": None,
                            "last_pushed": created,
                        }
                    )

            elif media_type == "application/vnd.docker.distribution.manifest.v2+json":
                config_digest = manifest.get("config", {}).get("digest")
                tag_info["images"].append(
                    {
                        "architecture": None,
                        "features": None,
                        "variant": None,
                        "digest": config_digest,
                        "os": None,
                        "os_features": None,
                        "os_version": None,
                        "size": None,
                        "status": None,
                        "last_pulled": None,
                        "last_pushed": created,
                    }
                )

        except requests.RequestException as e:
            logging.warning( f"Failed to fetch manifest for tag {tag}: {e}", extra={"indent": 4} )
            tag_info = {
                "creator": None,
                "id": None,
                "images": [],
                "last_updated": None,
                "last_updater": None,
                "last_updater_username": None,
                "name": tag,
                "repository": None,
                "full_size": None,
                "v2": None,
                "tag_status": None,
                "tag_last_pulled": None,
                "tag_last_pushed": None,
                "media_type": None,
                "content_type": "image",
                "digest": None,
            }

        detailed_tags.append(tag_info)

    return detailed_tags


def get_image_tags(imageName: str, imageUrl: str, imageTagsUrl: str, imageTag: str, max_pages=config.ghcr.pageCrawlLimit) -> List[Any]:
    """
    Retrieve and process available image tags for a GHCR (GitHub Container Registry) image.

    This function performs the following steps:
    1. Authenticates with GHCR using configured credentials or anonymous access.
    2. Fetches paginated tag lists using the GHCR tag listing API.
    3. Filters the returned tags to retain only those relevant to the current imageTag.
    4. Sorts and truncates the tag list to keep only the current and newer versions.
    5. Fetches additional metadata for each remaining tag (e.g., digests).

    Parameters:
        imageName (str): The name of the image (e.g., "myorg/myapp").
        imageUrl (str): The full registry URL for this image (e.g., "https://ghcr.io/v2/myorg/myapp").
        imageTagsUrl (str): URL endpoint used to list tags (typically ends with /tags/list).
        imageTag (str): The current tag of the running image (used for filtering and comparison).
        max_pages (int): Maximum number of pagination requests to perform (default from config).

    Returns:
        List[Dict]: A list of dictionaries representing relevant tag metadata,
                    filtered, sorted, and truncated for update evaluation.
    """
    tags: List[str] = []
    page_size = 100
    next_url = update_url_with_page_size(imageTagsUrl, page_size)

    # Get authentication headers for GHCR
    auth_headers = get_auth_headers(config.ghcr.apiUrl, imageName)

    # Auth - use configured token if available, otherwise fall back to anonymous
    if auth_headers:
        logging.debug(f"Using configured authentication for GHCR")
        headers = auth_headers
    else:
        logging.debug(f"No authentication configured for GHCR, using anonymous access")
        try:
            token_response = requests.get("https://ghcr.io/token", params={"scope": f"repository:{imageName}:pull"}, timeout=10)
            token_response.raise_for_status()
            token = token_response.json().get("token")
            if not token:
                raise ValueError("No token received")
            headers = {"Authorization": f"Bearer {token}"}
        except (requests.RequestException, ValueError) as e:
            logging.error(f"Failed to retrieve auth token: {e}", extra={"indent": 4})
            return tags

    for _ in range(max_pages):
        if not next_url:
            break

        try:
            response = requests.get(next_url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            tags.extend(data.get("tags", []))

            # Ensure next page retains page_size
            link_header = response.headers.get("Link", "")
            match = re.search(r'<([^>]+)>;\s*rel="next"', link_header)
            if match:
                next_url = update_url_with_page_size(f"https://ghcr.io{match.group(1)}", page_size)
            else:
                next_url = None
        except requests.RequestException as e:
            logging.error(f"Error fetching tags from {next_url}: {e}", extra={"indent": 4})
            break

    logging.debug(f"tags:\n{json.dumps(tags, indent=4)}", extra={"indent": 4})
    filtered_tags = generic.filter_image_tags(tags, imageTag)
    logging.debug(f"filtered_tags:\n{json.dumps(filtered_tags, indent=4)}", extra={"indent": 4})
    sorted_tags = generic.sort_tags(filtered_tags)
    logging.debug(f"sorted_filtered_tags:\n{json.dumps(sorted_tags, indent=4)}", extra={"indent": 4})
    truncated_tags = generic.truncate_tags(sorted_tags, imageTag)
    logging.debug(f"truncated_tags:\n{json.dumps(truncated_tags, indent=4)}", extra={"indent": 4})
    detailed_tags = fetch_ghcr_tag_details(imageUrl, truncated_tags, token)
    logging.debug(f"detailed_tags:\n{json.dumps(detailed_tags, indent=4)}", extra={"indent": 4})
    return detailed_tags
