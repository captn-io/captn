#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
import logging
import os
import textwrap
import time
import argcomplete
from argparse import RawTextHelpFormatter
from datetime import datetime, timezone

from app import __version__

from .utils import cleanup, common, engines, self_update
from .utils.registries import get_image_tags
from .utils.common import setup_logging
from .utils.config import config, create_example_config
from .utils.scripts import execute_pre_script, execute_post_script, should_continue_on_pre_failure, should_rollback_on_post_failure
from .utils.notifiers import notification_manager


def get_container_names():
    """
    Get list of all Docker container names for auto-completion.

    This function retrieves all Docker containers (running and stopped) and returns
    their names for use in command-line argument completion.

    Returns:
        list: List of container names, or empty list if Docker client is unavailable
    """
    try:
        client = engines.get_client()
        if client:
            containers = client.containers.list(all=True)
            return [container.name for container in containers]
    except Exception:
        pass
    return []


def get_container_statuses():
    """
    Get list of valid container statuses for auto-completion.

    This function returns all valid Docker container statuses that can be used
    for filtering containers in the command-line interface.

    Returns:
        list: List of valid container status strings
    """
    return ["running", "exited", "created", "paused", "restarting", "removing", "dead", "all"]


def get_log_levels():
    """
    Get list of valid log levels for auto-completion.

    This function returns all valid logging levels that can be used
    in the command-line interface for setting the application's log verbosity.

    Returns:
        list: List of valid log level strings
    """
    return ["debug", "info", "warning", "error", "critical"]


def clear_logs():
    """
    Delete all log files and comparison files in the logs directory.

    This function removes all log files (captn.log*) and comparison files
    (container_comparison_*.json) from the application's logs directory.
    It's used to clean up old log data before starting a new update cycle.

    The function handles both regular log files and their rotated versions,
    as well as container comparison files created during update verification.
    """
    import glob
    import os

    log_dir = os.path.join(os.path.dirname(__file__), "logs")
    if os.path.exists(log_dir):
        deleted_count = 0

        # Find all log files (captn.log, captn.log.1, captn.log.2, etc.)
        log_pattern = os.path.join(log_dir, "captn.log*")
        log_files = glob.glob(log_pattern)

        for log_file in log_files:
            try:
                # Delete the file completely
                os.remove(log_file)
                deleted_count += 1
                logging.info(f"Deleted log file: {os.path.basename(log_file)}")
            except Exception as e:
                logging.error(f"Failed to delete log file {log_file}: {e}")

        # Find all comparison files (container_comparison_*.json)
        comparison_pattern = os.path.join(log_dir, "container_comparison_*.json")
        comparison_files = glob.glob(comparison_pattern)

        for comparison_file in comparison_files:
            try:
                # Delete the file completely
                os.remove(comparison_file)
                deleted_count += 1
                logging.info(f"Deleted comparison file: {os.path.basename(comparison_file)}")
            except Exception as e:
                logging.error(f"Failed to delete comparison file {comparison_file}: {e}")

        if deleted_count > 0:
            logging.info(f"Successfully deleted {deleted_count} file(s)")
        else:
            logging.info("No log or comparison files found to delete")
    else:
        logging.info("Log directory not found")


