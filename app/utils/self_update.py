#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import os
import tempfile

from docker.types import Mount


def complete_self_update(client, dry_run):
    """
    Check if this is a new container instance that needs to complete a self-update.
    This function checks for a marker file that indicates a self-update was in progress.
    """
    marker_file = os.path.join(tempfile.gettempdir(), "container_updater_self_update_marker")

    if os.path.exists(marker_file):
        logging.info("Self-update marker found - completing self-update process", extra={"indent": 0})

        try:
            # Remove the marker file
            if not dry_run:
                os.remove(marker_file)
                logging.info("Self-update marker removed", extra={"indent": 2})
            else:
                logging.info("Would remove self-update marker", extra={"indent": 2})

        except Exception as e:
            logging.error(f"Failed to remove self-update marker: {e}", extra={"indent": 2})


def create_self_update_helper_container(client, container_name, new_image_reference, dry_run):
    """
    Create a helper container to perform the self-update.

    Parameters:
        client: Docker client instance
        container_name: Name of the container to update
        new_image_reference: New image reference to use
        dry_run: If True, only log what would be done

    Returns:
        Container object if successful, None otherwise
    """
    helper_name = f"{container_name}_self_update_helper"

    # Create script to run inside helper container
    script_content = f"""
                        #!/bin/bash

                        # Waiting 200 sec (Debugging and Testing)
                        sleep 200

                        # Create config directory
                        mkdir -p /app/conf

                        # Create config file directly in the container
                        cat > /app/conf/captn.cfg << 'EOF'
                        [logging]
                        level = DEBUG

                        [rules]
                        default = {{
                            "minImageAge": "99999h",
                            "progressiveUpgrade": false,
                            "allow": {{
                                "major": true,
                                "minor": true,
                                "patch": true,
                                "build": true,
                                "digest": true
                            }}
                        }}
                        EOF

                        # Run container updater
                        captn --run --filter name={container_name}

                        # Exit
                        exit 0
                    """

    try:
        # Prepare container configuration with only the Docker socket mount
        mounts = [
            Mount(type="bind", source="/var/run/docker.sock", target="/var/run/docker.sock")
        ]

        # Create helper container
        log_action = "Would create" if dry_run else "Creating"
        logging.info(f"{log_action} helper container '{helper_name}'", extra={"indent": 4})

        if not dry_run:
            container = client.containers.run(
                image=new_image_reference,
                name=helper_name,
                mounts=mounts,
                privileged=False,
                remove=True,
                detach=True,
                command=["/bin/bash", "-c", script_content],
            )

            logging.info(
                f"Helper container '{helper_name}' created with ID: {container.short_id}",
                extra={"indent": 6},
            )
            return container
        else:
            logging.info(
                f"Would create helper container with script content length: {len(script_content)}",
                extra={"indent": 6},
            )
            return None

    except Exception as e:
        logging.error(f"Failed to create helper container '{helper_name}': {e}", extra={"indent": 4})
        return None
