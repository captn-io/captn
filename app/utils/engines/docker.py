#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import fnmatch
import json
import logging
import os
import time
from datetime import datetime

import docker
from docker import errors as docker_errors
from docker.types import Mount

from ..common import get_container_backup_name, parse_duration
from ..config import config
from ..scripts import execute_post_script, should_rollback_on_post_failure

logging = logging.getLogger(__name__)


def filter_environment_variables(container_inspect_data, image_inspect_data, container_name=None):
    """
    Filter environment variables to only include those that were explicitly set
    when the container was started, excluding those that come from the image.

    This function compares environment variables between the container and its
    base image to identify only those variables that were explicitly set when
    the container was created, filtering out inherited variables from the image.

    Parameters:
        container_inspect_data (dict): Container inspect data
        image_inspect_data (dict): Image inspect data
        container_name (str, optional): Container name for logging

    Returns:
        list: Filtered environment variables that should be preserved
    """
    logging.debug(f"Filtering environment variables", extra={"indent": 4})
    container_env = container_inspect_data.get("Config", {}).get("Env", [])
    image_env = image_inspect_data.get("Config", {}).get("Env", [])

    if not container_env:
        return []

    if not image_env:
        return container_env

    # Convert lists to dictionaries for easier comparison
    container_env_dict = {}
    for env_var in container_env:
        if '=' in env_var:
            key, value = env_var.split('=', 1)
            container_env_dict[key] = value

    image_env_dict = {}
    for env_var in image_env:
        if '=' in env_var:
            key, value = env_var.split('=', 1)
            image_env_dict[key] = value

    # Get environment variables that are unique to the container
    unique_env_vars = []
    for key, value in container_env_dict.items():
        # Skip if this variable exists in the image with the same value
        if key in image_env_dict and image_env_dict[key] == value:
            logging.debug(f"Skipping ENV '{key}' (inherited from image)", extra={"indent": 6})
            continue

        # Apply additional filtering rules
        if should_preserve_env_variable(key, value, container_name):
            unique_env_vars.append(f"{key}={value}")
            logging.debug(f"Preserving ENV '{key}'", extra={"indent": 6})
        else:
            logging.debug(f"Filtering out ENV '{key}' (matches filter rule)", extra={"indent": 6})

    return unique_env_vars


def should_preserve_env_variable(key, value, container_name=None):
    """
    Determine if an environment variable should be preserved based on filtering rules.

    This function applies environment variable filtering rules to determine
    whether a specific environment variable should be preserved during container
    recreation. It checks against exclude and preserve patterns from configuration.

    Parameters:
        key (str): Environment variable name
        value (str): Environment variable value
        container_name (str, optional): Container name for context-specific rules

    Returns:
        bool: True if the variable should be preserved, False otherwise
    """
    # Get filtering rules from configuration
    env_filter_rules = get_env_filter_rules(container_name)

    # Check against filter patterns
    for pattern in env_filter_rules.get('exclude_patterns', []):
        if fnmatch.fnmatch(key, pattern):
            return False

    # Check against preserve patterns (these override exclude patterns)
    for pattern in env_filter_rules.get('preserve_patterns', []):
        if fnmatch.fnmatch(key, pattern):
            return True

    # Default: preserve if not explicitly excluded
    return True


def get_env_filter_rules(container_name=None):
    """
    Get environment variable filtering rules from configuration.

    This function retrieves environment variable filtering rules from the
    configuration, including global rules and container-specific overrides.

    Parameters:
        container_name (str, optional): Container name for specific rules

    Returns:
        dict: Filtering rules including exclude_patterns and preserve_patterns
    """
    # Check if ENV filtering is enabled
    if not getattr(config.envFiltering, 'enabled', True):
        return {'exclude_patterns': [], 'preserve_patterns': []}

    # Get rules from configuration
    rules = {
        'exclude_patterns': [],
        'preserve_patterns': []
    }

    # Load exclude patterns from config
    if hasattr(config.envFiltering, 'excludePatterns'):
        try:
            exclude_patterns = json.loads(config.envFiltering.excludePatterns)
            if isinstance(exclude_patterns, list):
                rules['exclude_patterns'] = exclude_patterns
        except (json.JSONDecodeError, AttributeError):
            logging.warning("Invalid excludePatterns in config, using defaults", extra={"indent": 4})

    # Load preserve patterns from config
    if hasattr(config.envFiltering, 'preservePatterns'):
        try:
            preserve_patterns = json.loads(config.envFiltering.preservePatterns)
            if isinstance(preserve_patterns, list):
                rules['preserve_patterns'] = preserve_patterns
        except (json.JSONDecodeError, AttributeError):
            logging.warning("Invalid preservePatterns in config, using defaults", extra={"indent": 4})

    # Container-specific rules (if configured)
    if container_name:
        container_rules = get_container_specific_env_rules(container_name)
        if container_rules:
            rules['exclude_patterns'].extend(container_rules.get('exclude_patterns', []))
            rules['preserve_patterns'].extend(container_rules.get('preserve_patterns', []))

    return rules