def parse_args():
    """
    Parse command-line arguments for the captn application.

    This function sets up the argument parser with all available command-line options
    including filters, logging configuration, dry-run mode, and daemon mode.
    It also configures auto-completion for container names, statuses, and log levels.

    Returns:
        argparse.Namespace: Parsed command-line arguments
    """
    parser = argparse.ArgumentParser(
        prog="captn.io/captn",
        description=(
            "A rule-driven container updater that automates container updates based on semantic versioning and registry metadata."
        ),
        formatter_class=RawTextHelpFormatter,
    )

    parser.add_argument(
        "--version", "-v",
        action="version",
        version=__version__,
        help="Display the current version"
    )
    parser.add_argument(
        "--run", "-r",
        action="store_true",
        help="Force actual execution without dry-run, overriding the configuration"
    )
    parser.add_argument(
        "--dry-run", "-t",
        action="store_true",
        help="Run Container Updater in dry-run mode to review what it would do (default is set in config)"
    )
    filter_arg = parser.add_argument(
        "--filter", nargs="*", metavar="FILTER",
        help=textwrap.dedent("""
                            Filter the list of containers to process.

                            Supported filter expressions:
                            name=<container_name>       Match container names. If wildcards (*, ?) are used,
                                                        pattern matching is applied. If no wildcards are given,
                                                        exact name matching is enforced. You can specify
                                                        multiple name filters.

                            status=<status>             Filter by container status. Supported values:
                                                        running, exited, created, paused, restarting,
                                                        removing, dead, or all.

                            Examples:
                            --filter name=nginx name=redis
                            --filter name=ngin* name=*cloud* name=cloud-0?
                            --filter status=running
                            --filter name=webapp status=all

                        """)
    )
    parser.add_argument(
        "--log-level", "-l",
        choices=["debug", "info", "warning", "error", "critical"],
        default=(
            config.logging.level.lower()
            if config.logging.level.lower() in ["debug", "info", "warning", "error", "critical"]
            else "info"
        ),
        help="Set the logging level",
    )
    parser.add_argument(
        "--clear-logs", "-c",
        action="store_true",
        help="Clear all log files before starting",
    )
    parser.add_argument(
        "--daemon", "-d",
        action="store_true",
        help="Run captn as a daemon with scheduled execution based on cronSchedule in config",
    )

    if argcomplete:
        argcomplete.autocomplete(parser)

    return parser.parse_args()


