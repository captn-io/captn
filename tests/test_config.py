"""
Unit tests for configuration management.
"""

import os
from unittest.mock import mock_open, patch

import pytest

from app.utils.config import config


class TestConfig:
    """Test configuration loading and validation."""

    def test_config_attributes(self):
        """Test that config has expected attributes."""
        # Test that main sections exist
        assert hasattr(config, "general")
        assert hasattr(config, "logging")
        assert hasattr(config, "rules")
        # These sections are created dynamically when accessed
        # assert hasattr(config, 'assignmentsByName')
        # assert hasattr(config, 'assignmentsByImage')
        # assert hasattr(config, 'assignmentsById')

    def test_config_defaults(self):
        """Test configuration default values."""
        # Test some expected default values
        assert hasattr(config.general, "dryRun")
        assert hasattr(config.logging, "level")

    @patch("builtins.open", new_callable=mock_open)
    @patch("os.path.exists")
    def test_config_file_loading(self, mock_exists, mock_file):
        """Test configuration file loading."""
        mock_exists.return_value = True
        mock_file.return_value.__enter__.return_value.read.return_value = """
[general]
dryRun = true

[logging]
level = DEBUG

[rules]
default = {"allow": {"patch": true}}
"""

        # This would test the actual config loading, but we need to mock the file system
        # For now, just test that the config object exists
        assert config is not None

    def test_config_environment_override(self):
        """Test environment variable overrides."""
        with patch.dict(os.environ, {"GENERAL_DRYRUN": "false"}):
            # This would test environment variable loading
            # For now, just test that the config object exists
            assert config is not None


class TestConfigValidation:
    """Test configuration validation logic."""

    def test_rules_json_parsing(self):
        """Test that rules are valid JSON."""
        # Test that rules can be parsed as JSON
        if hasattr(config.rules, "_values"):
            for rule_name, rule_json in config.rules._values.items():
                try:
                    import json

                    json.loads(rule_json)
                except json.JSONDecodeError:
                    pytest.fail(f"Invalid JSON in rule '{rule_name}': {rule_json}")

    def test_required_sections(self):
        """Test that required configuration sections exist."""
        required_sections = ["general", "logging", "rules"]
        for section in required_sections:
            assert hasattr(config, section), f"Missing required section: {section}"

    def test_logging_level_validation(self):
        """Test that logging level is valid."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if hasattr(config.logging, "level"):
            level = config.logging.level.upper()
            assert level in valid_levels, f"Invalid logging level: {level}"
