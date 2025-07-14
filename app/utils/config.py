import configparser
import json
import os
import re

# Default values
DEFAULTS = {
    "general": {
        "dryRun": "true",
    },
    "update": {
        "delayBetweenUpdates": "2m",
    },
    "updateVerification": {
        "maxWait": "480s",
        "stableTime": "15s",
        "checkInterval": "5s",
        "gracePeriod": "15s",
    },
    "prune": {
        "removeUnusedImages": "true",
        "removeOldContainers": "true",
        "minBackupAge": "48h",
        "minBackupsToKeep": "1",
    },
    "docker": {
        "apiUrl": "https://registry.hub.docker.com/v2",
        "pageCrawlLimit": "1000",
        "pageSize": "100",
    },
    "ghcr": {
        "apiUrl": "https://ghcr.io/v2",
        "pageCrawlLimit": "1000",
        "pageSize": "100",
    },
    "logging": {"level": "INFO"},
    "rules": {
        "default": """{
            "minImageAge": "3h",
            "progressiveUpgrade": false,
            "allow": {
                "major": false,
                "minor": false,
                "patch": false,
                "build": false,
                "digest": false
            }
        }""",
        "relaxed": """{
            "minImageAge": "3h",
            "progressiveUpgrade": true,
            "allow": {
                "major": true,
                "minor": true,
                "patch": true,
                "build": true,
                "digest": true
            },
            "conditions": {
                "major": {
                    "require": ["minor", "patch", "build"]
                }
            }
        }""",
        "permissive": """{
            "minImageAge": "3h",
            "progressiveUpgrade": true,
            "allow": {
                "major": true,
                "minor": true,
                "patch": true,
                "build": true,
                "digest": true
            }
        }""",
        "strict": """{
            "minImageAge": "3h",
            "progressiveUpgrade": false,
            "allow": {
                "major": false,
                "minor": false,
                "patch": false,
                "build": false,
                "digest": false
            }
        }""",
        "patch_only": """{
            "minImageAge": "3h",
            "progressiveUpgrade": true,
            "allow": {
                "major": false,
                "minor": false,
                "patch": true,
                "build": false,
                "digest": false
            }
        }""",
        "security_only": """{
            "minImageAge": "3h",
            "progressiveUpgrade": true,
            "allow": {
                "major": false,
                "minor": false,
                "patch": true,
                "build": false,
                "digest": true
            }
        }""",
        "ci_cd": """{
            "minImageAge": "3h",
            "progressiveUpgrade": true,
            "allow": {
                "major": false,
                "minor": true,
                "patch": true,
                "build": true,
                "digest": false
            },
            "conditions": {
                "minor": {
                    "require": ["patch"]
                }
            }
        }""",
        "conservative": """{
            "minImageAge": "24h",
            "progressiveUpgrade": true,
            "allow": {
                "major": false,
                "minor": false,
                "patch": true,
                "build": true,
                "digest": false
            },
            "lagPolicy": {
                "major": 1
            }
        }""",
    },
}


class ConfigNamespace:
    def __init__(self, section: str, values: dict):
        self._section = section
        self._values = values

    def _auto_cast(self, value):
        if value is None:
            return None

        # Try boolean
        if isinstance(value, str):
            if value.lower() in ('true', 'false'):
                return value.lower() == 'true'

        # Try integer
        if isinstance(value, str) and value.isdigit():
            return int(value)

        # Try float
        try:
            return float(value)
        except (ValueError, TypeError):
            pass

        # Leave as string
        return value

    def __getattr__(self, key):
        value = (
            self._values.get(key)
            or DEFAULTS.get(self._section, {}).get(key)
        )
        return self._auto_cast(value)


