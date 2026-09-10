#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import base64
import json
import logging
import os
import re
from typing import Dict, Optional, Tuple
from urllib.parse import urlencode, urlparse, urlunparse, parse_qsl

import requests

from ..config import config

logger = logging.getLogger(__name__)


class RegistryAuthManager:
    """
    Manages authentication credentials for different container registries and repositories.

    This class provides a comprehensive authentication system for container registries,
    supporting both registry-level and repository-specific credentials. It handles
    credential loading, validation, and retrieval with proper fallback mechanisms.

    Supports multiple authentication levels:
    - Registry-level: Credentials for entire registries (e.g., "https://registry.hub.docker.com/v2")
    - Repository-level: Specific credentials for individual repositories (e.g., "captnio/captn")

    Credentials file format:
    {
        "registries": {
            "https://registry.hub.docker.com/v2": {
                "username": "default_user",
                "password": "default_password"
            }
        },
        "repositories": {
            "captnio/captn": {
                "username": "specific_user",
                "password": "specific_password"
            },
            "myorg/private-repo": {
                "token": "specific_token"
            }
        }
    }
    """

    def __init__(self):
        self._registry_credentials = {}
        self._repository_credentials = {}
        self.load_credentials()

    def load_credentials(self):
        """
        Load credentials from the configured JSON file.

        This method reads the credentials file specified in the configuration
        and loads both registry-level and repository-specific credentials.
        It handles various error conditions gracefully and provides appropriate logging.
        """
        self._registry_credentials = {}
        self._repository_credentials = {}
        if not config.registryAuth.enabled:
            logger.debug("Registry authentication is disabled", extra={"indent": 2})
            return

        credentials_file = config.registryAuth.credentialsFile
        if not os.path.exists(credentials_file):
            logger.warning(f"Credentials file not found: {credentials_file}", extra={"indent": 2})
            return

        try:
            with open(credentials_file, 'r') as f:
                data = json.load(f)

            if not isinstance(data, dict):
                logger.error(f"Invalid credentials file format: expected dict, got {type(data)}", extra={"indent": 2})
                return

            self._registry_credentials = data.get("registries", {}) or {}
            self._repository_credentials = data.get("repositories", {}) or {}
            logger.debug(f"Loaded {len(self._registry_credentials)} registry and {len(self._repository_credentials)} repository credentials", extra={"indent": 2})

        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to load credentials from {credentials_file}: {e}", extra={"indent": 2})
            self._registry_credentials = {}
            self._repository_credentials = {}

    def get_credentials(self, registry_url: str, repository_name: Optional[str] = None) -> Optional[Dict[str, str]]:
        """
        Get credentials for a specific registry and optionally a specific repository.

        This method retrieves authentication credentials using a priority-based approach.
        It first checks for repository-specific credentials, then falls back to
        registry-level credentials if no repository-specific ones are found.

        Priority order:
        1. Repository-specific credentials (if repository_name provided)
        2. Registry-level credentials (fallback)
        3. None (no credentials found - anonymous access)

        Args:
            registry_url: The registry URL (e.g., "https://registry.hub.docker.com/v2")
            repository_name: Optional repository name (e.g., "captnio/captn")

        Returns:
            Dictionary containing credentials or None if not found
        """
        # logger.debug(f"func_params:\n{json.dumps({k: v for k, v in locals().items()}, indent=4)}", extra={"indent": 2})

        if not config.registryAuth.enabled:
            return None

        # First, try repository-specific credentials
        if repository_name and repository_name in self._repository_credentials:
            logger.debug(f"Found repository-specific credentials for: {repository_name}", extra={"indent": 2})
            return self._repository_credentials[repository_name]

        # Fall back to registry-level credentials
        normalized_url = self.normalize_registry_url(registry_url)

        # Try exact match first
        if normalized_url in self._registry_credentials:
            logging.info(f"Using registry-level credentials for: {registry_url}", extra={"indent": 2})
            return self._registry_credentials[normalized_url]

        # Try partial matches for subdomains
        for url, creds in self._registry_credentials.items():
            if self.urls_match(normalized_url, url):
                logger.debug(f"Using registry-level credentials (partial match) for: {registry_url}", extra={"indent": 2})
                return creds

        logger.debug(f"No credentials found for registry: {registry_url}, repository: {repository_name}", extra={"indent": 2})
        return None

    def normalize_registry_url(self, url: str) -> str:
        """
        Normalize registry URL for consistent matching.

        This method standardizes registry URLs by removing trailing slashes
        and normalizing the scheme to ensure consistent credential matching.

        Parameters:
            url (str): Registry URL to normalize

        Returns:
            str: Normalized registry URL
        """
        parsed = urlparse(url)
        # Remove trailing slashes and normalize scheme
        normalized = f"{parsed.scheme}://{parsed.netloc.rstrip('/')}"
        if parsed.path and parsed.path != '/':
            normalized += parsed.path.rstrip('/')
        return normalized

    def urls_match(self, url1: str, url2: str) -> bool:
        """
        Check if two registry URLs match (handles subdomains).

        This method compares two registry URLs to determine if they match,
        including support for subdomain matching (e.g., "registry.example.com"
        would match "example.com").

        Parameters:
            url1 (str): First registry URL
            url2 (str): Second registry URL

        Returns:
            bool: True if the URLs match, False otherwise
        """
        parsed1 = urlparse(url1)
        parsed2 = urlparse(url2)

        # Check if one is a subdomain of the other
        domain1 = parsed1.netloc.split('.')
        domain2 = parsed2.netloc.split('.')

        # Check if one domain ends with the other
        if len(domain1) >= len(domain2):
            return domain1[-len(domain2):] == domain2
        else:
            return domain2[-len(domain1):] == domain1

    def get_auth_headers(self, registry_url: str, repository_name: Optional[str] = None) -> Dict[str, str]:
        """
        Get static authentication headers from configured credentials.

        Prefer :func:`obtain_oci_auth_headers` for OCI Distribution API tag/manifest
        access (GitLab, GHCR, Harbor, ...). This method remains useful for Docker
        Engine login helpers and registries that accept a preconfigured Bearer token.

        Parameters:
            registry_url (str): The registry URL
            repository_name (str, optional): Optional repository name

        Returns:
            dict: Dictionary containing authentication headers
        """
        credentials = self.get_credentials(registry_url, repository_name)
        if not credentials:
            return {}

        username, password, bearer_token = _split_credentials(credentials)

        # Token-only credentials (typical for GHCR PATs)
        if bearer_token:
            return {"Authorization": f"Bearer {bearer_token}"}

        # Username + password/token -> Basic (Docker Hub login API, docker login, ...)
        if username and password:
            auth_string = base64.b64encode(f"{username}:{password}".encode()).decode()
            return {"Authorization": f"Basic {auth_string}"}

        return {}

    def is_authenticated(self, registry_url: str, repository_name: Optional[str] = None) -> bool:
        """
        Check if we have valid credentials for a registry and optionally a specific repository.

        Accepts either a token-only credential or username + password/token.

        Parameters:
            registry_url (str): The registry URL
            repository_name (str, optional): Optional repository name

        Returns:
            bool: True if valid credentials exist, False otherwise
        """
        credentials = self.get_credentials(registry_url, repository_name)
        if not credentials:
            return False

        username, password, bearer_token = _split_credentials(credentials)
        return bool(bearer_token or (username and password))

    def list_registries(self) -> list:
        """
        List all configured registries.

        Returns:
            list: List of registry URLs that have configured credentials
        """
        return list(self._registry_credentials.keys())

    def list_repositories(self) -> list:
        """
        List all configured repositories.

        Returns:
            list: List of repository names that have configured credentials
        """
        return list(self._repository_credentials.keys())