def get_container_specific_env_rules(container_name):
    """
    Get container-specific environment variable filtering rules.

    This function retrieves container-specific environment variable filtering
    rules from the configuration. It supports case-insensitive substring
    matching for container names.

    Parameters:
        container_name (str): Container name

    Returns:
        dict: Container-specific rules or empty dict if no rules found
    """
    # Load container-specific rules from config
    if hasattr(config.envFiltering, 'containerSpecificRules'):
        try:
            container_rules = json.loads(config.envFiltering.containerSpecificRules)
            if isinstance(container_rules, dict):
                # Find matching container rule (case-insensitive substring matching)
                for rule_name, rule_data in container_rules.items():
                    if rule_name.lower() in container_name.lower():
                        if isinstance(rule_data, dict):
                            return {
                                'exclude_patterns': rule_data.get('excludePatterns', []),
                                'preserve_patterns': rule_data.get('preservePatterns', [])
                            }
        except (json.JSONDecodeError, AttributeError):
            logging.warning("Invalid containerSpecificRules in config", extra={"indent": 4})

    return {}


def get_client():
    """
    Returns a Docker client instance.

    This function initializes and returns a Docker client instance, performing
    necessary checks for Docker socket availability and permissions. It provides
    detailed error messages and troubleshooting guidance if the connection fails.

    Returns:
        Docker client instance or None if connection fails
    """
    # Check if Docker socket is available
    docker_socket_path = "/var/run/docker.sock"
    if not os.path.exists(docker_socket_path):
        logging.error(f"Docker socket not found at {docker_socket_path}")
        logging.error("To fix this issue:")
        logging.error("1. Ensure Docker daemon is running")
        logging.error("2. Mount the Docker socket when running the container:")
        logging.error("   docker run -v /var/run/docker.sock:/var/run/docker.sock captnio/captn:latest")
        logging.error("3. Or run captn on the host system directly")
        return None

    # Check if we have read/write access to the Docker socket
    if not os.access(docker_socket_path, os.R_OK | os.W_OK):
        logging.error(f"No read/write access to Docker socket at {docker_socket_path}")
        logging.error("To fix this issue:")
        logging.error("1. Run the container with proper permissions")
        logging.error("2. Or add your user to the docker group on the host")
        logging.error("3. Or run captn with sudo/root privileges")
        return None

    try:
        return docker.from_env()
    except docker_errors.DockerException as e:
        logging.error(f"Failed to connect to Docker daemon: {e}")
        logging.error("To fix this issue:")
        logging.error("1. Ensure Docker daemon is running")
        logging.error("2. Check Docker daemon logs: sudo journalctl -u docker")
        logging.error("3. Verify Docker socket permissions")
        return None


def get_containers(filters, client):
    """
    Get containers based on specified filters.

    This function retrieves Docker containers and applies filtering based on
    container names and status. It supports wildcard pattern matching for
    container names and various status filters.

    Parameters:
        filters: List of filter strings in format "key=value"
        client: Docker client instance

    Returns:
        list: List of containers matching the filters
    """
    logging.debug("Retrieving container list", extra={"indent": 0})

    try:
        name_filters = []
        filter_status = None

        # Parse --filter arguments
        if filters:
            for f in filters:
                if "=" not in f:
                    logging.warning(f"Ignoring malformed filter: {f}", extra={"indent": 2})
                    continue
                key, value = f.split("=", 1)

                if key == "status":
                    filter_status = value  # we'll handle 'all' case later
                elif key == "name":
                    name_filters.append(value)
                else:
                    logging.warning(f"Unsupported filter key: {key}", extra={"indent": 2})

        list_kwargs = {}

        # Set 'all=True' if status=all, else rely on Docker default (running only)
        if filter_status == "all":
            list_kwargs["all"] = True
        elif filter_status:
            list_kwargs["filters"] = {"status": filter_status}

        # Get full list and filter manually by name
        containers = client.containers.list(**list_kwargs)
        logging.debug(f"Found Containers before name filtering: {len(containers)}", extra={"indent": 2})

        if name_filters:

            def name_matches(cname):
                return any(
                    (fnmatch.fnmatch(cname, nf) if any(x in nf for x in ["*", "?"]) else cname == nf)
                    for nf in name_filters
                )

            containers = [c for c in containers if name_matches(c.name)]
            logging.debug(f"Containers after name filtering: {len(containers)}", extra={"indent": 2})

    except docker_errors.DockerException as e:
        logging.error(f"Docker error: {str(e)}", extra={"indent": 2})
        containers = []

    return containers


