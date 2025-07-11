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

logging = logging.getLogger(__name__)


def get_client():
    """
    Returns a Docker client instance.
    This function is used to ensure that the Docker client is initialized only once.
    Will be used in the future to allow alternative container environments (e.g., Podman, container, etc.).
    """
    return docker.from_env()


def get_containers(filters, client):
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
    Returns a dictionary with registry, name, tag, digest and reference.
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
    Pulls a Docker image using the given reference.

    Parameters:
        client (docker.DockerClient): Docker client instance.
        image_reference (str): Image to pull (e.g. 'ghcr.io/org/app:1.2.3').
        dry_run (bool): If True, does not perform the actual pull.

    Returns:
        Image object if successful, None otherwise.
    """

    log_action = "Would pull" if dry_run else "Pulling"

    try:
        logging.info(f"{log_action} image '{image_reference}'", extra={"indent": 4})
        image = client.images.pull(image_reference) if not dry_run else None
        if not dry_run and image:
            logging.debug(f"Successfully pulled image '{image.short_id}'", extra={"indent": 6})
        return image
    except docker_errors.APIError as e:
        logging.error(f"Failed to pull image '{image_reference}': {str(e)}", extra={"indent": 6})
        return None


def get_container_spec(client, container_inspect_data, container_name, image):
    """
    Generates a complete container configuration from an inspect payload.
    Can be directly used with Docker SDK's create_container() call.

    Parameters:
        container_inspect_data (dict): Output of docker inspect on the container
        container_name (str): Name to assign to the new container
        image (str): New image reference to use

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

        kwargs = {
            "target": destination,
            "type": mount_type,
            "read_only": not m.get("RW", True),
        }

        if "Source" in m:
            kwargs["source"] = m["Source"]

        if "Propagation" in m and m["Propagation"]:
            kwargs["propagation"] = m["Propagation"]

        mounts.append(Mount(**{k: v for k, v in kwargs.items() if v is not None}))

    host_config_clean = {
        "binds": host_config.get("Binds"),
        "port_bindings": host_config.get("PortBindings"),
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
        "environment": config.get("Env"),
        "working_dir": config.get("WorkingDir"),
        "hostname": config.get("Hostname"),
        "user": config.get("User"),
        "mac_address": config.get("MacAddress"),
        "stdin_open": config.get("OpenStdin"),
        "tty": config.get("Tty"),
        "labels": config.get("Labels"),
        "volumes": config.get("Volumes"),
        "healthcheck": config.get("Healthcheck"),
    }

    spec.update({k: v for k, v in optional_keys.items() if v})

    return spec


def verify_container_start(container, dry_run=False):
    max_wait = parse_duration(config.updateVerification.maxWait, "s")
    stable_time = parse_duration(config.updateVerification.stableTime, "s")
    check_interval = parse_duration(config.updateVerification.checkInterval, "s")
    grace_period = parse_duration(config.updateVerification.gracePeriod, "s")
    start_time = datetime.now()
    deadline = start_time.timestamp() + max_wait
    last_state = None

    logging.info(
        f"{'Would verify' if dry_run else 'Verifying'} startup of container '{container.name}'",
        extra={"indent": 4},
    )

    if grace_period > 0:
        logging.debug(
            f"{'Would wait' if dry_run else 'Waiting'} {grace_period}s before startup verification begins",
            extra={"indent": 6},
        )
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
                logging.debug(
                    f"RestartCount={state.get('RestartCount', 0)}, StartedAt={state.get('StartedAt')}",
                    extra={"indent": 6},
                )
                raise RuntimeError(f"Container '{container.name}' restarted during startup verification")
            if state.get("StartedAt") != last_state["startedAt"]:
                logging.debug(
                    f"RestartCount={state.get('RestartCount', 0)}, StartedAt={state.get('StartedAt')}",
                    extra={"indent": 6},
                )
                raise RuntimeError(f"Container '{container.name}' was manually restarted")
        logging.debug(
            f"RestartCount={state.get('RestartCount', 0)}, StartedAt={state.get('StartedAt')}",
            extra={"indent": 6},
        )

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
                    logging.info(
                        f"Container '{container.name}' has been healthy for {stable_time}s",
                        extra={"indent": 4},
                    )
                    return True
            else:
                stable_start = None  # Reset if not continuously healthy
            if health_status == "unhealthy":
                raise RuntimeError(f"Container '{container.name}' is unhealthy")
        else:
            # No healthcheck: fallback to monitoring stability
            if stable_start and (datetime.now() - stable_start).total_seconds() >= stable_time:
                logging.info(
                    f"Container '{container.name}' appears stable after {stable_time}s",
                    extra={"indent": 4},
                )
                return True

        time.sleep(check_interval)

    raise TimeoutError(f"Startup verification for container '{container.name}' timed out after {max_wait}s")