# Global instance
auth_manager = RegistryAuthManager()


def _split_credentials(credentials: Dict[str, str]) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Normalize credential dict into (username, password, bearer_token).

    - ``token`` without ``username`` -> bearer token (e.g. GHCR PAT)
    - ``username`` + ``password`` or ``token`` -> Basic auth material for challenge/login
    """
    username = credentials.get("username") or None
    if username:
        password = credentials.get("password") or credentials.get("token") or None
        return username, password, None

    bearer_token = credentials.get("token") or None
    password = credentials.get("password") or None
    return None, password, bearer_token


def parse_www_authenticate(header: str) -> Dict[str, str]:
    """
    Parse a WWW-Authenticate header into a dict of parameters.

    Example:
      Bearer realm="https://gitlab.example/jwt/auth",service="container_registry",scope="repository:foo/bar:pull"
    """
    if not header:
        return {}

    result: Dict[str, str] = {}
    scheme_match = re.match(r"^\s*(\w+)\s+(.*)$", header, re.DOTALL)
    if not scheme_match:
        return {}

    result["scheme"] = scheme_match.group(1)
    params = scheme_match.group(2)
    for match in re.finditer(r'(\w+)="([^"]*)"', params):
        result[match.group(1)] = match.group(2)
    return result


def _build_token_url(realm: str, service: Optional[str], scope: Optional[str]) -> str:
    parsed = urlparse(realm)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    if service:
        query["service"] = service
    if scope:
        query["scope"] = scope
    return urlunparse(parsed._replace(query=urlencode(query)))


def _fetch_oauth_token(
    realm: str,
    service: Optional[str],
    scope: Optional[str],
    username: Optional[str] = None,
    password: Optional[str] = None,
    timeout: int = 15,
) -> Optional[str]:
    """Exchange credentials (or anonymous access) at the auth realm for a Bearer token."""
    token_url = _build_token_url(realm, service, scope)
    headers = {}
    if username and password:
        basic = base64.b64encode(f"{username}:{password}".encode()).decode()
        headers["Authorization"] = f"Basic {basic}"

    logger.debug(f"Requesting OCI registry token from {token_url}", extra={"indent": 2})
    response = requests.get(token_url, headers=headers, timeout=timeout)
    response.raise_for_status()
    data = response.json()
    token = data.get("token") or data.get("access_token")
    if not token:
        logger.error("OCI auth realm returned no token/access_token", extra={"indent": 2})
        return None
    return token


def obtain_oci_auth_headers(
    registry_api_url: str,
    repository_name: str,
    probe_url: Optional[str] = None,
    timeout: int = 30,
) -> Optional[Dict[str, str]]:
    """
    Obtain Authorization headers for the OCI Distribution API (Docker Registry HTTP API V2).

    This follows the standard registry auth challenge used by GitLab, GHCR, Harbor, etc.:

    1. Optional preconfigured Bearer token (``token`` without username) is used directly.
    2. Otherwise probe ``probe_url`` (default: ``{registry}/``) without auth.
    3. On HTTP 401, parse ``WWW-Authenticate`` Bearer ``realm`` / ``service`` / ``scope``.
    4. Fetch a JWT/access token from the realm (with Basic credentials when configured).
    5. Return ``Authorization: Bearer ...`` headers.

    Docker Hub **tag discovery** still uses the Hub REST API + Hub JWT login in
    ``registries/docker.py``; this helper is for OCI ``/v2/...`` endpoints only.

    Returns:
        dict: Auth headers (may be empty for fully public registries), or None if
        authentication/token exchange failed and authenticated access is required.
    """
    credentials = get_credentials(registry_api_url, repository_name)
    username, password, bearer_token = _split_credentials(credentials) if credentials else (None, None, None)

    if bearer_token:
        logger.debug(
            f"Using preconfigured Bearer token for OCI registry {registry_api_url}",
            extra={"indent": 2},
        )
        return {"Authorization": f"Bearer {bearer_token}"}

    if not probe_url:
        probe_url = registry_api_url if registry_api_url.endswith("/") else f"{registry_api_url}/"

    try:
        probe = requests.get(probe_url, timeout=timeout)
    except requests.RequestException as e:
        logger.error(f"OCI registry probe failed for {probe_url}: {e}", extra={"indent": 2})
        return None

    if probe.ok:
        logger.debug(f"OCI registry probe succeeded anonymously for {probe_url}", extra={"indent": 2})
        return {}

    if probe.status_code != 401:
        logger.error(
            f"OCI registry probe for {probe_url} returned HTTP {probe.status_code} "
            f"(expected 200 or 401 for auth challenge)",
            extra={"indent": 2},
        )
        return None

    www_auth = probe.headers.get("WWW-Authenticate") or probe.headers.get("Www-Authenticate") or ""
    challenge = parse_www_authenticate(www_auth)
    if challenge.get("scheme", "").lower() != "bearer" or not challenge.get("realm"):
        logger.error(
            f"OCI registry returned 401 without a usable Bearer realm "
            f"(WWW-Authenticate: {www_auth!r})",
            extra={"indent": 2},
        )
        return None

    scope = challenge.get("scope") or f"repository:{repository_name}:pull"
    service = challenge.get("service")

    try:
        token = _fetch_oauth_token(
            realm=challenge["realm"],
            service=service,
            scope=scope,
            username=username,
            password=password,
            timeout=min(timeout, 20),
        )
    except requests.RequestException as e:
        logger.error(
            f"OCI token exchange failed for {registry_api_url} "
            f"(repository={repository_name}): {e}",
            extra={"indent": 2},
        )
        return None

    if not token:
        return None

    if username:
        logger.debug(
            f"Obtained OCI Bearer token for {registry_api_url} using configured credentials",
            extra={"indent": 2},
        )
    else:
        logger.debug(
            f"Obtained anonymous OCI Bearer token for {registry_api_url}",
            extra={"indent": 2},
        )

    return {"Authorization": f"Bearer {token}"}


def get_auth_headers(registry_url: str, repository_name: Optional[str] = None) -> Dict[str, str]:
    """
    Convenience function to get static auth headers for a registry and optionally a repository.

    Parameters:
        registry_url (str): The registry URL
        repository_name (str, optional): Optional repository name

    Returns:
        dict: Dictionary containing authentication headers
    """
    return auth_manager.get_auth_headers(registry_url, repository_name)


def is_authenticated(registry_url: str, repository_name: Optional[str] = None) -> bool:
    """
    Convenience function to check if a registry and optionally a repository is authenticated.

    Parameters:
        registry_url (str): The registry URL
        repository_name (str, optional): Optional repository name

    Returns:
        bool: True if authenticated, False otherwise
    """
    return auth_manager.is_authenticated(registry_url, repository_name)


def get_credentials(registry_url: str, repository_name: Optional[str] = None) -> Optional[Dict[str, str]]:
    """
    Convenience function to get credentials for a registry and optionally a repository.

    Parameters:
        registry_url (str): The registry URL
        repository_name (str, optional): Optional repository name

    Returns:
        dict or None: Credentials dictionary or None if not found
    """
    return auth_manager.get_credentials(registry_url, repository_name)