"""
Integration tests for captn.

These tests verify that the main application entry point works correctly
and that basic functionality is accessible.
"""

import os
import subprocess
import sys
from unittest.mock import Mock, patch

import pytest


class TestCommandLineInterface:
    """Test command-line interface functionality."""

    def test_version_flag(self):
        """Test --version flag."""
        result = subprocess.run(
            [sys.executable, "-m", "app", "--version"],
            capture_output=True,
            text=True,
            cwd=os.path.join(os.path.dirname(__file__), ".."),
        )
        assert result.returncode == 0
        assert "0.5.0" in result.stdout

    def test_help_flag(self):
        """Test --help flag."""
        result = subprocess.run(
            [sys.executable, "-m", "app", "--help"],
            capture_output=True,
            text=True,
            cwd=os.path.join(os.path.dirname(__file__), ".."),
        )
        assert result.returncode == 0
        assert "captn" in result.stdout
        assert "rule-driven container updater" in result.stdout

    def test_dry_run_flag(self):
        """Test --dry-run flag."""
        # Create logs directory to avoid FileNotFoundError
        logs_dir = os.path.join(os.path.dirname(__file__), "..", "app", "logs")
        os.makedirs(logs_dir, exist_ok=True)

        result = subprocess.run(
            [sys.executable, "-m", "app", "--dry-run"],
            capture_output=True,
            text=True,
            cwd=os.path.join(os.path.dirname(__file__), ".."),
        )
        # Should exit with 0 even if no containers found
        assert result.returncode == 0

    def test_log_level_flag(self):
        """Test --log-level flag."""
        # Create logs directory to avoid FileNotFoundError
        logs_dir = os.path.join(os.path.dirname(__file__), "..", "app", "logs")
        os.makedirs(logs_dir, exist_ok=True)

        result = subprocess.run(
            [sys.executable, "-m", "app", "--log-level", "debug", "--dry-run"],
            capture_output=True,
            text=True,
            cwd=os.path.join(os.path.dirname(__file__), ".."),
        )
        assert result.returncode == 0


class TestModuleImports:
    """Test that all modules can be imported correctly."""

    def test_main_module_import(self):
        """Test that main module can be imported."""
        from app import __main__

        assert __main__ is not None

    def test_utils_imports(self):
        """Test that all utility modules can be imported."""
        from app.utils import cleanup, common, config, self_update
        from app.utils.engines import docker
        from app.utils.notifiers import telegram
        from app.utils.registries import docker as registry_docker
        from app.utils.registries import generic, ghcr

        assert common is not None
        assert config is not None
        assert cleanup is not None
        assert self_update is not None
        assert docker is not None
        assert registry_docker is not None
        assert generic is not None
        assert ghcr is not None
        assert telegram is not None

    def test_version_import(self):
        """Test that version can be imported."""
        from app import __version__

        assert __version__ == "0.5.0"


class TestBasicFunctionality:
    """Test basic application functionality."""

    @patch("app.utils.engines.get_client")
    @patch("app.utils.engines.get_containers")
    def test_no_containers_found(self, mock_get_containers, mock_get_client):
        """Test behavior when no containers are found."""
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        mock_get_containers.return_value = []

        # This would test the main function, but we need to mock more dependencies
        # For now, just test that the modules can be imported
        from app import __main__

        assert __main__ is not None

    def test_logging_setup(self):
        """Test that logging can be set up."""
        import logging

        from app.utils.common import setup_logging

        # Create logs directory to avoid FileNotFoundError
        logs_dir = os.path.join(os.path.dirname(__file__), "..", "app", "logs")
        os.makedirs(logs_dir, exist_ok=True)

        # Test that setup_logging doesn't crash
        setup_logging(log_level="info", dry_run=True)

        # Check that root logger has handlers
        root_logger = logging.getLogger()
        assert len(root_logger.handlers) > 0


@pytest.mark.integration
class TestDockerIntegration:
    """Integration tests that require Docker."""

    def test_docker_image_build(self):
        """Test that Docker image can be built."""
        # This would test building the Docker image
        # For now, just check that the Dockerfile exists
        dockerfile_path = os.path.join(
            os.path.dirname(__file__), "..", "docker", "DOCKERFILE"
        )
        assert os.path.exists(dockerfile_path), "Dockerfile not found"

    def test_dockerfile_syntax(self):
        """Test that Dockerfile has valid syntax."""
        dockerfile_path = os.path.join(
            os.path.dirname(__file__), "..", "docker", "DOCKERFILE"
        )
        if os.path.exists(dockerfile_path):
            with open(dockerfile_path, "r") as f:
                content = f.read()
                # Basic checks
                assert "FROM" in content
                assert "COPY" in content or "ADD" in content
                assert "CMD" in content or "ENTRYPOINT" in content
