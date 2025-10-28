import configparser
import json
import os
import re
import logging

# Default values
DEFAULTS = {
    "general": {
        "dryRun": "false",
        "cronSchedule": "30 2 * * *",
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
        "removeUnusedImages": "false",
        "removeOldContainers": "true",
        "minBackupAge": "48h",
        "minBackupsToKeep": "1",
    },
    "selfUpdate": {
        "removeHelperContainer": "true",
    },
    "preScripts": {
        "enabled": "true",
        "scriptsDirectory": "/app/conf/scripts",
        "timeout": "5m",
        "continueOnFailure": "false",
    },
    "postScripts": {
        "enabled": "true",
        "scriptsDirectory": "/app/conf/scripts",
        "timeout": "5m",
        "rollbackOnFailure": "true",
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
    "registryAuth": {
        "enabled": "false",
        "credentialsFile": "/app/conf/registry-credentials.json",
    },
    "envFiltering": {
        "enabled": "true",
        "excludePatterns": """[
        ]""",
        "preservePatterns": """[
        ]""",
        "containerSpecificRules": """{
        }"""
    },
    "notifiers": {
        "enabled": "false",
    },
    "notifiers.telegram": {
        "enabled": "false",
        "token": "",
        "chatId": "",
    },
    "notifiers.email": {
        "enabled": "false",
        "smtpServer": "",
        "smtpPort": "587",
        "username": "",
        "password": "",
        "fromAddr": "",
        "toAddr": "",
        "timeout": "30",
    },
    "rules": {
        "default": """{
            "minImageAge": "3h",
            "progressiveUpgrade": false,
            "allow": {
                "major": false,
                "minor": false,
                "patch": false,
                "build": false,
                "digest": false,
                "scheme_change": false
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
                "digest": true,
                "scheme_change": false
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
                "digest": true,
                "scheme_change": false
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
                "digest": false,
                "scheme_change": false
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
                "digest": false,
                "scheme_change": false
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
                "digest": true,
                "scheme_change": false
            }
        }""",
        "digest_only": """{
            "minImageAge": "3h",
            "progressiveUpgrade": true,
            "allow": {
                "major": false,
                "minor": false,
                "patch": false,
                "build": false,
                "digest": true,
                "scheme_change": false
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
                "digest": false,
                "scheme_change": false
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
                "digest": false,
                "scheme_change": false
            },
            "lagPolicy": {
                "major": 1
            }
        }""",
    },
}


class ConfigNamespace:
    """
    A namespace wrapper for configuration sections that provides automatic type casting.

    This class wraps configuration sections and automatically casts string values
    to appropriate Python types (boolean, integer, float) while preserving the
    original string format for values that can't be automatically converted.
    """

    def __init__(self, section: str, values: dict):
        """
        Initialize a configuration namespace.

        Parameters:
            section (str): Name of the configuration section
            values (dict): Dictionary of configuration values
        """
        self._section = section
        self._values = values

    def auto_cast(self, value):
        """
        Automatically cast a string value to the appropriate Python type.

        Parameters:
            value: The value to cast

        Returns:
            The casted value (bool, int, float, or str)
        """
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
        """
        Get a configuration value with automatic type casting.

        Parameters:
            key (str): Configuration key to retrieve

        Returns:
            The configuration value with appropriate type
        """
        value = (
            self._values.get(key)
            or DEFAULTS.get(self._section, {}).get(key)
        )
        return self.auto_cast(value)


class Config:
    """
    Main configuration manager for the captn application.

    This class handles loading, parsing, and validating configuration files.
    It provides access to configuration sections through attribute-style access
    and includes comprehensive validation of configuration values.
    """

    def __init__(self, config_path: str = "/app/conf/captn.cfg"):
        """
        Initialize the configuration manager.

        Parameters:
            config_path (str): Path to the configuration file
        """
        self.config_path = config_path
        self.load_config()

    def load_config(self):
        """
        Load configuration from file.

        This method reads the configuration file, merges it with default values,
        and validates the resulting configuration structure.
        """
        parser = configparser.ConfigParser()
        parser.optionxform = lambda optionstr: str(optionstr)  # disables lowercasing of keys
        parser.read(self.config_path)
        self._namespaces = {}

        for section in set(DEFAULTS.keys()).union(parser.sections()):
            values = dict(DEFAULTS.get(section, {}))
            if parser.has_section(section):
                values.update(parser[section])
            self._namespaces[section] = ConfigNamespace(section, values)

        # Dot-notation support: e.g. notifiers.telegram will be available as attribute of `notifiers`
        for section in list(self._namespaces.keys()):
            if '.' in section:
                parent, child = section.split('.', 1)
                if parent in self._namespaces:
                    setattr(self._namespaces[parent], child, self._namespaces[section])

        # Validate configuration after loading
        self.validate_config()

    def reload(self):
        """
        Reload configuration from disk.

        This method re-reads the configuration file and updates the internal
        configuration state. Useful for runtime configuration changes.

        Returns:
            bool: True if reload was successful, False otherwise
        """
        try:
            self.load_config()
            return True
        except Exception as e:
            logging.error(f"Failed to reload configuration: {e}")
            return False

    def validate_config(self):
        """
        Validate configuration structure and values.

        This method performs comprehensive validation of the configuration,
        checking for required sections, valid data types, and proper formatting.
        Raises ValueError with detailed error messages if validation fails.
        """
        errors = []

        # Validate required sections
        required_sections = ["general", "logging", "rules", "notifiers"]
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
                if not self.is_valid_duration(update.delayBetweenUpdates):
                    errors.append("update.delayBetweenUpdates must be a valid duration (e.g., '15s', '2m', '1h')")

        # Validate updateVerification section
        if "updateVerification" in self._namespaces:
            uv = self._namespaces["updateVerification"]
            for field in ["maxWait", "stableTime", "checkInterval", "gracePeriod"]:
                if hasattr(uv, field):
                    if not self.is_valid_duration(getattr(uv, field)):
                        errors.append(f"updateVerification.{field} must be a valid duration")

        # Validate prune section
        if "prune" in self._namespaces:
            prune = self._namespaces["prune"]
            for field in ["removeUnusedImages", "removeOldContainers"]:
                if hasattr(prune, field):
                    if not isinstance(getattr(prune, field), bool):
                        errors.append(f"prune.{field} must be a boolean (true/false)")

            if hasattr(prune, "minBackupAge"):
                if not self.is_valid_duration(prune.minBackupAge):
                    errors.append("prune.minBackupAge must be a valid duration")

            if hasattr(prune, "minBackupsToKeep"):
                if not isinstance(prune.minBackupsToKeep, int) or prune.minBackupsToKeep < 0:
                    errors.append("prune.minBackupsToKeep must be a non-negative integer")

        # Validate selfUpdate section
        if "selfUpdate" in self._namespaces:
            self_update = self._namespaces["selfUpdate"]
            if hasattr(self_update, "removeHelperContainer"):
                if not isinstance(self_update.removeHelperContainer, bool):
                    errors.append("selfUpdate.removeHelperContainer must be a boolean (true/false)")

        # Validate preScripts section
        if "preScripts" in self._namespaces:
            pre_scripts = self._namespaces["preScripts"]
            if hasattr(pre_scripts, "enabled"):
                if not isinstance(pre_scripts.enabled, bool):
                    errors.append("preScripts.enabled must be a boolean (true/false)")

            if hasattr(pre_scripts, "timeout"):
                if not self.is_valid_duration(pre_scripts.timeout):
                    errors.append("preScripts.timeout must be a valid duration")

            if hasattr(pre_scripts, "continueOnFailure"):
                if not isinstance(pre_scripts.continueOnFailure, bool):
                    errors.append("preScripts.continueOnFailure must be a boolean (true/false)")

        # Validate postScripts section
        if "postScripts" in self._namespaces:
            post_scripts = self._namespaces["postScripts"]
            if hasattr(post_scripts, "enabled"):
                if not isinstance(post_scripts.enabled, bool):
                    errors.append("postScripts.enabled must be a boolean (true/false)")

            if hasattr(post_scripts, "timeout"):
                if not self.is_valid_duration(post_scripts.timeout):
                    errors.append("postScripts.timeout must be a valid duration")

            if hasattr(post_scripts, "rollbackOnFailure"):
                if not isinstance(post_scripts.rollbackOnFailure, bool):
                    errors.append("postScripts.rollbackOnFailure must be a boolean (true/false)")

        # Validate docker section
        if "docker" in self._namespaces:
            docker = self._namespaces["docker"]
            if hasattr(docker, "apiUrl"):
                if not self.is_valid_url(docker.apiUrl):
                    errors.append("docker.apiUrl must be a valid URL")

            for field in ["pageCrawlLimit", "pageSize"]:
                if hasattr(docker, field):
                    if not isinstance(getattr(docker, field), int) or getattr(docker, field) <= 0:
                        errors.append(f"docker.{field} must be a positive integer")

        # Validate ghcr section
        if "ghcr" in self._namespaces:
            ghcr = self._namespaces["ghcr"]
            if hasattr(ghcr, "apiUrl"):
                if not self.is_valid_url(ghcr.apiUrl):
                    errors.append("ghcr.apiUrl must be a valid URL")

            for field in ["pageCrawlLimit", "pageSize"]:
                if hasattr(ghcr, field):
                    if not isinstance(getattr(ghcr, field), int) or getattr(ghcr, field) <= 0:
                        errors.append(f"ghcr.{field} must be a positive integer")

        # Validate registryAuth section
        if "registryAuth" in self._namespaces:
            auth = self._namespaces["registryAuth"]
            if hasattr(auth, "enabled"):
                if not isinstance(auth.enabled, bool):
                    errors.append("registryAuth.enabled must be a boolean (true/false)")

                                # Only validate credentials file if authentication is enabled
                if auth.enabled and hasattr(auth, "credentialsFile"):
                    if not isinstance(auth.credentialsFile, str) or not os.path.exists(auth.credentialsFile):
                        errors.append(f"registryAuth.credentialsFile must be a valid path to a JSON file")

        # Validate envFiltering section
        if "envFiltering" in self._namespaces:
            env_filter = self._namespaces["envFiltering"]
            if hasattr(env_filter, "enabled"):
                if not isinstance(env_filter.enabled, bool):
                    errors.append("envFiltering.enabled must be a boolean (true/false)")

            # Validate excludePatterns
            if hasattr(env_filter, "excludePatterns"):
                if not self.is_valid_json(env_filter.excludePatterns):
                    errors.append("envFiltering.excludePatterns must be valid JSON array")
                else:
                    try:
                        patterns = json.loads(env_filter.excludePatterns)
                        if not isinstance(patterns, list):
                            errors.append("envFiltering.excludePatterns must be a JSON array")
                        else:
                            for pattern in patterns:
                                if not isinstance(pattern, str):
                                    errors.append("envFiltering.excludePatterns must contain only strings")
                    except json.JSONDecodeError:
                        errors.append("envFiltering.excludePatterns contains invalid JSON")

            # Validate preservePatterns
            if hasattr(env_filter, "preservePatterns"):
                if not self.is_valid_json(env_filter.preservePatterns):
                    errors.append("envFiltering.preservePatterns must be valid JSON array")
                else:
                    try:
                        patterns = json.loads(env_filter.preservePatterns)
                        if not isinstance(patterns, list):
                            errors.append("envFiltering.preservePatterns must be a JSON array")
                        else:
                            for pattern in patterns:
                                if not isinstance(pattern, str):
                                    errors.append("envFiltering.preservePatterns must contain only strings")
                    except json.JSONDecodeError:
                        errors.append("envFiltering.preservePatterns contains invalid JSON")

            # Validate containerSpecificRules
            if hasattr(env_filter, "containerSpecificRules"):
                if not self.is_valid_json(env_filter.containerSpecificRules):
                    errors.append("envFiltering.containerSpecificRules must be valid JSON object")
                else:
                    try:
                        rules = json.loads(env_filter.containerSpecificRules)
                        if not isinstance(rules, dict):
                            errors.append("envFiltering.containerSpecificRules must be a JSON object")
                        else:
                            for container_name, rule_data in rules.items():
                                if not isinstance(rule_data, dict):
                                    errors.append(f"envFiltering.containerSpecificRules.{container_name} must be an object")
                                else:
                                    for rule_type in ["excludePatterns", "preservePatterns"]:
                                        if rule_type in rule_data:
                                            if not isinstance(rule_data[rule_type], list):
                                                errors.append(f"envFiltering.containerSpecificRules.{container_name}.{rule_type} must be an array")
                                            else:
                                                for pattern in rule_data[rule_type]:
                                                    if not isinstance(pattern, str):
                                                        errors.append(f"envFiltering.containerSpecificRules.{container_name}.{rule_type} must contain only strings")
                    except json.JSONDecodeError:
                        errors.append("envFiltering.containerSpecificRules contains invalid JSON")

        # Validate rules section
        if "rules" in self._namespaces:
            rules = self._namespaces["rules"]
            for rule_name, rule_json in rules._values.items():
                if not self.is_valid_json(rule_json):
                    errors.append(f"rules.{rule_name} must be valid JSON")
                else:
                    # Validate rule structure
                    try:
                        rule_data = json.loads(rule_json)
                        rule_errors = self.validate_rule_structure(rule_name, rule_data)
                        errors.extend(rule_errors)
                    except json.JSONDecodeError:
                        errors.append(f"rules.{rule_name} contains invalid JSON")

        # Validate notifiers section
        if "notifiers" in self._namespaces:
            notifiers = self._namespaces["notifiers"]
            if hasattr(notifiers, "enabled") and not isinstance(notifiers.enabled, bool):
                errors.append("notifiers.enabled must be a boolean (true/false)")

        # Validate notifiers.telegram
        if "notifiers.telegram" in self._namespaces:
            tg = self._namespaces["notifiers.telegram"]
            if hasattr(tg, "enabled") and not isinstance(tg.enabled, bool):
                errors.append("notifiers.telegram.enabled must be a boolean (true/false)")
            if tg.enabled:
                if not isinstance(tg.token, str) or not tg.token:
                    errors.append("notifiers.telegram.token must be set if enabled")
                if not (isinstance(tg.chatId, str) or isinstance(tg.chatId, int)) or not tg.chatId:
                    errors.append("notifiers.telegram.chatId must be set if enabled")

        # Validate notifiers.email
        if "notifiers.email" in self._namespaces:
            em = self._namespaces["notifiers.email"]
            if hasattr(em, "enabled") and not isinstance(em.enabled, bool):
                errors.append("notifiers.email.enabled must be a boolean (true/false)")

            if em.enabled:
                if not isinstance(em.smtpServer, str) or not em.smtpServer:
                    errors.append("notifiers.email.smtpServer must be set if email notifications are enabled")
                if not isinstance(em.smtpPort, (str, int)) or not str(em.smtpPort).isdigit():
                    errors.append("notifiers.email.smtpPort must be a valid port number")
                if not isinstance(em.fromAddr, str) or not em.fromAddr:
                    errors.append("notifiers.email.fromAddr must be set if email notifications are enabled")
                if not isinstance(em.toAddr, str) or not em.toAddr:
                    errors.append("notifiers.email.toAddr must be set if email notifications are enabled")
                if not isinstance(em.username, str):
                    errors.append("notifiers.email.username must be a string")
                if not isinstance(em.password, str):
                    errors.append("notifiers.email.password must be a string")

        # Raise validation errors if any found
        if errors:
            error_msg = "Configuration validation failed:\n" + "\n".join(f"  - {error}" for error in errors)
            raise ValueError(error_msg)

    def is_valid_duration(self, value):
        """
        Check if a value is a valid duration string.

        Parameters:
            value: The value to validate

        Returns:
            bool: True if the value is a valid duration string (e.g., "10m", "2h")
        """
        if not isinstance(value, str):
            return False
        # Pattern: number followed by unit (s, m, h, d)
        pattern = r'^\d+[smhd]$'
        return bool(re.match(pattern, value))

    def is_valid_url(self, value):
        """
        Check if a value is a valid URL.

        Parameters:
            value: The value to validate

        Returns:
            bool: True if the value is a valid HTTP/HTTPS URL
        """
        if not isinstance(value, str):
            return False
        # Simple URL validation
        pattern = r'^https?://[^\s/$.?#].[^\s]*$'
        return bool(re.match(pattern, value))

    def is_valid_json(self, value):
        """
        Check if a value is valid JSON.

        Parameters:
            value: The value to validate

        Returns:
            bool: True if the value is valid JSON string
        """
        if not isinstance(value, str):
            return False
        try:
            json.loads(value)
            return True
        except json.JSONDecodeError:
            return False

    def validate_rule_structure(self, rule_name, rule_data):
        """
        Validate the structure of a rule.

        This method validates that a rule object contains all required fields
        and that the values are of the correct types and formats.

        Parameters:
            rule_name (str): Name of the rule being validated
            rule_data (dict): Rule data to validate

        Returns:
            list: List of validation error messages (empty if valid)
        """
        errors = []

        # Check required fields
        required_fields = ["minImageAge", "allow"]
        for field in required_fields:
            if field not in rule_data:
                errors.append(f"rules.{rule_name} missing required field: {field}")

        # Validate minImageAge
        if "minImageAge" in rule_data:
            if not self.is_valid_duration(rule_data["minImageAge"]):
                errors.append(f"rules.{rule_name}.minImageAge must be a valid duration")

        # Validate allow object
        if "allow" in rule_data:
            allow = rule_data["allow"]
            if not isinstance(allow, dict):
                errors.append(f"rules.{rule_name}.allow must be an object")
            else:
                valid_update_types = ["major", "minor", "patch", "build", "digest", "scheme_change"]
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
        """
        Get a configuration section by name.

        Parameters:
            section (str): Name of the configuration section

        Returns:
            ConfigNamespace: Configuration namespace for the requested section

        Raises:
            AttributeError: If the section doesn't exist
        """
        if section not in self._namespaces:
            raise AttributeError(f"Config section '{section}' not found")
        return self._namespaces[section]


def create_example_config(example_path: str = "/app/conf/captn.example.cfg"):
    """
    Create or update the captn.example.cfg file with current default values and documentation.

    This function generates a comprehensive example configuration file that includes
    all available configuration options with detailed descriptions and their default values.
    It ensures the example config file is always up-to-date with the latest configuration
    options and their documentation.

    Parameters:
        example_path (str): Path where the example configuration file should be created
    """

    example_content = """# captn Configuration Example
# ===========================
#
# This file contains all available configuration options for captn with detailed
# descriptions and their default values. Copy this file to 'captn.cfg' and modify
# the settings according to your needs.
#
# File location: /app/conf/captn.cfg
#
# Note: All boolean values should be 'true' or 'false' (lowercase)
#       Duration values use format: number + unit (s=seconds, m=minutes, h=hours, d=days)
#       Example: '30s', '2m', '1h', '24h', '1d'

[general]
# Enable dry-run mode (no actual container updates will be performed)
# This is useful for testing and seeing what captn would do without making changes
# Possible values: true, false
# Default: false
dryRun = false

# Cron schedule for automatic updates when running in daemon mode
# Format: minute hour day month weekday
# Examples:
#   "30 2 * * *"     - Daily at 2:30 AM
#   "0 */6 * * *"    - Every 6 hours
#   "*/5 * * * *"    - Every 5 minutes
#   "0 2 * * 0"      - Weekly on Sunday at 2:00 AM
# Default: "30 2 * * *" (daily at 2:30 AM)
cronSchedule = 30 2 * * *

[notifiers]
# Enable/disable all notifications globally
# Possible values: true, false
# Default: false
enabled = false

[notifiers.telegram]
# Enable Telegram notifications
# Possible values: true, false
# Default: false
enabled = false
# Telegram bot token (from @BotFather)
token =
# Telegram chat ID (can be user or group)
chatId =

[notifiers.email]
# Enable email notifications
# This enables SMTP-based email notifications with detailed HTML reports
# Possible values: true, false
# Default: false
enabled = false
# SMTP server address
# The hostname or IP address of your SMTP server
# Common examples: smtp.gmail.com, smtp.strato.de, mail.yourdomain.com
# Possible values: String (hostname or IP address)
#   Examples: smtp.gmail.com, smtp.strato.de, mail.yourdomain.com
# Default: "" (empty)
smtpServer =
# SMTP server port
# The port number for SMTP communication
# Common ports: 587 (TLS), 465 (SSL), 25 (unencrypted, not recommended)
# Possible values: Integer
#   Common: 587 (TLS), 465 (SSL)
#   Examples: 587, 465, 25
# Default: 587
smtpPort = 587
# SMTP username
# Your email account username for SMTP authentication
# For Gmail, use your full email address
# For other providers, check their documentation
# Possible values: String
#   Examples: your-email@gmail.com, username@yourdomain.com
# Default: "" (empty)
username =
# SMTP password
# Your email account password or app-specific password
# For Gmail, use an App Password (not your regular password)
# For other providers, use your account password or app password
# Possible values: String
#   Examples: your-app-password, your-account-password
# Default: "" (empty)
password =
# Sender address
# The email address that will appear as the sender
# Should match your SMTP account or be authorized to send from this address
# Possible values: String (valid email address)
#   Examples: captn@yourdomain.com, your-email@gmail.com
# Default: "" (empty)
fromAddr =
# Recipient address
# The email address that will receive the update reports
# Can be the same as fromAddr or a different address
# Possible values: String (valid email address)
#   Examples: admin@yourdomain.com, your-email@gmail.com
# Default: "" (empty)
toAddr =
# SMTP connection timeout in seconds
# This prevents the application from hanging if the SMTP server is slow to respond
# Increase this value if you experience timeout issues with slow SMTP servers
# Possible values: Integer
#   Minimum: 10
#   Maximum: 300
#   Examples: 30, 60, 120
# Default: 30
timeout = 30

[update]
# Delay between container updates to avoid overwhelming the system
# This prevents too many containers from being updated simultaneously
# Possible values: Duration format (number + unit: s=seconds, m=minutes, h=hours, d=days)
#   Minimum: 1s
#   Maximum: -
#   Examples: "30s", "2m", "1h", "24h"
# Default: "2m" (2 minutes)
delayBetweenUpdates = 2m

[updateVerification]
# Maximum time to wait for a container to become stable after update
# If container doesn't become stable within this time, it's considered failed
# Possible values: Duration format (number + unit: s=seconds, m=minutes, h=hours, d=days)
#   Minimum: 10s
#   Maximum: -
#   Examples: "60s", "5m", "10m", "30m"
# Default: "480s" (8 minutes)
maxWait = 480s

# Time a container must remain stable before considering the update successful
# This helps ensure the container is truly stable and not just temporarily running
# Possible values: Duration format (number + unit: s=seconds, m=minutes, h=hours, d=days)
#   Minimum: 5s
#   Maximum: -
#   Examples: "10s", "30s", "1m", "2m"
# Default: "15s" (15 seconds)
stableTime = 15s

# Interval between stability checks during update verification
# Shorter intervals provide faster feedback but use more resources
# Possible values: Duration format (number + unit: s=seconds, m=minutes, h=hours, d=days)
#   Minimum: 1s
#   Maximum: -
#   Examples: "2s", "5s", "10s", "30s"
# Default: "5s" (5 seconds)
checkInterval = 5s

# Additional time to wait after container becomes stable before proceeding
# This provides a buffer to catch any late failures
# Possible values: Duration format (number + unit: s=seconds, m=minutes, h=hours, d=days)
#   Minimum: 0s
#   Maximum: -
#   Examples: "5s", "15s", "30s", "1m"
# Default: "15s" (15 seconds)
gracePeriod = 15s

[prune]
# Remove unused Docker images after successful updates
# This helps keep the system clean and save disk space
# Possible values: true, false
# Default: false
removeUnusedImages = false

# Remove old stopped containers after successful updates
# This helps maintain a clean container environment
#
# Backup containers are identified by:
# - Container name contains "_bak_cu_" (backup container-updater)
# - Container status is "exited"
# - Container name ends with timestamp format: YYYYMMDD-HHMMSS
# Example backup container names: "myapp_bak_cu_20241201-143022"
#
# Only containers older than minBackupAge and meeting the minimum backup count
# requirements will be removed.
# Possible values: true, false
# Default: true
removeOldContainers = true

# Minimum age a backed up container must reach before it can be deleted
# Backup containers younger than this value will always be kept, regardless of other settings
# Possible values: Duration format (number + unit: s=seconds, m=minutes, h=hours, d=days)
#   Minimum: 0s (immediate deletion allowed)
#   Maximum: -
#   Examples: "1h", "6h", "24h", "48h", "7d"
# Default: "48h" (48 hours)
minBackupAge = 48h

# Minimum number of backups to keep for each container
# Even if backups are older than minBackupAge, this many will be preserved
# Possible values: Integer
#   Minimum: 0 (no backups kept)
#   Maximum: -
#   Examples: 0, 1, 3, 5, 10
# Default: 1
minBackupsToKeep = 1

[selfUpdate]
# Remove helper containers after successful self-updates
# Helper containers are temporary containers created during self-update operations
# to perform the actual update of the captn container itself
# Possible values: true, false
#   true:  Helper container is automatically removed after completion (default)
#   false: Helper container remain for manual inspection
# Default: true
removeHelperContainer = true

[preScripts]
# Enable pre-update script execution
# Pre-scripts are executed before container updates and can perform tasks like
# backups, health checks, or other preparatory actions
# Possible values: true, false
# Default: true
enabled = true

# Directory containing pre-update scripts
# Scripts can be container-specific (e.g., "myapp_pre.sh") or generic ("pre.sh")
# Container-specific scripts take precedence over generic scripts
# Default: /app/conf/scripts
scriptsDirectory = /app/conf/scripts

# Timeout for pre-script execution in seconds
# If a script doesn't complete within this time, it will be terminated
# Possible values: Duration format (number + unit: s=seconds, m=minutes, h=hours, d=days)
#   Minimum: 0s (immediate deletion allowed)
#   Maximum: -
#   Examples: "30s", "5m", "1h", "1d"
# Default: 5m (5 minutes)
timeout = 5m

# Whether to continue with the update if pre-script fails
# If false, the update process will be aborted when pre-script fails
# If true, the update will proceed even if pre-script fails
# Possible values: true, false
# Default: false (abort on failure)
continueOnFailure = false

[postScripts]
# Enable post-update script execution
# Post-scripts are executed after successful container updates and can perform
# tasks like health checks, notifications, or cleanup actions
# Possible values: true, false
# Default: true
enabled = true

# Directory containing post-update scripts
# Scripts can be container-specific (e.g., "myapp_post.sh") or generic ("post.sh")
# Container-specific scripts take precedence over generic scripts
# Default: /app/conf/scripts
scriptsDirectory = /app/conf/scripts

# Timeout for post-script execution in seconds
# If a script doesn't complete within this time, it will be terminated
# Possible values: Duration format (number + unit: s=seconds, m=minutes, h=hours, d=days)
#   Minimum: 0s (immediate deletion allowed)
#   Maximum: -
#   Examples: "30s", "5m", "1h", "1d"
# Default: 5m (5 minutes)
timeout = 5m

# Whether to rollback the container if post-script fails
# If true, the container will be rolled back to the previous version if post-script fails
# If false, the update will be considered successful even if post-script fails
# Possible values: true, false
# Default: true (rollback on failure)
rollbackOnFailure = true

[docker]
# Docker Hub API URL for fetching image metadata
# Usually doesn't need to be changed unless using a custom registry
# Possible values: Valid HTTP/HTTPS URL
#   Examples: "https://registry.hub.docker.com/v2", "https://custom.registry.com/v2"
# Default: "https://registry.hub.docker.com/v2"
apiUrl = https://registry.hub.docker.com/v2

# Maximum number of pages to crawl when searching for images
# Higher values allow finding older images but increase API usage
# Possible values: Integer
#   Minimum: 1
#   Maximum: 1000
#   Examples: 100, 500, 1000
# Default: 1000
pageCrawlLimit = 1000

# Number of images to fetch per API request
# Higher values reduce API calls but increase memory usage
# Possible values: Integer
#   Minimum: 1
#   Maximum: 100
#   Examples: 10, 50, 100
# Default: 100
pageSize = 100

[ghcr]
# GitHub Container Registry API URL for fetching image metadata
# Usually doesn't need to be changed
# Possible values: Valid HTTP/HTTPS URL
#   Examples: "https://ghcr.io/v2", "https://custom.ghcr.com/v2"
# Default: "https://ghcr.io/v2"
apiUrl = https://ghcr.io/v2

# Maximum number of pages to crawl when searching for images
# Higher values allow finding older images but increase API usage
# Possible values: Integer
#   Minimum: 1
#   Maximum: 1000
#   Examples: 100, 500, 1000
# Default: 1000
pageCrawlLimit = 1000

# Number of images to fetch per API request
# Higher values reduce API calls but increase memory usage
# Possible values: Integer
#   Minimum: 1
#   Maximum: 100
#   Examples: 10, 50, 100
# Default: 100
pageSize = 100

[logging]
# Logging level for captn
# Possible values: DEBUG, INFO, WARNING, ERROR, CRITICAL
#   DEBUG:      Most verbose, shows all details
#   INFO:       Standard information level (recommended)
#   WARNING:    Only warnings and errors
#   ERROR:      Only errors
#   CRITICAL:   Only critical errors
# Default: "INFO"
level = INFO

[registryAuth]
# Enable registry authentication for private container repositories
# This allows captn to authenticate with private registries using credentials
# Possible values: true, false
# Default: false
enabled = false

# Path to a JSON file containing registry credentials.
# The file must be a JSON object with two top-level keys: "registries" and "repositories".
# - "registries" maps registry API URLs to their authentication credentials (username/password or token).
# - "repositories" maps specific image repository names to their credentials, which override registry-level credentials.
# Example:
# {
#     "registries": {
#         "https://registry.hub.docker.com/v2": {
#             "username": "your_dockerhub_username",
#             "password": "your_dockerhub_password_or_token"
#         },
#         "https://ghcr.io/v2": {
#             "token": "your_github_personal_access_token"
#         }
#     },
#     "repositories": {
#         "captnio/captn": {
#             "username": "captnio",
#             "password": "specific_token_for_captn"
#         },
#         "myorg/private-repo": {
#             "token": "specific_token_for_private_repo"
#         }
#     }
# }
# If both "registries" and "repositories" are present, repository credentials take precedence for matching images.
# Default: /app/conf/registry-credentials.json
credentialsFile = /app/conf/registry-credentials.json

[envFiltering]
# Enable environment variable filtering during container recreation
# This feature filters out environment variables that come from the image
# and should not be preserved during container updates
# Possible values: true, false
# Default: true
enabled = true

# Patterns for environment variables that should be excluded from container recreation
# These variables are typically build-time variables or system variables that
# should not be preserved when recreating containers with new images
# Format: JSON array of string patterns (supports wildcards: *, ?, [])
# Examples: "IMMICH_BUILD_*", "NODE_VERSION", "BUILD_*", "GIT_*"
# Default: None
#
# Examples:
# excludePatterns = [
#     "IMMICH_BUILD_*",
#     "NODE_VERSION"
# ]

# Patterns for environment variables that should always be preserved
# These variables are typically configuration variables that should
# always be kept when recreating containers
# Format: JSON array of string patterns (supports wildcards: *, ?, [])
# Examples: "DB_*", "REDIS_*", "TZ", "PASSWORD"
# Default: None
#
# Examples:
# preservePatterns = [
#     "TZ",
#     "PUID",
#     "PGID",
#     "UMASK",
#     "DB_*"
# ]

# Container-specific environment variable filtering rules
# These rules override the global patterns for specific containers
# Format: JSON object with container names as keys
# Container names are matched using case-insensitive substring matching
# Example: "immich" will match "immich-server", "immich-api", etc.
# Default: None
#
# Examples:
# containerSpecificRules = {
#     "immich": {
#         "excludePatterns": [
#             "IMMICH_BUILD_*",
#             "IMMICH_SOURCE_*",
#             "IMMICH_REPOSITORY_*"
#         ],
#         "preservePatterns": [
#             "IMMICH_ENV",
#             "IMMICH_LOG_LEVEL",
#             "IMMICH_MACHINE_LEARNING_URL"
#         ]
#     }
# }

[assignmentsByName]
# Direct rule assignments by container name
# This allows you to assign rules to containers
# Format: container_name = rule_name
#
# Examples:
# MariaDB = conservative
# PostgreSQL = strict
# redis = permissive

[rules]
# Rule definitions for update behavior
# Each rule is a JSON object that defines update policies
# Rules can be referenced by name in container labels or command line

# Default rule - conservative approach
# Only allows patch updates with strict verification
default =       {
                    "minImageAge": "3h",
                    "progressiveUpgrade": false,
                    "allow": {
                        "major": false,
                        "minor": false,
                        "patch": false,
                        "build": false,
                        "digest": false,
                        "scheme_change": false
                    }
                }

# Relaxed rule - allows more updates with progressive upgrade
# Allows major, minor, and patch updates with conditions
relaxed =       {
                    "minImageAge": "3h",
                    "progressiveUpgrade": true,
                    "allow": {
                        "major": true,
                        "minor": true,
                        "patch": true,
                        "build": true,
                        "digest": true,
                        "scheme_change": false
                    },
                    "conditions": {
                        "major": {
                            "require": ["minor", "patch", "build"]
                        }
                    }
                }

# Permissive rule - allows all update types
# Most permissive rule, use with caution
permissive =    {
                    "minImageAge": "3h",
                    "progressiveUpgrade": true,
                    "allow": {
                        "major": true,
                        "minor": true,
                        "patch": true,
                        "build": true,
                        "digest": true,
                        "scheme_change": false
                    }
                }

# Strict rule - very conservative
# Only allows updates when explicitly configured
strict =        {
                    "minImageAge": "3h",
                    "progressiveUpgrade": false,
                    "allow": {
                        "major": false,
                        "minor": false,
                        "patch": false,
                        "build": false,
                        "digest": false,
                        "scheme_change": false
                    }
                }

# Patch-only rule - only patch updates
# Good for production environments
patch_only =    {
                    "minImageAge": "3h",
                    "progressiveUpgrade": true,
                    "allow": {
                        "major": false,
                        "minor": false,
                        "patch": true,
                        "build": false,
                        "digest": false,
                        "scheme_change": false
                    }
                }

# Security-only rule - patch and digest updates
# Focuses on security updates only
security_only = {
                    "minImageAge": "3h",
                    "progressiveUpgrade": true,
                    "allow": {
                        "major": false,
                        "minor": false,
                        "patch": true,
                        "build": false,
                        "digest": true,
                        "scheme_change": false
                    }
                }

# Digest-only rule - only digest updates
# Focuses on updates that change the image digest only
digest_only =  {
                    "minImageAge": "24h",
                    "progressiveUpgrade": true,
                    "allow": {
                        "major": false,
                        "minor": false,
                        "patch": false,
                        "build": false,
                        "digest": true,
                        "scheme_change": false
                    }
                }

# CI/CD rule - minor, patch, and build updates
# Good for development and CI/CD environments
ci_cd =         {
                    "minImageAge": "3h",
                    "progressiveUpgrade": true,
                    "allow": {
                        "major": false,
                        "minor": true,
                        "patch": true,
                        "build": true,
                        "digest": false,
                        "scheme_change": false
                    },
                    "conditions": {
                        "minor": {
                            "require": ["patch"]
                        }
                    }
                }

# Conservative rule - patch and build updates with lag
# Conservative approach with longer image age requirement
conservative =  {
                    "minImageAge": "24h",
                    "progressiveUpgrade": true,
                    "allow": {
                        "major": false,
                        "minor": false,
                        "patch": true,
                        "build": true,
                        "digest": false,
                        "scheme_change": false
                    },
                    "lagPolicy": {
                        "major": 1
                    }
                }
"""

    try:
        # Ensure the directory exists
        os.makedirs(os.path.dirname(example_path), exist_ok=True)

        # Write the example config file
        with open(example_path, 'w', encoding='utf-8') as f:
            f.write(example_content)

        logging.info(f"Example config file created/updated: {example_path}")
        return True
    except Exception as e:
        logging.error(f"Failed to create/update example config file: {e}")
        return False


# Global instance
config = Config()
