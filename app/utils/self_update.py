#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import os

from docker.types import Mount
from app.utils.config import config


def is_self_update_helper():
    """
    Check if this captn instance is running as a self-update helper.

    This function checks for the ROLE environment variable to determine
    if this instance should act as a self-update helper container.

    Returns:
        bool: True if this is a self-update helper, False otherwise
    """
    role = os.environ.get("ROLE")
    return role == "SELFUPDATEHELPER"


def should_skip_daemon_mode():
    """
    Determine if captn should skip daemon mode based on its role.

    Self-update helper containers should not start the daemon mode
    as they are meant to perform a specific update task and then exit.

    Returns:
        bool: True if daemon mode should be skipped, False otherwise
    """
    return is_self_update_helper()


def complete_self_update(client, dry_run):
    """
    Legacy function for backward compatibility.

    This function is kept for backward compatibility but is no longer needed
    with the new ROLE-based self-update approach.

    Parameters:
        client: Docker client instance
        dry_run (bool): If True, only log what would be done
    """
    # This function is no longer needed with the new approach
    # but kept for backward compatibility
    pass


def create_self_update_helper_container(client, container_name, new_image_reference, dry_run):
    """
    Create a helper container to perform the self-update.

    This function creates a temporary helper container that will perform the
    actual self-update operation. The helper container runs the new image
    with the ROLE=SELFUPDATEHELPER environment variable and will execute
    captn to update the original container, then exit.

    Parameters:
        client: Docker client instance
        container_name: Name of the container to update
        new_image_reference: New image reference to use
        dry_run: If True, only log what would be done

    Returns:
        Container object if successful, None otherwise
    """
    helper_name = f"{container_name}_self_update_helper"

    try:
        # Prepare container configuration with only the Docker socket mount
        mounts = [
            Mount(type="bind", source="/var/run/docker.sock", target="/var/run/docker.sock")
        ]

        # Environment variables for the helper container
        environment = {
            "ROLE": "SELFUPDATEHELPER",
            "TARGET_CONTAINER": container_name,
        }

        # Get removeHelperContainer setting from config
        remove_helper = getattr(config.selfUpdate, "removeHelperContainer", False)

        # Create helper container
        action = "Would create" if dry_run else "Creating"
        logging.info(f"{action} helper container '{helper_name}'", extra={"indent": 2})

        if not dry_run:
            container = client.containers.run(
                image=new_image_reference,
                name=helper_name,
                mounts=mounts,
                environment=environment,
                privileged=False,
                remove=remove_helper,
                detach=True,
                command=[f"{'--dry-run' if dry_run else '--run'}", "--filter", f"name={container_name}", "--log-level", "debug"],
            )

            logging.info(f"Helper container '{helper_name}' created with ID: {container.short_id}", extra={"indent": 4})
            return container
        else:
            logging.info(f"Would create helper container", extra={"indent": 4})
            return None

    except Exception as e:
        logging.error(f"Failed to create helper container '{helper_name}': {e}", extra={"indent": 4})
        return None


