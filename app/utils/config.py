import configparser
import os

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
        env_key = f"{self._section}_{key}"
        value = (
            self._values.get(key)
            or os.getenv(env_key)
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

    def __getattr__(self, section):
        if section not in self._namespaces:
            raise AttributeError(f"Config section '{section}' not found")
        return self._namespaces[section]


# Global instance
config = Config()
