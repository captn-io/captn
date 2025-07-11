#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import logging
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import requests

from ..config import config
from . import generic

logging = logging.getLogger(__name__)


def _update_url_with_page_size(url: str, page_size: int = config.docker.pageSize):
    """Ensure the URL includes the desired page_size parameter."""
    parts = urlparse(url)
    query = parse_qs(parts.query)
    query["page_size"] = [str(page_size)]
    new_query = urlencode(query, doseq=True)
    return urlunparse(parts._replace(query=new_query))


def get_image_tags(imageTagsUrl, imageTag, max_pages=config.docker.pageCrawlLimit, page_size=config.docker.pageSize):
    tags = []
    page_count = 0

    logging.debug(f"func_params:\n{json.dumps({k: v for k, v in locals().items()}, indent=4)}", extra={"indent": 4})

    while imageTagsUrl:
        if max_pages is not None and page_count >= max_pages:
            break

        imageTagsUrl = _update_url_with_page_size(imageTagsUrl, page_size=page_size)

        try:
            response = requests.get(imageTagsUrl, timeout=30)
            response.raise_for_status()
            data = response.json()

            if "results" in data:
                tags.extend(data["results"])

            imageTagsUrl = data.get("next")
            page_count += 1
        except requests.exceptions.RequestException as e:
            print(f"Error fetching image tags from {imageTagsUrl}: {e}")
            break

    logging.debug(f"-> tags:\n{json.dumps(tags, indent=4)}", extra={"indent": 2})
    tags = generic._filter_image_tags(tags, imageTag)
    logging.debug(f"-> filtered_tags:\n{json.dumps(tags, indent=4)}", extra={"indent": 2})
    tags = generic._sort_tags(tags)
    logging.debug(f"-> sorted_filtered_tags:\n{json.dumps(tags, indent=4)}", extra={"indent": 2})
    tags = generic._truncate_tags(tags, imageTag)
    logging.debug(f"-> truncated_tags:\n{json.dumps(tags, indent=4)}", extra={"indent": 2})
    return tags