def execute_self_update_from_helper(client, target_container_name, dry_run):
    """
    Execute self-update from within a helper container.

    This function is called when captn is running as a self-update helper
    (ROLE=SELFUPDATEHELPER). It performs the actual update of the target
    container and then exits the helper container.

    Parameters:
        client: Docker client instance
        target_container_name: Name of the container to update
        dry_run: If True, only log what would be done
    """
    if not is_self_update_helper():
        logging.warning("execute_self_update_from_helper called but ROLE is not SELFUPDATEHELPER", extra={"indent": 0})
        return

    logging.info(f"Executing self-update for container '{target_container_name}' from helper", extra={"indent": 0})

    try:
        # Get the target container
        target_container = None
        try:
            target_container = client.containers.get(target_container_name)
        except Exception as e:
            logging.error(f"Target container '{target_container_name}' not found: {e}", extra={"indent": 2})
            return

        # Get container inspection data
        container_inspect_data = client.api.inspect_container(target_container.id)

        # Get image inspect data for environment filtering
        current_image_id = container_inspect_data.get("Image")
        image_inspect_data = client.api.inspect_image(current_image_id)

        # The helper container is running the new image, so we need to get the new image reference
        # from the helper container's image
        try:
            helper_container_id = os.environ.get("HOSTNAME", "")
            helper_inspect = client.api.inspect_container(helper_container_id)
            helper_image_id = helper_inspect.get("Image")
            helper_image = client.images.get(helper_image_id)
            new_image_reference = helper_image.tags[0] if helper_image.tags else helper_image.id
        except Exception as e:
            logging.error(f"Could not get helper image reference: {e}", extra={"indent": 2})
            return

        # Recreate the container with the new image
        new_container = recreate_container(
            client,
            target_container,
            new_image_reference,
            container_inspect_data,
            dry_run,
            image_inspect_data
        )

        if new_container:
            logging.info(f"Successfully updated container '{target_container_name}'", extra={"indent": 2})
        else:
            logging.error(f"Failed to update container '{target_container_name}'", extra={"indent": 2})

    except Exception as e:
        logging.error(f"Error during self-update execution: {e}", extra={"indent": 2})
    finally:
        # Helper container should exit after completing the update
        if not dry_run:
            logging.info("Self-update helper container exiting", extra={"indent": 0})
            # Exit the process to stop the helper container
            os._exit(0)


def trigger_self_update_from_producer(client, container_name, new_image_reference, dry_run):
    """
    Trigger a self-update process by creating a helper container.

    This function initiates the self-update process for the captn container by creating
    a temporary helper container that will handle the actual update process. The helper
    container runs independently and can safely update the main captn container without
    being affected by the update itself.

    The function creates a helper container with the necessary environment variables
    and configuration to perform the self-update. If the helper container creation
    fails, it attempts to clean up any partially created resources.

    Args:
        client: Docker client instance for container operations
        container_name (str): Name of the container to be updated (typically 'captn')
        new_image_reference (str): Full image reference for the new version to update to
        dry_run (bool): If True, simulate the update process without making actual changes

    Returns:
        None: This function doesn't return a value, but logs the progress and results

    Raises:
        Exception: Any exceptions during helper container creation are caught and logged,
                  but not re-raised to prevent disruption of the main update process

    Note:
        This function is called at the end of the main update cycle to handle self-updates
        separately from other container updates, ensuring that the captn container can
        be updated without interrupting the update process itself.
    """
    try:
        helper_container = create_self_update_helper_container(
            client, container_name, new_image_reference, dry_run
        )
        if helper_container:
            logging.info(f"Update process for '{container_name}' is now handled by '{helper_container.name}'", extra={"indent": 2})
    except Exception as e:
        logging.error("Failed to create helper container", extra={"indent": 2})
        try:
            helper_container.remove(force=True)
            logging.info("Helper container cleaned up", extra={"indent": 2})
        except Exception as e:
            logging.warning(f"Could not clean up helper container: {e}", extra={"indent": 2})


def recreate_container(client, container, image, container_inspect_data, dry_run, image_inspect_data=None):
    """
    Import and call the recreate_container function from engines.docker.

    This function is a wrapper that imports and calls the actual recreate_container
    function from the engines.docker module, providing a consistent interface
    for self-update operations.

    Parameters:
        client: Docker client instance
        container: Container object to recreate
        image: New image reference
        container_inspect_data: Original container inspection data
        dry_run (bool): If True, only log what would be done
        image_inspect_data: Image inspection data for environment filtering (optional)

    Returns:
        Container object if successful, None otherwise
    """
    from .engines.docker import recreate_container as _recreate_container
    return _recreate_container(client, container, image, container_inspect_data, dry_run, image_inspect_data)