class Config:
    def __init__(self, config_path: str = "/app/conf/captn.cfg"):
        parser = configparser.ConfigParser()
        parser.optionxform = lambda optionstr: str(optionstr)  # disables lowercasing of keys
        parser.read(config_path)
        self._namespaces = {}

        for section in set(DEFAULTS.keys()).union(parser.sections()):
            values = dict(DEFAULTS.get(section, {}))
            if parser.has_section(section):
                values.update(parser[section])
            self._namespaces[section] = ConfigNamespace(section, values)

        # Validate configuration after loading
        self._validate_config()

    def _validate_config(self):
        """Validate configuration structure and values."""
        errors = []

        # Validate required sections
        required_sections = ["general", "logging", "rules"]
        for section in required_sections:
            if section not in self._namespaces:
                errors.append(f"Missing required section: [{section}]")

        # Validate general section
        if "general" in self._namespaces:
            general = self._namespaces["general"]
            if hasattr(general, "dryRun"):
                if not isinstance(general.dryRun, bool):
                    errors.append("general.dryRun must be a boolean (true/false)")

        # Validate logging section
        if "logging" in self._namespaces:
            logging_config = self._namespaces["logging"]
            if hasattr(logging_config, "level"):
                valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
                if logging_config.level.upper() not in valid_levels:
                    errors.append(f"logging.level must be one of: {', '.join(valid_levels)}")

        # Validate update section
        if "update" in self._namespaces:
            update = self._namespaces["update"]
            if hasattr(update, "delayBetweenUpdates"):
                if not self._is_valid_duration(update.delayBetweenUpdates):
                    errors.append("update.delayBetweenUpdates must be a valid duration (e.g., '15s', '2m', '1h')")

        # Validate updateVerification section
        if "updateVerification" in self._namespaces:
            uv = self._namespaces["updateVerification"]
            for field in ["maxWait", "stableTime", "checkInterval", "gracePeriod"]:
                if hasattr(uv, field):
                    if not self._is_valid_duration(getattr(uv, field)):
                        errors.append(f"updateVerification.{field} must be a valid duration")

        # Validate prune section
        if "prune" in self._namespaces:
            prune = self._namespaces["prune"]
            for field in ["removeUnusedImages", "removeOldContainers"]:
                if hasattr(prune, field):
                    if not isinstance(getattr(prune, field), bool):
                        errors.append(f"prune.{field} must be a boolean (true/false)")

            if hasattr(prune, "minBackupAge"):
                if not self._is_valid_duration(prune.minBackupAge):
                    errors.append("prune.minBackupAge must be a valid duration")

            if hasattr(prune, "minBackupsToKeep"):
                if not isinstance(prune.minBackupsToKeep, int) or prune.minBackupsToKeep < 0:
                    errors.append("prune.minBackupsToKeep must be a non-negative integer")

        # Validate docker section
        if "docker" in self._namespaces:
            docker = self._namespaces["docker"]
            if hasattr(docker, "apiUrl"):
                if not self._is_valid_url(docker.apiUrl):
                    errors.append("docker.apiUrl must be a valid URL")

            for field in ["pageCrawlLimit", "pageSize"]:
                if hasattr(docker, field):
                    if not isinstance(getattr(docker, field), int) or getattr(docker, field) <= 0:
                        errors.append(f"docker.{field} must be a positive integer")

        # Validate ghcr section
        if "ghcr" in self._namespaces:
            ghcr = self._namespaces["ghcr"]
            if hasattr(ghcr, "apiUrl"):
                if not self._is_valid_url(ghcr.apiUrl):
                    errors.append("ghcr.apiUrl must be a valid URL")

            for field in ["pageCrawlLimit", "pageSize"]:
                if hasattr(ghcr, field):
                    if not isinstance(getattr(ghcr, field), int) or getattr(ghcr, field) <= 0:
                        errors.append(f"ghcr.{field} must be a positive integer")

        # Validate rules section
        if "rules" in self._namespaces:
            rules = self._namespaces["rules"]
            for rule_name, rule_json in rules._values.items():
                if not self._is_valid_json(rule_json):
                    errors.append(f"rules.{rule_name} must be valid JSON")
                else:
                    # Validate rule structure
                    try:
                        rule_data = json.loads(rule_json)
                        rule_errors = self._validate_rule_structure(rule_name, rule_data)
                        errors.extend(rule_errors)
                    except json.JSONDecodeError:
                        errors.append(f"rules.{rule_name} contains invalid JSON")

        # Raise validation errors if any found
        if errors:
            error_msg = "Configuration validation failed:\n" + "\n".join(f"  - {error}" for error in errors)
            raise ValueError(error_msg)

    def _is_valid_duration(self, value):
        """Check if a value is a valid duration string."""
        if not isinstance(value, str):
            return False
        # Pattern: number followed by unit (s, m, h, d)
        pattern = r'^\d+[smhd]$'
        return bool(re.match(pattern, value))

    def _is_valid_url(self, value):
        """Check if a value is a valid URL."""
        if not isinstance(value, str):
            return False
        # Simple URL validation
        pattern = r'^https?://[^\s/$.?#].[^\s]*$'
        return bool(re.match(pattern, value))

    def _is_valid_json(self, value):
        """Check if a value is valid JSON."""
        if not isinstance(value, str):
            return False
        try:
            json.loads(value)
            return True
        except json.JSONDecodeError:
            return False

    def _validate_rule_structure(self, rule_name, rule_data):
        """Validate the structure of a rule."""
        errors = []

        # Check required fields
        required_fields = ["minImageAge", "allow"]
        for field in required_fields:
            if field not in rule_data:
                errors.append(f"rules.{rule_name} missing required field: {field}")

        # Validate minImageAge
        if "minImageAge" in rule_data:
            if not self._is_valid_duration(rule_data["minImageAge"]):
                errors.append(f"rules.{rule_name}.minImageAge must be a valid duration")

        # Validate allow object
        if "allow" in rule_data:
            allow = rule_data["allow"]
            if not isinstance(allow, dict):
                errors.append(f"rules.{rule_name}.allow must be an object")
            else:
                valid_update_types = ["major", "minor", "patch", "build", "digest"]
                for update_type, allowed in allow.items():
                    if update_type not in valid_update_types:
                        errors.append(f"rules.{rule_name}.allow contains invalid update type: {update_type}")
                    elif not isinstance(allowed, bool):
                        errors.append(f"rules.{rule_name}.allow.{update_type} must be a boolean")

        # Validate progressiveUpgrade (optional)
        if "progressiveUpgrade" in rule_data:
            if not isinstance(rule_data["progressiveUpgrade"], bool):
                errors.append(f"rules.{rule_name}.progressiveUpgrade must be a boolean")

        return errors

    def __getattr__(self, section):
        if section not in self._namespaces:
            raise AttributeError(f"Config section '{section}' not found")
        return self._namespaces[section]


# Global instance
config = Config()