def get_local_image_metadata(image, container_inspect_data):
    """
    Extracts registry, repository, tag/digest and full reference from a Docker image object.

    This function analyzes a Docker image object to extract metadata including
    registry information, image name, tags, and digests. It handles various
    image reference formats and provides fallback mechanisms for edge cases.

    Parameters:
        image: Docker image object
        container_inspect_data: Container inspection data

    Returns:
        dict: Dictionary containing registry, name, tag, digest, reference, and API URLs
    """
    repo_tag = image.attrs.get("RepoTags", [])
    repo_digest = image.attrs.get("RepoDigests", [])
    image_id = image.attrs.get("Id")
    container_image_ref = container_inspect_data.get("Config", {}).get("Image")

    if "@" in container_image_ref:
        name, digest = container_image_ref.split("@", 1)
        tag = None
    elif ":" in container_image_ref:
        name, tag = container_image_ref.rsplit(":", 1)
        digest = None
    else:
        name = container_image_ref
        tag = None
        digest = None

    # Determine reference (prefer tagged name, fall back to digest, then to container input)
    if repo_tag:
        reference = repo_tag[0]
        tag_or_digest = reference.split(":")[-1]
    elif repo_digest:
        reference = repo_digest[0]
        tag_or_digest = reference.split("@")[-1]
    elif container_image_ref:
        # fallback for images that are only defined by digest in the container
        reference = container_image_ref
        if "@" in container_image_ref:
            tag_or_digest = container_image_ref.split("@")[-1]
        elif ":" in container_image_ref:
            tag_or_digest = container_image_ref.split(":")[-1]
        else:
            tag_or_digest = None
    else:
        reference = image_id
        tag_or_digest = None

    # Extract registry and name from known reference (tag or digest)
    if "@" in reference:
        path = reference.split("@")[0]
    elif ":" in reference:
        path = reference.rsplit(":", 1)[0]
    else:
        path = reference

    # Protect against image IDs like "sha256:..."
    if path.startswith("sha256"):
        # Attempt to fallback to container_image_ref instead
        fallback_ref = container_image_ref.split("@")[0].split(":")[0]
        path = fallback_ref if "/" in fallback_ref else f"library/{fallback_ref}"

    parts = path.split("/")

    if len(parts) == 1:
        # e.g. 'nginx'
        registry = "docker.io"
        name = f"library/{parts[0]}"
        apiUrl = config.docker.apiUrl
        imageUrl = f"{apiUrl}/repositories/{name}"
        imageTagsUrl = f"{apiUrl}/repositories/{name}/tags"
    elif "." not in parts[0] and ":" not in parts[0]:
        # e.g. 'library/nginx'
        registry = "docker.io"
        name = path
        apiUrl = config.docker.apiUrl
        imageUrl = f"{apiUrl}/repositories/{name}"
        imageTagsUrl = f"{apiUrl}/repositories/{name}/tags"
    else:
        # e.g. 'ghcr.io/immich-app/immich-server'
        registry = parts[0]
        name = "/".join(parts[1:])
        apiUrl = config.ghcr.apiUrl
        imageUrl = f"{apiUrl}/{name}"
        imageTagsUrl = f"{apiUrl}/{name}/tags/list"

    return {
        "apiUrl": apiUrl,
        "imageUrl": imageUrl,
        "imageTagsUrl": imageTagsUrl,
        "id": image_id,
        "name": name,
        "reference": reference,
        "registry": registry,
        "tag_or_digest": tag_or_digest,
        "tag": tag,
        "digest": digest,
    }


def pull_image(client, image_reference, dry_run):
    """
    Pulls a Docker image using the given reference with authentication support.

    This function pulls a Docker image from a registry with support for
    authentication. It handles different registry types (Docker Hub, GHCR, etc.)
    and applies appropriate authentication methods for each.

    Parameters:
        client (docker.DockerClient): Docker client instance.
        image_reference (str): Image to pull (e.g. 'ghcr.io/org/app:1.2.3').
        dry_run (bool): If True, does not perform the actual pull.

    Returns:
        Image object if successful, None otherwise.
    """

    try:
        # Extract registry and repository for authentication
        registry = "docker.io"  # Default registry
        repository_name = None

        if "/" in image_reference:
            parts = image_reference.split("/")
            if "." in parts[0] or parts[0] in ["ghcr.io", "quay.io", "registry.gitlab.com"]:
                # Custom registry (e.g., ghcr.io/org/app:tag)
                registry = parts[0]
                repository_name = "/".join(parts[1:]).split(":")[0] if ":" in "/".join(parts[1:]) else "/".join(parts[1:])
            else:
                # Docker Hub (e.g., org/app:tag)
                repository_name = "/".join(parts).split(":")[0] if ":" in "/".join(parts) else "/".join(parts)
        else:
            # Single name (e.g., nginx:tag)
            repository_name = image_reference.split(":")[0] if ":" in image_reference else image_reference

        # Get credentials for this registry and repository
        from ..registries.auth import get_credentials
        creds = get_credentials(f"https://{registry}/v2", repository_name)

        if creds and not dry_run:
            # Handle different authentication methods based on registry type
            if registry in ["ghcr.io"]:
                # GHCR uses token-based authentication
                token = creds.get("token")
                if token:
                    try:
                        # For GHCR, we need to use the token as both username and password
                        client.login(username="oauth2accesstoken", password=token, registry=registry)
                        logging.debug(f"Successfully logged in to GHCR registry: {registry}", extra={"indent": 6})
                    except docker_errors.APIError as e:
                        logging.warning(f"Failed to login to GHCR registry {registry}: {e}", extra={"indent": 6})
                        # Continue with pull attempt even if login fails
                    except Exception as e:
                        logging.warning(f"Unexpected error during GHCR login to registry {registry}: {e}", extra={"indent": 6})
                        # Continue with pull attempt even if login fails
                else:
                    logging.debug(f"No token found for GHCR registry {registry}", extra={"indent": 6})
            else:
                # Docker Hub and other registries use username/password authentication
                username = creds.get("username")
                password = creds.get("password") or creds.get("token")

                if username and password:
                    try:
                        # Perform Docker login for this registry
                        client.login(username=username, password=password, registry=registry)
                        logging.debug(f"Successfully logged in to registry: {registry}", extra={"indent": 6})
                    except docker_errors.APIError as e:
                        logging.warning(f"Failed to login to registry {registry}: {e}", extra={"indent": 6})
                        # Continue with pull attempt even if login fails
                    except Exception as e:
                        logging.warning(f"Unexpected error during login to registry {registry}: {e}", extra={"indent": 6})
                        # Continue with pull attempt even if login fails
                else:
                    logging.debug(f"Incomplete credentials for registry {registry} - missing username or password", extra={"indent": 6})
        elif not creds:
            logging.debug(f"No credentials found for registry {registry}, attempting anonymous pull", extra={"indent": 6})

        logging.info(f"{'Would pull' if dry_run else 'Pulling'} image '{image_reference}'", extra={"indent": 4})
        image = client.images.pull(image_reference) if not dry_run else None
        if not dry_run and image:
            logging.debug(f"Successfully pulled image '{image.short_id}'", extra={"indent": 6})
        return image
    except docker_errors.APIError as e:
        logging.error(f"Failed to pull image '{image_reference}': {str(e)}", extra={"indent": 6})
        return None


