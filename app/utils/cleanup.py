#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
from datetime import datetime

from .common import parse_duration
from .config import config


def cleanup_old_backup_containers(client, dry_run=False):
    """
    Remove old backup containers created by container-updater.

    Parameters:
        client: Docker client instance
        dry_run (bool): If True, only log what would be done without actually removing

    Returns:
        int: Number of containers removed
    """
    if not config.prune.removeOldContainers:
        logging.debug("Container cleanup disabled by configuration", extra={"indent": 4})
        return 0

    logging.info(
        f"{'Would check and remove' if dry_run else 'Checking and removing'} old backup containers",
        extra={"indent": 4},
    )

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
                        logging.debug(
                            f"{'Would remove' if dry_run else 'Removing'} container '{container_name}'",
                            extra={"indent": 6},
                        )
                        if not dry_run:
                            container.remove()
                            removed_count += 1

                except Exception as e:
                    logging.warning(
                        f"Could not parse or evaluate container '{container_name}' for pruning: {e}",
                        extra={"indent": 6},
                    )

    except Exception as e:
        logging.error(f"Container cleanup failed: {e}", extra={"indent": 4})

    return removed_count


def cleanup_unused_images(client, dry_run=False):
    """
    Remove unused Docker images.

    Parameters:
        client: Docker client instance
        dry_run (bool): If True, only log what would be done without actually removing

    Returns:
        dict: Prune results from Docker API
    """
    if not config.prune.removeUnusedImages:
        logging.debug("Image cleanup disabled by configuration", extra={"indent": 4})
        return {}

    logging.info(
        f"{'Would remove' if dry_run else 'Removing'} images unused within the past 24h",
        extra={"indent": 4},
    )

    try:
        # Get current images before pruning
        images_before = client.images.list()
        logging.debug(f"Images before pruning: {len(images_before)}", extra={"indent": 6})

        if not dry_run:
            # Use more aggressive pruning options
            result = client.images.prune(
                filters={
                    "dangling": False,  # Remove all unused images, not just dangling ones
                    "until": "24h",  # Remove images older than 24h if unused
                }
            )
            logging.debug(f"Image prune result: {result}", extra={"indent": 6})

            # Get images after pruning
            images_after = client.images.list()
            logging.debug(
                f"Images after pruning: {len(images_after)} (removed {len(images_before) - len(images_after)})",
                extra={"indent": 6},
            )

            return result
        else:
            return {}

    except Exception as e:
        logging.error(f"Image cleanup failed: {e}", extra={"indent": 4})
        return {}


def perform_cleanup(client, dry_run=False):
    """
    Perform all cleanup operations based on configuration.

    Parameters:
        client: Docker client instance
        dry_run (bool): If True, only log what would be done without actually removing

    Returns:
        dict: Summary of cleanup operations performed
    """
    logging.info(f"{'Would perform' if dry_run else 'Performing'} cleanup operations", extra={"indent": 2})

    summary = {"containers_removed": 0, "images_pruned": False, "errors": []}

    try:
        # Cleanup old backup containers
        summary["containers_removed"] = cleanup_old_backup_containers(client, dry_run)

        # Cleanup unused images
        image_result = cleanup_unused_images(client, dry_run)
        summary["images_pruned"] = bool(image_result)

    except Exception as e:
        error_msg = f"Cleanup operation failed: {e}"
        logging.error(error_msg, extra={"indent": 2})
        summary["errors"].append(error_msg)

    return summary
