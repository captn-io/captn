#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
from datetime import datetime

from .common import parse_duration
from .config import config


def cleanup_backup_containers(client, dry_run=False):
    """
    Remove backup containers created by captn.

    This function identifies and removes backup containers that have exceeded
    the minimum age threshold defined in the configuration. Backup containers
    are created during the update process and follow the naming pattern
    <container_name>_bak_cu_<timestamp>.

    Parameters:
        client: Docker client instance
        dry_run (bool): If True, only log what would be done without actually removing

    Returns:
        int: Number of containers removed
    """
    if not config.prune.removeOldContainers:
        logging.debug("Container cleanup disabled by configuration", extra={"indent": 2})
        return 0

    logging.info(f"{'Would check and remove' if dry_run else 'Checking and removing'} backup containers", extra={"indent": 2})

    removed_count = 0
    now = datetime.now()

    try:
        for container in client.containers.list(all=True, filters={"status": "exited"}):
            container_name = container.name
            if "_bak_cu_" in container_name:
                try:
                    # Extract timestamp from backup container name
                    date_str = container_name.split("_bak_cu_")[-1]
                    container_time = datetime.strptime(date_str, "%Y%m%d-%H%M%S")
                    age_hours = (now - container_time).total_seconds() / 3600

                    min_age_hours = parse_duration(config.prune.minBackupAge, "h")

                    if age_hours >= min_age_hours:
                        logging.debug(f"{'Would remove' if dry_run else 'Removing'} container '{container_name}'", extra={"indent": 4})
                        if not dry_run:
                            container.remove()
                            removed_count += 1

                except Exception as e:
                    logging.warning(f"Could not parse or evaluate container '{container_name}' for pruning: {e}", extra={"indent": 4})

    except Exception as e:
        logging.error(f"Container cleanup failed: {e}", extra={"indent": 4})

    return removed_count


def cleanup_unused_images(client, dry_run=False):
    """
    Remove unused Docker images.

    This function removes Docker images that are no longer referenced by any
    containers. It uses Docker's built-in prune functionality to identify and
    remove unused images based on the configuration settings.

    Parameters:
        client: Docker client instance
        dry_run (bool): If True, only log what would be done without actually removing

    Returns:
        dict: Prune results from Docker API containing information about removed images
    """
    if not config.prune.removeUnusedImages:
        logging.debug("Image cleanup disabled by configuration", extra={"indent": 2})
        return {}

    logging.info(f"{'Would remove' if dry_run else 'Removing'} unused images", extra={"indent": 2})

    try:
        # Get current images before pruning
        images_before = client.images.list()
        logging.debug(f"Images before pruning: {len(images_before)}", extra={"indent": 4})

        if not dry_run:
            result = client.images.prune(
                filters={
                    "dangling": False,  # Remove all unused images
                    "until": "24h",     # Remove images older than 24h
                }
            )
            logging.debug(f"Image prune result: {result}", extra={"indent": 4})

            # Get images after pruning
            images_after = client.images.list()
            logging.debug(f"Images after pruning: {len(images_after)} (removed {len(images_before) - len(images_after)})", extra={"indent": 4})

            return result
        else:
            return {}

    except Exception as e:
        logging.error(f"Image cleanup failed: {e}", extra={"indent": 4})
        return {}


def perform_cleanup(client, dry_run=False):
    """
    Perform all cleanup operations based on configuration.

    This function orchestrates all cleanup operations including removal of old
    backup containers and pruning of unused images. It respects the configuration
    settings for each cleanup operation and provides a summary of what was performed.

    Parameters:
        client: Docker client instance
        dry_run (bool): If True, only log what would be done without actually removing

    Returns:
        dict: Summary of cleanup operations performed with counts and error information
    """
    if not config.prune.removeUnusedImages and not config.prune.removeOldContainers:
        logging.debug("All cleanup operations are disabled by configuration", extra={"indent": 0})
        return {}

    logging.info(f"{'Would perform' if dry_run else 'Performing'} cleanup operations", extra={"indent": 0})

    summary = {"containers_removed": 0, "images_pruned": False, "errors": []}

    try:
        # Cleanup backup containers
        summary["containers_removed"] = cleanup_backup_containers(client, dry_run)

        # Cleanup unused images
        image_result = cleanup_unused_images(client, dry_run)
        summary["images_pruned"] = bool(image_result)

    except Exception as e:
        error_msg = f"Cleanup operation failed: {e}"
        logging.error(error_msg, extra={"indent": 2})
        summary["errors"].append(error_msg)

    return summary
