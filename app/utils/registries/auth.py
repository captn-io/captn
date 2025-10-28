#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import logging
import os
from typing import Dict, Optional
from urllib.parse import urlparse

from ..config import config

logging = logging.getLogger(__name__)


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
            logging.debug("Registry authentication is disabled", extra={"indent": 2})
            return

        credentials_file = config.registryAuth.credentialsFile
        if not os.path.exists(credentials_file):
            logging.warning(f"Credentials file not found: {credentials_file}", extra={"indent": 2})
            return

        try:
            with open(credentials_file, 'r') as f:
                data = json.load(f)

            if not isinstance(data, dict):
                logging.error(f"Invalid credentials file format: expected dict, got {type(data)}", extra={"indent": 2})
                return

            self._registry_credentials = data.get("registries", {}) or {}
            self._repository_credentials = data.get("repositories", {}) or {}
            logging.debug(f"Loaded {len(self._registry_credentials)} registry and {len(self._repository_credentials)} repository credentials", extra={"indent": 2})

        except (json.JSONDecodeError, IOError) as e:
            logging.error(f"Failed to load credentials from {credentials_file}: {e}", extra={"indent": 2})
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
        # logging.debug(f"func_params:\n{json.dumps({k: v for k, v in locals().items()}, indent=4)}", extra={"indent": 2})

        if not config.registryAuth.enabled:
            return None

        # First, try repository-specific credentials
        if repository_name and repository_name in self._repository_credentials:
            logging.debug(f"Found repository-specific credentials for: {repository_name}", extra={"indent": 2})
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
                logging.debug(f"Using registry-level credentials (partial match) for: {registry_url}", extra={"indent": 2})
                return creds

        logging.debug(f"No credentials found for registry: {registry_url}, repository: {repository_name}", extra={"indent": 2})
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
        Get authentication headers for a registry and optionally a specific repository.

        This method generates appropriate authentication headers based on the
        registry type and available credentials. It supports different authentication
        methods for different registry types (e.g., Bearer tokens for GHCR, Basic auth for Docker Hub).

        Parameters:
            registry_url (str): The registry URL
            repository_name (str, optional): Optional repository name

        Returns:
            dict: Dictionary containing authentication headers
        """
        credentials = self.get_credentials(registry_url, repository_name)
        if not credentials:
            return {}

        # Determine registry type and create appropriate headers
        if "ghcr.io" in registry_url or "github.com" in registry_url:
            # GHCR uses Bearer token
            token = credentials.get("token")
            if token:
                return {"Authorization": f"Bearer {token}"}
        else:
            # Docker Hub and other registries use Basic auth
            username = credentials.get("username")
            password = credentials.get("password") or credentials.get("token")
            if username and password:
                import base64
                auth_string = base64.b64encode(f"{username}:{password}".encode()).decode()
                return {"Authorization": f"Basic {auth_string}"}

        return {}

    def is_authenticated(self, registry_url: str, repository_name: Optional[str] = None) -> bool:
        """
        Check if we have valid credentials for a registry and optionally a specific repository.

        This method validates that appropriate credentials exist for the specified
        registry and repository combination, checking for the required credential
        types based on the registry type.

        Parameters:
            registry_url (str): The registry URL
            repository_name (str, optional): Optional repository name

        Returns:
            bool: True if valid credentials exist, False otherwise
        """
        credentials = self.get_credentials(registry_url, repository_name)
        if not credentials:
            return False

        # Validate credentials based on registry type
        if "ghcr.io" in registry_url or "github.com" in registry_url:
            return "token" in credentials
        else:
            return "username" in credentials and ("password" in credentials or "token" in credentials)

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


def get_auth_headers(registry_url: str, repository_name: Optional[str] = None) -> Dict[str, str]:
    """
    Convenience function to get auth headers for a registry and optionally a repository.

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