def get_container_spec(client, container_inspect_data, container_name, image, image_inspect_data=None):
    """
    Generates a complete container configuration from an inspect payload.

    This function creates a complete container specification that can be used
    to recreate a container with the same configuration but a new image.
    It handles mounts, environment variables, networking, and host configuration.

    Parameters:
        client: Docker client instance
        container_inspect_data (dict): Output of docker inspect on the container
        container_name (str): Name to assign to the new container
        image (str): New image reference to use
        image_inspect_data (dict, optional): Image inspect data for ENV filtering

    Returns:
        dict: Ready-to-use arguments for client.api.create_container()
    """
    config = container_inspect_data["Config"]
    host_config = container_inspect_data["HostConfig"]
    # networking = container_inspect_data.get("NetworkSettings", {})
    mounts_raw = container_inspect_data.get("Mounts", [])

    mounts = []
    for m in sorted(mounts_raw, key=lambda x: x.get("Destination", "")):
        mount_type = m.get("Type")
        destination = m.get("Destination")
        if mount_type not in {"bind", "volume", "tmpfs"} or not destination:
            continue

        # Skip automatically generated named volumes (hash-like names)
        if mount_type == "volume" and "Name" in m:
            volume_name = m["Name"]
            # Check if volume name looks like an auto-generated hash (64 hex characters)
            if len(volume_name) == 64 and all(c in '0123456789abcdef' for c in volume_name):
                logging.debug(f"Skipping auto-generated volume '{volume_name}' for destination '{destination}'", extra={"indent": 6})
                continue

        kwargs = {
            "target": destination,
            "type": mount_type,
            "read_only": not m.get("RW", True),
        }

        # Handle source differently for named volumes vs bind mounts
        if mount_type == "volume" and "Name" in m:
            # For named volumes, use the volume name as source
            kwargs["source"] = m["Name"]
        elif "Source" in m:
            # For bind mounts, use the source path
            kwargs["source"] = m["Source"]

        if "Propagation" in m and m["Propagation"]:
            kwargs["propagation"] = m["Propagation"]

        mounts.append(Mount(**{k: v for k, v in kwargs.items() if v is not None}))

    host_config_clean = {
        # "binds": host_config.get("Binds"),
        "port_bindings": host_config.get("PortBindings") if host_config.get("NetworkMode") and (host_config.get("NetworkMode") not in ["host", "none"]) else None,
        "publish_all_ports": host_config.get("PublishAllPorts", False),
        "restart_policy": host_config.get("RestartPolicy"),
        "devices": host_config.get("Devices"),
        "cap_add": host_config.get("CapAdd"),
        "cap_drop": host_config.get("CapDrop"),
        "dns": host_config.get("Dns"),
        "log_config": host_config.get("LogConfig"),
        "network_mode": host_config.get("NetworkMode"),
        "privileged": host_config.get("Privileged", False),
        "read_only": host_config.get("ReadonlyRootfs", False),
        "security_opt": host_config.get("SecurityOpt"),
        # "tmpfs": host_config.get("Tmpfs"),  # Removed as tmpfs is handled via Mounts
        "ulimits": host_config.get("Ulimits"),
        "mounts": mounts,
    }

    # networking_config = {}
    # Networking config removed due to missing client context and unused variable.

    # Filter environment variables if image_inspect_data is provided
    container_env = config.get("Env", [])
    if image_inspect_data:
        filtered_env = filter_environment_variables(container_inspect_data, image_inspect_data, container_name)
        logging.debug(f"Environment variables: {len(container_env)} total, {len(filtered_env)} preserved", extra={"indent": 6})
        if filtered_env:
            logging.debug(f"-> Preserved ENVs:\n{json.dumps(filtered_env, indent=4)}", extra={"indent": 6})
    else:
        filtered_env = container_env
        logging.warning("No image_inspect_data provided - preserving all environment variables", extra={"indent": 6})

    spec = {
        "name": container_name,
        "image": image,
        "host_config": client.api.create_host_config(**host_config_clean),
        "networking_config": client.api.create_networking_config(
            {
                k: {
                    "Aliases": v.get("Aliases"),
                    "Links": v.get("Links"),
                    "MacAddress": v.get("MacAddress"),
                    "DriverOpts": v.get("DriverOpts"),
                    "IPAMConfig": v.get("IPAMConfig"),
                }
                for k, v in container_inspect_data.get("NetworkSettings", {}).get("Networks", {}).items()
            }
        ),
    }

    optional_keys = {
        "command": config.get("Cmd"),
        "entrypoint": config.get("Entrypoint"),
        "environment": filtered_env,  # Use filtered environment variables
        "working_dir": config.get("WorkingDir"),
        "hostname": config.get("Hostname"),
        "user": config.get("User"),
        "mac_address": config.get("MacAddress"),
        "stdin_open": config.get("OpenStdin"),
        "tty": config.get("Tty"),
        "labels": config.get("Labels"),
        "volumes": config.get("Volumes"),
        "healthcheck": config.get("Healthcheck"),
        "ports": config.get("ExposedPorts"),
    }

    spec.update({k: v for k, v in optional_keys.items() if v})

    return spec


