"""
Unit tests for common utility functions.
"""

from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from app.utils.common import (
    get_container_allowed_update_types,
    get_container_backup_name,
    get_update_permit,
    get_update_type,
    normalize_version,
    parse_duration,
)


class TestNormalizeVersion:
    """Test version normalization functionality."""

    def test_normalize_version_basic(self):
        """Test basic version normalization."""
        assert normalize_version("1.2.3") == (1, 2, 3, 0)
        assert normalize_version("1.2.3.4") == (1, 2, 3, 4)
        assert normalize_version("10.20.30.40") == (10, 20, 30, 40)

    def test_normalize_version_with_prefixes(self):
        """Test version normalization with prefixes."""
        assert normalize_version("v1.2.3") == (1, 2, 3, 0)
        assert normalize_version("version-1.2.3") == (1, 2, 3, 0)
        assert normalize_version("release_1.2.3") == (1, 2, 3, 0)

    def test_normalize_version_invalid(self):
        """Test version normalization with invalid versions."""
        assert normalize_version("invalid") == (-1, -1, -1, -1)
        assert normalize_version("1.2.a") == (1, 2, 0, 0)
        assert normalize_version("") == (-1, -1, -1, -1)

    def test_normalize_version_edge_cases(self):
        """Test edge cases in version normalization."""
        assert normalize_version("1") == (1, 0, 0, 0)
        assert normalize_version("1.2") == (1, 2, 0, 0)
        assert normalize_version("1.2.3.4.5") == (1, 2, 3, 4)  # Truncate to 4 parts

    def test_normalize_version_real_world_examples(self):
        """Test real-world version formats from various software."""
        # Docker/Container versions
        assert normalize_version("1.6.6-apache") == (1, 6, 6, 0)
        assert normalize_version("28.0.5") == (28, 0, 5, 0)
        assert normalize_version("8.0.1.1") == (8, 0, 1, 1)
        assert normalize_version("8.5") == (8, 5, 0, 0)
        assert normalize_version("16.11.2-ce.0") == (16, 11, 2, 0)

        # Versioned releases
        assert normalize_version("v0.107.49") == (0, 107, 49, 0)
        assert normalize_version("ubuntu-v16.11.1") == (16, 11, 1, 0)

        # Date-based versions - extracts all numbers including build numbers
        assert normalize_version("2024-02-06a-ls220") == (2024, 2, 6, 220)
        assert normalize_version("2024-02-06a-ls220.") == (2024, 2, 6, 220)
        assert normalize_version("2024-02..06a--ls220.") == (2024, 2, 6, 220)

        # Complex version formats - extracts all numbers
        assert normalize_version("2.2.0-2023.11.04") == (2, 2, 0, 2023)
        assert normalize_version("r1605-ls185") == (1605, 185, 0, 0)

        # Ubuntu/Distribution versions
        assert normalize_version("ubuntu-kde") == (-1, -1, -1, -1)  # No numbers


class TestParseDuration:
    """Test duration parsing functionality."""

    def test_parse_duration_seconds(self):
        """Test parsing seconds."""
        assert parse_duration("30s", "s") == 30
        assert parse_duration("30s", "m") == 0.5
        assert parse_duration("30s", "h") == 1 / 120
        # Default return unit is minutes
        assert parse_duration("30s") == 0.5

    def test_parse_duration_minutes(self):
        """Test parsing minutes."""
        assert parse_duration("30m") == 30
        assert parse_duration("30m", "s") == 1800
        assert parse_duration("30m", "h") == 0.5
        assert parse_duration("30m", "d") == 1 / 48

    def test_parse_duration_hours(self):
        """Test parsing hours."""
        assert parse_duration("2h", "h") == 2
        assert parse_duration("2h", "s") == 7200
        assert parse_duration("2h", "m") == 120
        assert parse_duration("2h", "d") == 1 / 12
        # Default return unit is minutes
        assert parse_duration("2h") == 120

    def test_parse_duration_days(self):
        """Test parsing days."""
        assert parse_duration("1d", "d") == 1
        assert parse_duration("1d", "s") == 86400
        assert parse_duration("1d", "m") == 1440
        assert parse_duration("1d", "h") == 24
        # Default return unit is minutes
        assert parse_duration("1d") == 1440

    def test_parse_duration_invalid(self):
        """Test parsing invalid durations."""
        with pytest.raises(ValueError):
            parse_duration("invalid")
        with pytest.raises(ValueError):
            parse_duration("30")
        with pytest.raises(ValueError):
            parse_duration("30x")


