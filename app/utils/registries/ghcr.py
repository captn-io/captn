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

logging = logging.getLogger(__name__)


def _update_url_with_page_size(url: str, page_size: int = config.ghcr.pageSize) -> str:
    """
    Ensure the URL includes or overrides the 'n' query parameter (page size).
    """
    parts = urlparse(url)
    query = parse_qs(parts.query)
    query["n"] = [str(page_size)]
    new_query = urlencode(query, doseq=True)
    return urlunparse(parts._replace(query=new_query))


def _fetch_ghcr_tag_details(imageUrl: str, tags: List[str], token: str) -> List[Dict]:
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

            logging.debug(
                f"Raw manifest data for tag {tag}: {json.dumps(manifest, indent=4)}",
                extra={"indent": 4},
            )
            header_digest = response.headers.get("Docker-Content-Digest")

            # Fallbacks for created
            created = manifest.get("annotations", {}).get(
                "org.opencontainers.image.created"
            )
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
            logging.warning(
                f"Failed to fetch manifest for tag {tag}: {e}", extra={"indent": 4}
            )
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


def _fetch_ghcr_tag_details_old(
    imageUrl: str, tags: List[str], token: str
) -> List[Dict]:
    """
    Retrieve detailed metadata for each tag in a GitHub Container Registry (GHCR) image.

    This function performs the following operations for each tag:
    - Sends a GET request to fetch the tag's manifest from GHCR.
    - Determines the media type (multi-arch index or single-arch manifest).
    - Extracts metadata such as digest, created timestamp, and architecture/os/platform info.
    - Falls back to fetching the config blob for created timestamp if not provided in the manifest.
    - Handles both multi-arch and single-arch images.
    - Handles request failures gracefully by returning minimal tag metadata.

    Parameters:
        imageUrl (str): The base URL of the GHCR image repository (e.g., "https://ghcr.io/v2/myorg/myapp").
        tags (List[str]): A list of tag strings to process.
        token (str): Bearer token for GHCR API authentication.

    Returns:
        List[Dict]: A list of enriched tag dictionaries, each containing metadata such as:
                    name, digest, media_type, image variants, and timestamps.
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

        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            manifest = response.json()
            media_type = manifest.get("mediaType")

            logging.debug(
                f"Raw manifest data for tag {tag}: {json.dumps(manifest, indent=4)}",
                extra={"indent": 4},
            )
            header_digest = response.headers.get("Docker-Content-Digest")
            created = manifest.get("annotations", {}).get(
                "org.opencontainers.image.created"
            )

            if (
                not created
                and media_type == "application/vnd.docker.distribution.manifest.v2+json"
            ):
                config_digest = manifest.get("config", {}).get("digest")
                if config_digest:
                    config_url = f"{imageUrl}/blobs/{config_digest}"
                    config_response = requests.get(
                        config_url, headers=headers, timeout=10
                    )
                    if config_response.ok:
                        config_data = config_response.json()
                        created = config_data.get("created")

            if not created and media_type in [
                "application/vnd.oci.image.index.v1+json",
                "application/vnd.docker.distribution.manifest.list.v2+json",
            ]:
                manifests = manifest.get("manifests", [])
                if manifests:
                    # Prefer linux/amd64 if available
                    preferred = next(
                        (
                            m
                            for m in manifests
                            if m.get("platform", {}).get("architecture") == "amd64"
                            and m.get("platform", {}).get("os") == "linux"
                        ),
                        manifests[0],
                    )
                    platform_digest = preferred.get("digest")
                    if platform_digest:
                        pm_url = f"{imageUrl}/manifests/{platform_digest}"
                        pm_response = requests.get(pm_url, headers=headers, timeout=10)
                        if pm_response.ok:
                            pm_manifest = pm_response.json()
                            config_digest = pm_manifest.get("config", {}).get("digest")
                            if config_digest:
                                config_url = f"{imageUrl}/blobs/{config_digest}"
                                config_response = requests.get(
                                    config_url, headers=headers, timeout=10
                                )
                                if config_response.ok:
                                    config_data = config_response.json()
                                    created = config_data.get("created")

            # Fallback for single manifest
            if (
                not created
                and media_type == "application/vnd.docker.distribution.manifest.v2+json"
            ):
                config_digest = manifest.get("config", {}).get("digest")
                if config_digest:
                    config_url = f"{imageUrl}/blobs/{config_digest}"
                    config_response = requests.get(
                        config_url, headers=headers, timeout=10
                    )
                    if config_response.ok:
                        config_data = config_response.json()
                        created = config_data.get("created")

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

            else:
                logging.warning(
                    f"Unsupported mediaType: {media_type}", extra={"indent": 4}
                )
                tag_info.update(
                    {
                        "last_updated": None,
                        "tag_last_pushed": None,
                        "media_type": None,
                        "digest": None,
                    }
                )

        except requests.RequestException as e:
            logging.warning(
                f"Failed to fetch manifest for tag {tag}: {e}", extra={"indent": 4}
            )
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
    1. Authenticates anonymously with GHCR and retrieves a bearer token.
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
    next_url = _update_url_with_page_size(imageTagsUrl, page_size)

    # Auth
    try:
        token_response = requests.get("https://ghcr.io/token", params={"scope": f"repository:{imageName}:pull"}, timeout=10)
        token_response.raise_for_status()
        token = token_response.json().get("token")
        if not token:
            raise ValueError("No token received")
    except (requests.RequestException, ValueError) as e:
        logging.error(f"Failed to retrieve auth token: {e}", extra={"indent": 4})
        return tags

    headers = {"Authorization": f"Bearer {token}"}

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
                next_url = _update_url_with_page_size(f"https://ghcr.io{match.group(1)}", page_size)
            else:
                next_url = None
        except requests.RequestException as e:
            logging.error(f"Error fetching tags from {next_url}: {e}", extra={"indent": 4})
            break

    logging.debug(f"tags:\n{json.dumps(tags, indent=4)}", extra={"indent": 4})
    tags = generic._filter_image_tags(tags, imageTag)
    logging.debug(f"filtered_tags:\n{json.dumps(tags, indent=4)}", extra={"indent": 4})
    tags = generic._sort_tags(tags)
    logging.debug(f"sorted_filtered_tags:\n{json.dumps(tags, indent=4)}", extra={"indent": 4})
    tags = generic._truncate_tags(tags, imageTag)
    logging.debug(f"truncated_tags:\n{json.dumps(tags, indent=4)}", extra={"indent": 4})
    tags = _fetch_ghcr_tag_details(imageUrl, tags, token)
    logging.debug(f"detailed_tags:\n{json.dumps(tags, indent=4)}", extra={"indent": 4})
    return tags