def main():
    """
    Main entry point for the captn application.

    This function orchestrates the entire container update process:
    1. Parses command-line arguments
    2. Sets up logging and configuration
    3. Handles daemon mode if requested
    4. Processes containers based on filters and rules
    5. Performs self-updates if needed
    6. Cleans up unused resources

    The function supports both interactive and daemon modes, with comprehensive
    logging and error handling throughout the update process.
    """
    args = parse_args()

    # Create/update example config file if running in container environment
    # This ensures the example file is always available when config directory is mounted
    if os.path.exists("/app/conf"):
        create_example_config()

    # Handle daemon mode
    if args.daemon:
        # Check if this is a self-update helper container
        if self_update.should_skip_daemon_mode():
            logging.info("Running as self-update helper - skipping daemon mode", extra={"indent": 0})
            return

        from .utils.scheduler import start_scheduler
        import signal
        import sys

        def signal_handler(signum, frame):
            logging.info("Received shutdown signal, stopping scheduler...")
            from .utils.scheduler import stop_scheduler
            stop_scheduler()
            sys.exit(0)

        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)

        # Setup logging
        setup_logging(log_level=args.log_level, dry_run=False)

        # Start the scheduler
        start_scheduler()

        # Keep the main thread alive
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logging.info("Received keyboard interrupt, shutting down...")
            from .utils.scheduler import stop_scheduler
            stop_scheduler()
        return

    dry_run = (
        False if args.run
        else (True if args.dry_run else str(config.general.dryRun).lower() in ("yes", "true", "1"))
    )

    # Clear logs if requested
    if args.clear_logs:
        clear_logs()

    setup_logging(log_level=args.log_level, dry_run=dry_run)

    client = engines.get_client()
    if not client:
        logging.error("Failed to get Docker client")
        return

    # Check if this is a self-update helper container
    if self_update.is_self_update_helper():
        logging.info("Running as self-update helper container", extra={"indent": 0})
        target_container = os.environ.get("TARGET_CONTAINER")
        if target_container:
            self_update.execute_self_update_from_helper(client, target_container, dry_run)
        else:
            logging.error("TARGET_CONTAINER environment variable not set", extra={"indent": 0})
        return

    # Check if this is a new container instance that needs to complete a self-update
    if not dry_run:
        self_update.complete_self_update(client, dry_run)

    containers = engines.get_containers(args.filter, client)

    if not containers:
        logging.info("No containers found matching the specified filters")
        return

    # Reset notification statistics at the start of each update cycle
    notification_manager.reset_stats()
    notification_manager.set_start_time()

    for container in containers:
        logging.info(f"Processing container '{container.name}'", extra={"indent": 0})

        # Rule pre-check: Determine if the container has any allowed update types
        allowed_types, effective_rule, rule_name_original = common.get_container_allowed_update_types(
            container_name=container.name,
            image_reference=None,  # Will be determined later when we have the actual image data
        )

        if not allowed_types:
            logging.info(
                f"Skipping container '{container.name}' - Assigned rule '{effective_rule}' does not allow any updates",
                extra={"indent": 2},
            )
            notification_manager.increment_skipped()
            continue

        notification_manager.increment_processed()

        try:
            container_inspect_data = client.api.inspect_container(container.id)
            image = client.images.get(container_inspect_data.get("Image"))
            image_metadata = engines.get_local_image_metadata(image, container_inspect_data)
            if not image_metadata:
                logging.error(f"Failed to get image metadata for container '{container.name}'", extra={"indent": 2})
                continue
            image_inspect_data = client.api.inspect_image(container_inspect_data.get("Image"))
            remote_image_tags = get_image_tags(
                imageName=image_metadata["name"],
                imageUrl=image_metadata["imageUrl"],
                registry=image_metadata["registry"],
                imageTagsUrl=image_metadata["imageTagsUrl"],
                imageTag=(
                    container_inspect_data["Config"]["Image"].rsplit(":", 1)[1]
                    if ":" in container_inspect_data["Config"]["Image"]
                    else None
                ),
            )
        except Exception as e:
            error_msg = f"Failed to inspect container '{container.name}': {e}"
            logging.error(error_msg, extra={"indent": 2})
            notification_manager.add_error(error_msg)
            continue

        # Debug logging with conditional formatting
        logging.debug(f"-> container_inspect_data:  \n{json.dumps(container_inspect_data, indent=4) if container_inspect_data   else None}", extra={"indent": 2})
        logging.debug(f"-> image_inspect_data:      \n{json.dumps(image_inspect_data, indent=4)     if image_inspect_data       else None}", extra={"indent": 2})
        logging.debug(f"-> image_metadata:          \n{json.dumps(image_metadata, indent=4)         if image_metadata           else None}", extra={"indent": 2})
        logging.debug(f"-> remote_image_tags:       \n{json.dumps(remote_image_tags, indent=4)      if remote_image_tags        else None}", extra={"indent": 2})

        if (container and container_inspect_data and image and image_metadata and image_inspect_data and remote_image_tags):
            virtual_image_metadata = image_metadata.copy() if dry_run else None
            for i, remote_image_tag in enumerate(reversed(remote_image_tags)):
                update_type = common.get_update_type(
                    old_version=(
                        virtual_image_metadata.get("tag") if dry_run and virtual_image_metadata
                        else image_metadata.get("tag") if image_metadata else None
                    ),
                    new_version=remote_image_tag.get("name"),
                    local_digests=image_inspect_data.get("RepoDigests"),
                    remote_digest=remote_image_tag.get("digest"),
                )
                logging.debug(f"-> update_type: {update_type}", extra={"indent": 6})

                if not update_type and i == len(remote_image_tags) - 1:
                    logging.info(f"No relevant image updates available for container '{container.name}'", extra={"indent": 2})

                if update_type not in ["unknown", None]:
                    update_permit, effective_rule, rule_name_original, update_reject_reason, new_image_reference = common.get_update_permit(
                        container_name=container.name,
                        image_reference=image_metadata.get("reference") if image_metadata else None,
                        update_type=update_type,
                        age=(
                            int((datetime.now(timezone.utc) - datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)).total_seconds() / 60)
                            if (ts := remote_image_tag.get("last_updated"))
                            else None
                        ),
                        old_version=(
                            virtual_image_metadata.get("tag") if dry_run and virtual_image_metadata
                            else image_metadata.get("tag") if image_metadata else None
                        ),
                        new_version=remote_image_tag.get("name"),
                        latest_version=remote_image_tags[0].get("name"),
                        pre_check=False,
                    )

                    if effective_rule != rule_name_original:
                        logging.warning(
                            f"Assigned rule '{rule_name_original}' not found for container '{container.name}', fallback to 'default'",
                            extra={"indent": 2},
                        )

                    current_tag = (
                        virtual_image_metadata.get("tag") if dry_run and virtual_image_metadata
                        else image_metadata.get("tag") if image_metadata else None
                    )
                    log_tag_info = (
                        f"{current_tag} -> {remote_image_tag.get('name')}" if update_type != "digest"
                        else f"{current_tag}"
                    )

                    if update_permit:
                        log_action = "Would process" if dry_run else "Processing"
                        logging.info(
                            f"{log_action} {update_type} update for '{container.name}' ({log_tag_info}) allowed by rule '{effective_rule}'",
                            extra={"indent": 2},
                        )

                        # Start timing for this update
                        update_start_time = time.time()

                        # 1. Fetch new image
                        new_image = engines.pull_image(client, new_image_reference, dry_run)
                        if not new_image and not dry_run:
                            continue

                        # 2. Run Pre-Scripts
                        pre_success, pre_output = execute_pre_script(container.name, dry_run)
                        if not pre_success and not should_continue_on_pre_failure():
                            error_msg = f"Pre-script failed for container '{container.name}'"
                            logging.error(error_msg, extra={"indent": 4})
                            notification_manager.add_error(error_msg)
                            current_tag = image_metadata.get("tag") if image_metadata else "Unknown"
                            new_tag = remote_image_tag.get("name") if remote_image_tag else "Unknown"
                            update_duration = time.time() - update_start_time
                            notification_manager.add_update_detail(
                                container_name=container.name,
                                old_version=current_tag,
                                new_version=new_tag,
                                update_type=update_type,
                                duration=update_duration,
                                status="failed"
                            )
                            continue

                        # 3. Recreate container
                        if engines.is_self_container(container.name, container.id):
                            # Prepare update info for potential failure tracking
                            current_tag = image_metadata.get("tag") if image_metadata else "Unknown"
                            new_tag = remote_image_tag.get("name") if remote_image_tag else "Unknown"

                            # Self-Update: Handle self-update if this is the self container
                            logging.info(
                                f"Self-update detected for container '{container.name}' - scheduling for end of update cycle",
                                extra={"indent": 4},
                            )

                            # Store the update info for later processing
                            main.self_update_info = {
                                "container": container,
                                "new_image_reference": new_image_reference,
                                "update_type": update_type,
                            }

                            # Self-Update: Currently we just assume that a self update will succeed because the helper container does not have access to the configuration and is not able to send messages
                            update_duration = time.time() - update_start_time
                            notification_manager.add_update_detail(
                                container_name=container.name,
                                old_version=current_tag,
                                new_version=new_tag,
                                update_type=update_type,
                                duration=update_duration
                            )

                            logging.debug(
                                "Progressive updates are not supported for self-updates - skipping remaining updates for actual execution",
                                extra={"indent": 4},
                            )
                            break
                        else:
                            # Prepare update info for potential failure tracking
                            current_tag = image_metadata.get("tag") if image_metadata else "Unknown"
                            new_tag = remote_image_tag.get("name") if remote_image_tag else "Unknown"

                            new_container = engines.recreate_container(client, container, new_image_reference, container_inspect_data, dry_run, image_inspect_data, notification_manager)
                            if new_container:
                                try:
                                    # Refresh container and used image information
                                    container = new_container
                                    container_inspect_data = client.api.inspect_container(container.id)
                                    image = client.images.get(container_inspect_data.get("Image"))
                                    image_metadata = engines.get_local_image_metadata(image, container_inspect_data)
                                    image_inspect_data = client.api.inspect_image(container_inspect_data.get("Image"))

                                    # In dry-run mode, update the virtual image tag to simulate a successful update and ensure accurate logging
                                    if dry_run and virtual_image_metadata:
                                        virtual_image_metadata["tag"] = remote_image_tag.get("name")

                                    logging.info(
                                        f"{'Would have recreated' if dry_run else 'Successfully recreated'} container '{new_container.name}' with updated image '{new_image_reference}'",
                                        extra={"indent": 4},
                                    )

                                    # Add successful update to notification statistics
                                    update_duration = time.time() - update_start_time
                                    notification_manager.add_update_detail(
                                        container_name=new_container.name,
                                        old_version=current_tag,
                                        new_version=new_tag,
                                        update_type=update_type,
                                        duration=update_duration
                                    )

                                except Exception as e:
                                    error_msg = f"Update failed for container '{new_container.name}': {e}"
                                    logging.error(error_msg, extra={"indent": 4})
                                    notification_manager.add_error(error_msg)

                                    # Add failed update to notification statistics
                                    update_duration = time.time() - update_start_time
                                    notification_manager.add_update_detail(
                                        container_name=new_container.name,
                                        old_version=current_tag,
                                        new_version=new_tag,
                                        update_type=update_type,
                                        duration=update_duration,
                                        status="failed"
                                    )
                            else:
                                error_msg = f"Failed to recreate container '{container.name}'"
                                logging.error(error_msg, extra={"indent": 4})
                                notification_manager.add_error(error_msg)

                                # Add failed update to notification statistics
                                update_duration = time.time() - update_start_time
                                notification_manager.add_update_detail(
                                    container_name=container.name,
                                    old_version=current_tag,
                                    new_version=new_tag,
                                    update_type=update_type,
                                    duration=update_duration,
                                    status="failed"
                                )

                        # 4. Wait for some seconds
                        if (config.update.delayBetweenUpdates and remote_image_tag != remote_image_tags[0] and json.loads(config.rules._values.get(effective_rule, "{}")).get("progressiveUpgrade", True)):
                            delay_s = common.parse_duration(config.update.delayBetweenUpdates, "s")
                            logging.info( f"Waiting {delay_s} second{'s' if delay_s != 1 else ''} before processing the next update for the same container", extra={"indent": 4}, )
                            if not dry_run:
                                time.sleep(delay_s)

                        if (not json.loads(config.rules._values.get(effective_rule, "{}")).get("progressiveUpgrade", True) and i < len(remote_image_tags) - 1):
                            logging.info( f"Progressive update disabled by rule '{effective_rule}' - skipping remaining updates for actual execution", extra={"indent": 4}, )
                            break
                    else:
                        logging.info(
                            f"{update_type.capitalize() if update_type else 'Unknown'} update for '{container.name}' ({log_tag_info}) has been prevented by rule '{effective_rule}' "
                            f"(Reason: [{update_reject_reason}]"
                            f"{' ' + (update_type.capitalize() if update_type else 'Unknown') + ' updates are generally not allowed' if update_reject_reason == 'General' else ''}"
                            f"{' Image age is too recent' if update_reject_reason == 'MinImageAge' else ''}"
                            f"{' Required conditions have not been satisfied' if update_reject_reason == 'Conditions' else ''}"
                            f"{' Version is too recent' if update_reject_reason == 'LagPolicy' else ''})",
                            extra={"indent": 2},
                        )
                elif not update_type:
                    pass
                else:
                    logging.warning(f"Unable to process update of type '{update_type}' for container '{container.name}'", extra={"indent": 2})

        elif not remote_image_tags:
            logging.info(f"No relevant image updates available for container '{container.name}'", extra={"indent": 2})
            notification_manager.increment_skipped()
        else:
            error_msg = (
                f"Missing required data for container '{container.name if container else 'UNKNOWN'}': "
                f"{'container ' if not container else ''}"
                f"{'inspect_data ' if not container_inspect_data else ''}"
                f"{'image ' if not image else ''}"
                f"{'image_metadata ' if not image_metadata else ''}"
                f"{'image_inspect_data ' if not image_inspect_data else ''}"
                f"{'remote_image_tags' if not remote_image_tags else ''}"
            )
            logging.error(error_msg, extra={"indent": 2})
            notification_manager.add_error(error_msg)

    # Handle self-updates at the very end to avoid interrupting other container updates
    if hasattr(main, "self_update_info") and main.self_update_info:
        container = main.self_update_info["container"]
        new_image_reference = main.self_update_info["new_image_reference"]

        logging.info(f"Processing self-update", extra={"indent": 0})

        if not dry_run:
            self_update.trigger_self_update_from_producer(
                client=client,
                container_name=container.name,
                new_image_reference=new_image_reference,
                dry_run=dry_run
            )
        else:
            logging.info("Would trigger self-update via helper container", extra={"indent": 4})

    # Cleanup unused images and backup containers based on prune settings
    if not hasattr(main, "self_update_info") or not main.self_update_info:
        cleanup.perform_cleanup(client, dry_run)
    else:
        logging.info("Skipped cleanup because a self-update is pending", extra={"indent": 0})

    # Send notification report at the end of the update cycle
    notification_manager.send_update_report(dry_run=dry_run)


if __name__ == "__main__":
    main()
