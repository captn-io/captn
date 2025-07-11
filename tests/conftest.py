"""
Pytest configuration and common fixtures for captn tests.

This module provides shared fixtures and configuration for all test modules.
"""

import os
import sys
from unittest.mock import Mock

import pytest

# Add the app directory to the Python path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))


@pytest.fixture
def mock_docker_client():
    """Mock Docker client for testing."""
    client = Mock()

    # Mock container objects
    container = Mock()
    container.name = "test-container"
    container.id = "test-container-id"
    container.status = "running"

    # Mock image objects
    image = Mock()
    image.tags = ["test-image:1.0.0"]
    image.id = "test-image-id"

    # Mock API responses
    client.containers.list.return_value = [container]
    client.images.get.return_value = image
    client.api.inspect_container.return_value = {
        "Config": {"Image": "test-image:1.0.0"},
        "State": {"Status": "running"},
    }
    client.api.inspect_image.return_value = {
        "RepoTags": ["test-image:1.0.0"],
        "RepoDigests": ["test-image@sha256:abc123"],
    }

    return client


@pytest.fixture
def sample_config():
    """Sample configuration for testing."""
    return {
        "general": {"dryRun": True},
        "logging": {"level": "INFO"},
        "rules": {
            "default": {
                "allow": {
                    "major": False,
                    "minor": False,
                    "patch": True,
                    "build": False,
                    "digest": False,
                }
            }
        },
        "assignmentsByName": {},
        "assignmentsByImage": {},
        "assignmentsById": {},
    }


@pytest.fixture
def mock_registry_response():
    """Mock registry API response for testing."""
    return [
        {
            "name": "1.0.1",
            "digest": "sha256:def456",
            "last_updated": "2024-01-01T12:00:00.000Z",
        },
        {
            "name": "1.0.0",
            "digest": "sha256:abc123",
            "last_updated": "2023-12-31T12:00:00.000Z",
        },
    ]
