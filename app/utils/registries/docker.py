#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import logging
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
from typing import Optional

import requests

from ..config import config
from . import generic
from .auth import get_credentials

logger = logging.getLogger(__name__)


def update_url_with_page_size(url: str, page_size: int = config.docker.pageSize):
    """
    Ensure the URL includes the desired page_size parameter.

    This function modifies a URL to include or update the page_size parameter
    for Docker Hub API requests, ensuring consistent pagination behavior.

    Parameters:
        url (str): The original URL
        page_size (int): Desired page size for the request

    Returns:
        str: Modified URL with page_size parameter
    """
    parts = urlparse(url)
    query = parse_qs(parts.query)
    query["page_size"] = [str(page_size)]
    new_query = urlencode(query, doseq=True)
    return urlunparse(parts._replace(query=new_query))


def get_dockerhub_jwt(repository_name: Optional[str] = None):
    """
    Get a JWT token for Docker Hub authentication.

    This function authenticates with Docker Hub using configured credentials
    and returns a JWT token for subsequent API requests.

    Parameters:
        repository_name (Optional[str]): Name of the repository for authentication

    Returns:
        Optional[str]: JWT token if authentication successful, None otherwise
    """
    logger.debug(f"func_params:\n{json.dumps({k: v for k, v in locals().items()}, indent=4)}", extra={"indent": 2})
    creds = get_credentials(config.docker.apiUrl, repository_name)
    if not creds:
        logger.debug(f"No credentials found for repository: {repository_name}", extra={"indent": 2})
        return None

    username = creds.get("username")
    password = creds.get("password") or creds.get("token")
    if not username or not password:
        logger.error(f"Incomplete credentials for repository: {repository_name} - username: {bool(username)}, password: {bool(password)}", extra={"indent": 2})
        return None

    # Log which credentials are being used (without exposing the actual values)
    if repository_name:
        logging.info(f"Using repository-specific credentials for: {repository_name}", extra={"indent": 2})
    else:
        logging.info(f"Using registry-level credentials for Docker Hub", extra={"indent": 2})

    try:
        resp = requests.post(
            "https://hub.docker.com/v2/users/login/",
            json={"username": username, "password": password},
            timeout=10
        )
        resp.raise_for_status()
        token = resp.json().get("token")
        if token:
            logger.debug("Successfully obtained Docker Hub JWT token", extra={"indent": 4})
            return token
        else:
            logger.error("No token received from Docker Hub login", extra={"indent": 4})
    except Exception as e:
        logger.error(f"Docker Hub login failed: {e}", extra={"indent": 4})
    return None


def get_image_tags(imageTagsUrl, imageTag, max_pages=config.docker.pageCrawlLimit, page_size=config.docker.pageSize):
    """
    Retrieve and process available image tags for a Docker Hub image.

    This function fetches image tags from Docker Hub API with authentication support,
    filters them based on the current image tag, and returns a sorted list of
    relevant tags for update evaluation.

    Parameters:
        imageTagsUrl (str): URL endpoint for fetching image tags
        imageTag (str): Current image tag for filtering
        max_pages (int): Maximum number of pages to crawl
        page_size (int): Number of tags per page

    Returns:
        List[Dict]: List of filtered and sorted image tag metadata
    """
    tags = []
    page_count = 0

    logger.debug(f"func_params:\n{json.dumps({k: v for k, v in locals().items()}, indent=4)}", extra={"indent": 4})

    # Extract repository name from the URL for auth
    # URL format: https://registry.hub.docker.com/v2/repositories/captnio/captn/tags
    try:
        repository_name = imageTagsUrl.split("/repositories/")[1].split("/tags")[0]
        logger.debug(f"Extracted repository name from URL: {repository_name}", extra={"indent": 2})
    except (IndexError, AttributeError):
        # Fallback: try to extract from imageTag if it contains the full repository name
        repository_name = imageTag.split(':')[0] if ':' in imageTag else imageTag
        logger.debug(f"Using fallback repository name from imageTag: {repository_name}", extra={"indent": 2})

    # Auth: Try JWT if credentials exist, else anonymous
    jwt_token = get_dockerhub_jwt(repository_name)
    if jwt_token:
        headers = {"Authorization": f"JWT {jwt_token}"}
        logger.debug(f"Using Docker Hub JWT authentication", extra={"indent": 2})
    else:
        headers = {}
        logger.debug(f"No authentication configured for Docker Hub (anonymous)", extra={"indent": 2})

    while imageTagsUrl:
        if max_pages is not None and page_count >= max_pages:
            break

        imageTagsUrl = update_url_with_page_size(imageTagsUrl, page_size=page_size)

        try:
            logger.debug(f"Making request to: {imageTagsUrl}", extra={"indent": 2})
            logger.debug(f"Headers: {headers}", extra={"indent": 2})
            response = requests.get(imageTagsUrl, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()

            if "results" in data:
                tags.extend(data["results"])

            imageTagsUrl = data.get("next")
            page_count += 1
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching image tags from {imageTagsUrl}: {e}", extra={"indent": 2})
            break

    logger.debug(f"-> tags:\n{json.dumps(tags, indent=4)}", extra={"indent": 2})
    tags = generic.filter_image_tags(tags, imageTag)
    logger.debug(f"-> filtered_tags:\n{json.dumps(tags, indent=4)}", extra={"indent": 2})
    tags = generic.sort_tags(tags)
    logger.debug(f"-> sorted_filtered_tags:\n{json.dumps(tags, indent=4)}", extra={"indent": 2})
    tags = generic.truncate_tags(tags, imageTag)
    logger.debug(f"-> truncated_tags:\n{json.dumps(tags, indent=4)}", extra={"indent": 2})
    return tags