def verify_container_start(container, dry_run=False):
    """
    Verify that a container starts successfully and remains stable.

    This function monitors a container after it starts to ensure it remains
    healthy and stable. It supports both health checks and fallback stability
    monitoring, with configurable timeouts and verification periods.

    Parameters:
        container: Container object to verify
        dry_run (bool): If True, only log what would be done without actually verifying

    Returns:
        bool: True if container is verified as stable and healthy

    Raises:
        RuntimeError: If container restarts or becomes unhealthy
        TimeoutError: If verification times out
    """
    max_wait = parse_duration(config.updateVerification.maxWait, "s")
    stable_time = parse_duration(config.updateVerification.stableTime, "s")
    check_interval = parse_duration(config.updateVerification.checkInterval, "s")
    grace_period = parse_duration(config.updateVerification.gracePeriod, "s")
    start_time = datetime.now()
    deadline = start_time.timestamp() + max_wait
    last_state = None

    logging.info( f"{'Would verify' if dry_run else 'Verifying'} startup of container '{container.name}'", extra={"indent": 4}, )

    if grace_period > 0:
        logging.debug( f"{'Would wait' if dry_run else 'Waiting'} {grace_period}s before startup verification begins", extra={"indent": 6}, )
        if not dry_run:
            time.sleep(grace_period)

    stable_start = None
    container.reload()
    state = container.attrs.get("State", {})
    health = state.get("Health", {})
    if "Health" in state:
        health_status = health.get("Status")
        logging.debug("Container is supporting health status", extra={"indent": 6})
    else:
        logging.debug("Container does not support health status", extra={"indent": 6})

    while datetime.now().timestamp() < deadline:
        container.reload()
        state = container.attrs.get("State", {})
        status = state.get("Status")
        health = state.get("Health", {})

        # Always check for unexpected restarts or manual restarts, regardless of healthcheck
        if last_state is None:
            last_state = {
                "startedAt": state.get("StartedAt"),
                "restarts": state.get("RestartCount", 0),
            }
            stable_start = datetime.now()
        else:
            if state.get("RestartCount", 0) > last_state["restarts"]:
                logging.debug( f"RestartCount={state.get('RestartCount', 0)}, StartedAt={state.get('StartedAt')}", extra={"indent": 6}, )
                raise RuntimeError(f"Container '{container.name}' restarted during startup verification")
            if state.get("StartedAt") != last_state["startedAt"]:
                logging.debug( f"RestartCount={state.get('RestartCount', 0)}, StartedAt={state.get('StartedAt')}", extra={"indent": 6}, )
                raise RuntimeError(f"Container '{container.name}' was manually restarted")
        logging.debug( f"RestartCount={state.get('RestartCount', 0)}, StartedAt={state.get('StartedAt')}", extra={"indent": 6}, )

        if status not in ("running", "starting"):
            raise RuntimeError(f"Container '{container.name}' is no longer running (status: {status})")

        # Handle healthcheck if present
        if "Health" in state:
            health_status = health.get("Status")
            logging.debug(f"Health status: {health_status}", extra={"indent": 6})

            if health_status == "healthy":
                if stable_start is None:
                    stable_start = datetime.now()
                elif stable_start and (datetime.now() - stable_start).total_seconds() >= stable_time:
                    logging.info( f"Container '{container.name}' has been healthy for {stable_time}s", extra={"indent": 4}, )
                    return True
            else:
                stable_start = None  # Reset if not continuously healthy
            if health_status == "unhealthy":
                raise RuntimeError(f"Container '{container.name}' is unhealthy")
        else:
            # No healthcheck: fallback to monitoring stability
            if stable_start and (datetime.now() - stable_start).total_seconds() >= stable_time:
                logging.info( f"Container '{container.name}' appears stable after {stable_time}s", extra={"indent": 4}, )
                return True

        time.sleep(check_interval)

    raise TimeoutError(f"Startup verification for container '{container.name}' timed out after {max_wait}s")