def recreate_container(client, container, image, container_inspect_data, dry_run):
    original_name = container.name
    backup_name = get_container_backup_name(original_name)
    new_container = None

    def _rollback():
        try:
            logging.info(f"{'Would roll' if dry_run else 'Rolling'} back", extra={"indent": 4})
            if new_container:
                try:
                    new_container.reload() if not dry_run else None
                    if new_container.attrs.get("State", {}).get("Status") != "stopped":
                        logging.info(
                            f"{'Would stop' if dry_run else 'Stopping'} new container '{new_container.id}'",
                            extra={"indent": 6},
                        )
                        new_container.stop(timeout=10) if not dry_run else None

                    logging.info(
                        f"{'Would remove' if dry_run else 'Removing'} new container '{new_container.id}'",
                        extra={"indent": 6},
                    )
                    new_container.remove() if not dry_run else None
                except docker_errors.NotFound:
                    logging.warning(
                        f"New container '{new_container.id}' does not exist anymore - skipping removal",
                        extra={"indent": 6},
                    )
                except Exception as e:
                    logging.error(
                        f"Failed to clean up new container '{new_container.id}': {e}",
                        extra={"indent": 6},
                    )

            if container.name != original_name:
                logging.info(
                    f"{'Would rename' if dry_run else 'Renaming'} original container '{container.id}' back to '{original_name}'",
                    extra={"indent": 6},
                )
                container.rename(original_name) if not dry_run else None
                container.reload() if not dry_run else None

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
        logging.info(
            f"{'Would rename' if dry_run else 'Renaming'} original container '{container.id}' to '{backup_name}'",
            extra={"indent": 4},
        )
        container.rename(backup_name) if not dry_run else None
        container.reload() if not dry_run else None
        logging.info(
            f"{'Would stop' if dry_run else 'Stopping'} original container '{container.id}'",
            extra={"indent": 4},
        )
        container.stop() if not dry_run else None
    except Exception as e:
        logging.error(
            f"Failed to prepare container '{container.id}' for replacement (rename/stop): {e}",
            extra={"indent": 6},
        )
        _rollback() if not dry_run else None
        return None

    try:
        spec = get_container_spec(client, container_inspect_data, original_name, image)
        response = client.api.create_container(**spec) if not dry_run else None
        new_container = client.containers.get(response.get("Id")) if not dry_run and response else container

        logging.debug(
            f"{'Would start' if dry_run else 'Starting'} new container{f' {new_container.id} ' if not dry_run else ''}with image '{image}'",
            extra={"indent": 4},
        )
        new_container.start() if not dry_run else None
        verify_container_start(container=new_container, dry_run=dry_run)

        logging.info(
            f"{'Would have recreated' if dry_run else 'Recreated'} new container '{new_container.id}' with image '{image}'",
            extra={"indent": 4},
        )
        return new_container if not dry_run else container

    except Exception as e:
        logging.error(f"Failed to recreate new container: {e}", extra={"indent": 4})
        _rollback() if not dry_run else None
        return None


def is_self_container(container_name, container_id):
    """
    Check if the given container is the container-updater itself.

    Parameters:
        container_name (str): Name of the container to check
        container_id (str, optional): ID of the container to check

    Returns:
        bool: True if this is the self container, False otherwise
    """

    logging.debug("Checking if the given container is the container-updater itself", extra={"indent": 6})
    logging.debug(f"func_params:\n{json.dumps({k: v for k, v in locals().items()}, indent=4)}", extra={"indent": 4})

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
    logging.debug(f"Checking against container name: {container_name}, container ID: {container_id}", extra={"indent": 8})

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

    # Also check if the container name is a substring of any identifier (for cases where
    # the container name is part of a longer identifier)
    for identifier in possible_identifiers:
        if container_name in identifier or identifier in container_name:
            logging.debug(f"Self container detected: partial match between {container_name} and {identifier}", extra={"indent": 8})
            return True

    logging.debug("Self container not detected", extra={"indent": 8})
    return False