class TestGetUpdateType:
    """Test update type determination."""

    def test_get_update_type_major(self):
        """Test major version update detection."""
        result = get_update_type("1.0.0", "2.0.0", ["sha256:abc123"], "sha256:def456")
        assert result == "major"

    def test_get_update_type_minor(self):
        """Test minor version update detection."""
        result = get_update_type("1.0.0", "1.1.0", ["sha256:abc123"], "sha256:def456")
        assert result == "minor"

    def test_get_update_type_patch(self):
        """Test patch version update detection."""
        result = get_update_type("1.0.0", "1.0.1", ["sha256:abc123"], "sha256:def456")
        assert result == "patch"

    def test_get_update_type_build(self):
        """Test build version update detection."""
        result = get_update_type("1.0.0", "1.0.0.1", ["sha256:abc123"], "sha256:def456")
        assert result == "build"

    def test_get_update_type_digest(self):
        """Test digest-only update detection."""
        result = get_update_type("1.0.0", "1.0.0", ["sha256:abc123"], "sha256:def456")
        assert result == "digest"

    def test_get_update_type_no_update(self):
        """Test no update detection."""
        result = get_update_type("1.0.0", "1.0.0", ["sha256:abc123"], "sha256:abc123")
        assert result is None

    def test_get_update_type_unknown(self):
        """Test unknown update type."""
        result = get_update_type("invalid", "also-invalid", ["sha256:abc123"], "sha256:def456")
        assert result == "unknown"


class TestGetContainerBackupName:
    """Test backup container name generation."""

    def test_get_container_backup_name(self):
        """Test backup name generation."""
        with patch("app.utils.common.datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 1, 1, 12, 0, 0)
            result = get_container_backup_name("test-container")
            assert result == "test-container_bak_cu_20240101-120000"


class TestGetUpdatePermit:
    """Test update permission logic."""

    def test_get_update_permit_allowed(self):
        """Test when update is allowed."""
        # Create a simple test config

        # Mock the config with a simple structure
        with patch("app.utils.common.config") as mock_config:
            # Create mock sections
            mock_rules = Mock()
            mock_rules._values = {"default": '{"allow": {"patch": true}}'}

            mock_assignments_by_name = Mock()
            mock_assignments_by_name._values = {}

            mock_assignments_by_image = Mock()
            mock_assignments_by_image._values = {}

            mock_assignments_by_id = Mock()
            mock_assignments_by_id._values = {}

            # Set up the mock config
            mock_config.rules = mock_rules
            mock_config.assignmentsByName = mock_assignments_by_name
            mock_config.assignmentsByImage = mock_assignments_by_image
            mock_config.assignmentsById = mock_assignments_by_id

            allowed, rule_name, original_rule, reason, image_ref = get_update_permit(
                container_name="test-container",
                image_reference="nginx:1.0.0",
                update_type="patch",
                age=60,
                old_version="1.0.0",
                new_version="1.0.1",
                latest_version="1.0.1",
            )

            assert allowed is True
            assert rule_name == "default"

    def test_get_update_permit_denied(self):
        """Test when update is denied."""
        with patch("app.utils.common.config") as mock_config:
            # Create mock sections
            mock_rules = Mock()
            mock_rules._values = {"default": '{"allow": {"patch": false}}'}

            mock_assignments_by_name = Mock()
            mock_assignments_by_name._values = {}

            mock_assignments_by_image = Mock()
            mock_assignments_by_image._values = {}

            mock_assignments_by_id = Mock()
            mock_assignments_by_id._values = {}

            # Set up the mock config
            mock_config.rules = mock_rules
            mock_config.assignmentsByName = mock_assignments_by_name
            mock_config.assignmentsByImage = mock_assignments_by_image
            mock_config.assignmentsById = mock_assignments_by_id

            allowed, rule_name, original_rule, reason, image_ref = get_update_permit(
                container_name="test-container",
                image_reference="nginx:1.0.0",
                update_type="patch",
                age=60,
                old_version="1.0.0",
                new_version="1.0.1",
                latest_version="1.0.1",
            )

            assert allowed is False
            assert rule_name == "default"


class TestGetContainerAllowedUpdateTypes:
    """Test getting allowed update types for containers."""

    def test_get_container_allowed_update_types(self):
        """Test getting allowed update types."""
        with patch("app.utils.common.config") as mock_config:
            # Create mock sections
            mock_rules = Mock()
            mock_rules._values = {"default": '{"allow": {"patch": true, "minor": false}}'}

            mock_assignments_by_name = Mock()
            mock_assignments_by_name._values = {}

            mock_assignments_by_image = Mock()
            mock_assignments_by_image._values = {}

            mock_assignments_by_id = Mock()
            mock_assignments_by_id._values = {}

            # Set up the mock config
            mock_config.rules = mock_rules
            mock_config.assignmentsByName = mock_assignments_by_name
            mock_config.assignmentsByImage = mock_assignments_by_image
            mock_config.assignmentsById = mock_assignments_by_id

            allowed_types, rule_name, original_rule = get_container_allowed_update_types("test-container")

            assert "patch" in allowed_types
            assert "minor" not in allowed_types
            assert rule_name == "default"