def create_container_inspect_comparison(original_inspect_data, new_container, container_name, error_message=None):
    """
    Create a before/after comparison of container inspect data for debugging purposes.

    This function creates a JSON file containing the before and after container
    inspection data, useful for debugging container recreation issues and
    understanding configuration differences.

    Parameters:
        original_inspect_data (dict): Original container inspect data
        new_container: New container object (can be None if creation failed)
        container_name (str): Name of the container
        error_message (str, optional): Error message that occurred

    Returns:
        str: Path to the comparison file if created, None otherwise
    """
    try:
        # Use the same logs directory as the main application
        logs_dir = "/app/logs"

        # Fallback to local logs directory if /app/logs is not accessible
        if not os.access(logs_dir, os.W_OK):
            logs_dir = "./logs"

        os.makedirs(logs_dir, exist_ok=True)

        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"container_comparison_{container_name}_{timestamp}.json"
        filepath = os.path.join(logs_dir, filename)

        # Get new container inspect data if available
        new_inspect_data = None
        if new_container:
            try:
                new_container.reload()
                new_inspect_data = new_container.attrs
            except Exception as e:
                new_inspect_data = {"error": f"Failed to inspect new container: {e}"}

        # Create comparison data
        comparison_data = {
            "container_name": container_name,
            "timestamp": datetime.now().isoformat(),
            "error_message": error_message,
            "original_container": {
                "inspect_data": original_inspect_data,
                "summary": {
                    "image": original_inspect_data.get("Config", {}).get("Image"),
                    "env_count": len(original_inspect_data.get("Config", {}).get("Env", [])),
                    "mounts_count": len(original_inspect_data.get("Mounts", [])),
                    "networks": list(original_inspect_data.get("NetworkSettings", {}).get("Networks", {}).keys()),
                    "ports": original_inspect_data.get("Config", {}).get("ExposedPorts"),
                    "restart_policy": original_inspect_data.get("HostConfig", {}).get("RestartPolicy"),
                    "working_dir": original_inspect_data.get("Config", {}).get("WorkingDir"),
                    "user": original_inspect_data.get("Config", {}).get("User"),
                    "command": original_inspect_data.get("Config", {}).get("Cmd"),
                    "entrypoint": original_inspect_data.get("Config", {}).get("Entrypoint"),
                }
            },
            "new_container": {
                "inspect_data": new_inspect_data,
                "summary": {
                    "image": new_inspect_data.get("Config", {}).get("Image") if new_inspect_data else None,
                    "env_count": len(new_inspect_data.get("Config", {}).get("Env", [])) if new_inspect_data else None,
                    "mounts_count": len(new_inspect_data.get("Mounts", [])) if new_inspect_data else None,
                    "networks": list(new_inspect_data.get("NetworkSettings", {}).get("Networks", {}).keys()) if new_inspect_data else None,
                    "ports": new_inspect_data.get("Config", {}).get("ExposedPorts") if new_inspect_data else None,
                    "restart_policy": new_inspect_data.get("HostConfig", {}).get("RestartPolicy") if new_inspect_data else None,
                    "working_dir": new_inspect_data.get("Config", {}).get("WorkingDir") if new_inspect_data else None,
                    "user": new_inspect_data.get("Config", {}).get("User") if new_inspect_data else None,
                    "command": new_inspect_data.get("Config", {}).get("Cmd") if new_inspect_data else None,
                    "entrypoint": new_inspect_data.get("Config", {}).get("Entrypoint") if new_inspect_data else None,
                } if new_inspect_data else None
            }
        }

        # Write comparison to file
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(comparison_data, f, indent=2, ensure_ascii=False)

        logging.error(f"Container inspect comparison saved to {filepath}", extra={"indent": 4})

        # Also log key differences in the main log
        if new_inspect_data and not isinstance(new_inspect_data, dict):
            logging.error("New container inspect data is not available", extra={"indent": 6})
        elif new_inspect_data:
            orig_summary = comparison_data["original_container"]["summary"]
            new_summary = comparison_data["new_container"]["summary"]

            logging.error("Key differences between original and new container:", extra={"indent": 6})

            # Compare key fields
            for field in ["image", "env_count", "mounts_count", "working_dir", "user"]:
                orig_val = orig_summary.get(field)
                new_val = new_summary.get(field)
                if orig_val != new_val:
                    logging.error(f"  {field}: '{orig_val}' -> '{new_val}'", extra={"indent": 8})

            # Compare networks
            orig_networks = set(orig_summary.get("networks", []))
            new_networks = set(new_summary.get("networks", []))
            if orig_networks != new_networks:
                logging.error(f"  networks: {list(orig_networks)} -> {list(new_networks)}", extra={"indent": 8})

        return filepath

    except Exception as e:
        logging.error(f"Failed to create container comparison: {e}", extra={"indent": 4})
        return None


def recreate_container(client, container, image, container_inspect_data, dry_run, image_inspect_data=None, notification_manager=None):
    """
    Recreate a container with a new image.

    This function performs a complete container recreation process:
    1. Creates a backup of the original container
    2. Stops the original container
    3. Creates a new container with the same configuration but new image
    4. Starts the new container and verifies it's healthy
    5. Removes the backup if successful, or rolls back if failed

    Parameters:
        client: Docker client instance
        container: Original container object
        image: New image reference
        container_inspect_data: Original container inspection data
        dry_run (bool): If True, only log what would be done without actually recreating
        image_inspect_data: Image inspection data for environment filtering (optional)

    Returns:
        Container object if successful, None otherwise
    """
    original_name = container.name
    backup_name = get_container_backup_name(original_name)
    new_container = None

    def rollback():
        try:
            logging.info(f"{'Would roll' if dry_run else 'Rolling'} back", extra={"indent": 4})
            if new_container:
                try:
                    new_container.reload() if not dry_run else None
                    if new_container.attrs.get("State", {}).get("Status") != "stopped":
                        logging.info( f"{'Would stop' if dry_run else 'Stopping'} new container '{new_container.id}'", extra={"indent": 6}, )
                        new_container.stop(timeout=10) if not dry_run else None

                    logging.info( f"{'Would remove' if dry_run else 'Removing'} new container '{new_container.id}'", extra={"indent": 6}, )
                    new_container.remove() if not dry_run else None
                except docker_errors.NotFound:
                    logging.warning( f"New container '{new_container.id}' does not exist anymore - skipping removal", extra={"indent": 6}, )
                except Exception as e:
                    logging.error( f"Failed to clean up new container '{new_container.id}': {e}", extra={"indent": 6}, )

            if container.name != original_name:
                logging.info( f"{'Would rename' if dry_run else 'Renaming'} original container '{container.id}' back to '{original_name}'", extra={"indent": 6}, )
                container.rename(original_name) if not dry_run else None
                container.reload() if not dry_run else None

            # Restore original restart policy if it was changed
            if hasattr(rollback, 'original_restart_policy') and rollback.original_restart_policy:
                try:
                    restart_policy_name = rollback.original_restart_policy.get("Name", "no")
                    logging.debug( f"{'Would restore' if dry_run else 'Restoring'} original restart policy '{restart_policy_name}' for container '{container.id}'", extra={"indent": 6}, )
                    if not dry_run:
                        container.update(restart_policy=rollback.original_restart_policy)
                        container.reload()
                except Exception as e:
                    logging.error( f"Failed to restore restart policy for container '{container.id}': {e}", extra={"indent": 6}, )

            container.reload() if not dry_run else None
            if container.attrs.get("State", {}).get("Status") != "running":
                logging.info(
                    f"{'Would start' if dry_run else 'Starting'} original container '{container.id}'",
                    extra={"indent": 6},
                )
                container.start() if not dry_run else None

            logging.info("Rollback successful", extra={"indent": 6})
        except Exception as re:
            logging.critical(f"Rollback failed for '{container.id}': {re}", extra={"indent": 8})
            return None

        return None

    try:
        # Store original restart policy before modifying it
        original_restart_policy_config = container.attrs.get("HostConfig", {}).get("RestartPolicy", {})
        original_restart_policy_name = original_restart_policy_config.get("Name", "no")
        rollback.original_restart_policy = original_restart_policy_config

        logging.info( f"{'Would rename' if dry_run else 'Renaming'} original container '{container.id}' to '{backup_name}'", extra={"indent": 4}, )
        container.rename(backup_name) if not dry_run else None
        container.reload() if not dry_run else None

        # Disable restart policy in backup container to prevent unwanted restarts
        if original_restart_policy_name != "no":
            logging.debug( f"{'Would disable' if dry_run else 'Disabling'} restart policy '{original_restart_policy_name}' in backup container '{container.id}'", extra={"indent": 4}, )
            if not dry_run:
                container.update(restart_policy={"Name": "no"})
                container.reload()

        logging.info( f"{'Would stop' if dry_run else 'Stopping'} original container '{container.id}'", extra={"indent": 4}, )
        container.stop() if not dry_run else None
    except Exception as e:
        error_msg = f"Failed to prepare container '{container.id}' for recreation (rename/stop): {e}"
        logging.error(error_msg, extra={"indent": 6})

        # Create comparison file for debugging (only original container data available)
        if not dry_run:
            create_container_inspect_comparison(
                original_inspect_data=container_inspect_data,
                new_container=None,
                container_name=original_name,
                error_message=error_msg
            )

        rollback() if not dry_run else None
        return None

    try:
        spec = get_container_spec(client, container_inspect_data, original_name, image, image_inspect_data)
        response = client.api.create_container(**spec) if not dry_run else None
        new_container = client.containers.get(response.get("Id")) if not dry_run and response else container

        logging.debug( f"{'Would start' if dry_run else 'Starting'} new container{f' {new_container.id} ' if not dry_run else ''}with image '{image}'", extra={"indent": 4}, )
        new_container.start() if not dry_run else None
        verify_container_start(container=new_container, dry_run=dry_run)

        logging.info( f"{'Would have recreated' if dry_run else 'Recreated'} new container '{new_container.id}' with image '{image}'", extra={"indent": 4}, )

        # Execute post-script after successful container recreation
        post_success, post_output = execute_post_script(original_name, dry_run)
        if not post_success:
            error_msg = f"Post-script failed for container '{original_name}'"
            logging.error(error_msg, extra={"indent": 4})

            # Add error to notification manager if available
            if notification_manager:
                notification_manager.add_error(error_msg)

            if should_rollback_on_post_failure():
                rollback()
                return None

        return new_container if not dry_run else container

    except Exception as e:
        error_msg = f"Failed to recreate new container: {e}"
        logging.error(error_msg, extra={"indent": 4})

        # Add error to notification manager if available
        if notification_manager:
            notification_manager.add_error(error_msg)

        # Create comparison file for debugging
        if not dry_run:
            create_container_inspect_comparison(
                original_inspect_data=container_inspect_data,
                new_container=new_container,
                container_name=original_name,
                error_message=error_msg
            )

        rollback() if not dry_run else None
        return None


def is_self_container(container_name, container_id):
    """
    Check if the given container is the captn application itself.

    This function determines if the specified container is the captn application
    container itself by checking various container identifiers against the current
    running environment. It uses multiple methods to identify the current container.

    Parameters:
        container_name (str): Name of the container to check
        container_id (str): ID of the container to check

    Returns:
        bool: True if this is the self container, False otherwise
    """

    logging.debug("Checking if the given container is the captn application itself", extra={"indent": 6})
    logging.debug(f"func_params:\n{json.dumps({k: v for k, v in locals().items()}, indent=4)}", extra={"indent": 8})

    # Check if we're running inside a container
    if not os.path.exists("/.dockerenv"):
        return False

    # Try multiple sources to identify the current container
    possible_identifiers = []

    # 1. HOSTNAME environment variable
    hostname = os.environ.get("HOSTNAME")
    if hostname:
        possible_identifiers.append(hostname.lstrip("/"))

    # 2. System hostname
    try:
        system_hostname = os.uname().nodename
        if system_hostname and system_hostname not in possible_identifiers:
            possible_identifiers.append(system_hostname.lstrip("/"))
    except Exception as e:
        logging.debug(f"Could not get system hostname: {e}", extra={"indent": 8})

    # 3. Container ID from /proc/self/cgroup (more reliable)
    try:
        with open("/proc/self/cgroup", "r") as f:
            for line in f:
                if "docker" in line or "containerd" in line:
                    # Extract container ID from cgroup path
                    # Format: 0::/system.slice/docker-<container_id>.scope
                    parts = line.strip().split("/")
                    for part in parts:
                        if part.startswith("docker-") and part.endswith(".scope"):
                            container_id = part[7:-6]  # Remove 'docker-' prefix and '.scope' suffix
                            possible_identifiers.append(container_id)
                            break
                        elif len(part) == 64 and all(c in "0123456789abcdef" for c in part):
                            # Full container ID (64 hex chars)
                            possible_identifiers.append(part)
                            break
    except Exception as e:
        logging.debug(f"Could not read /proc/self/cgroup: {e}", extra={"indent": 8})

    # 4. Container ID from /proc/1/cgroup (alternative method)
    try:
        with open("/proc/1/cgroup", "r") as f:
            for line in f:
                if "docker" in line or "containerd" in line:
                    parts = line.strip().split("/")
                    for part in parts:
                        if part.startswith("docker-") and part.endswith(".scope"):
                            container_id = part[7:-6]
                            possible_identifiers.append(container_id)
                            break
                        elif len(part) == 64 and all(c in "0123456789abcdef" for c in part):
                            possible_identifiers.append(part)
                            break
    except Exception as e:
        logging.debug(f"Could not read /proc/1/cgroup: {e}", extra={"indent": 8})

    logging.debug(f"Possible container identifiers: {possible_identifiers}", extra={"indent": 8})

    # Check if any of our identifiers match the container name
    for identifier in possible_identifiers:
        if container_name == identifier:
            logging.debug(f"Self container detected: {container_name} matches {identifier}", extra={"indent": 8})
            return True

    # Check if any of our identifiers match the container ID
    if container_id:
        for identifier in possible_identifiers:
            if container_id == identifier:
                logging.debug(f"Self container detected: {container_id} matches {identifier}", extra={"indent": 8})
                return True

    # Also check if the container name is a substring of any identifier (for cases where the container name is part of a longer identifier)
    for identifier in possible_identifiers:
        if container_name in identifier or identifier in container_name:
            logging.debug(f"Self container detected: partial match between {container_name} and {identifier}", extra={"indent": 8})
            return True

    # Check if container id starts with any of the identifiers
    if container_id:
        for identifier in possible_identifiers:
            if container_id.startswith(identifier):
                logging.debug(f"Self container detected: {container_id} starts with {identifier}", extra={"indent": 8})
                return True

    logging.debug("Self container not detected", extra={"indent": 8})
    return False
