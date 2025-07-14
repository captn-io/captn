#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
import logging
import os
import tempfile
import textwrap
import time
import argcomplete
from argparse import RawTextHelpFormatter
from datetime import datetime, timezone

from app import __version__

from .utils import cleanup, common, engines, registries, self_update
from .utils.common import setup_logging
from .utils.config import config


def get_container_names():
    """Get list of all Docker container names for auto-completion."""
    try:
        client = engines.get_client()
        if client:
            containers = client.containers.list(all=True)
            return [container.name for container in containers]
    except Exception:
        pass
    return []


def get_container_statuses():
    """Get list of valid container statuses for auto-completion."""
    return ["running", "exited", "created", "paused", "restarting", "removing", "dead", "all"]


def get_log_levels():
    """Get list of valid log levels for auto-completion."""
    return ["debug", "info", "warning", "error", "critical"]


def clear_logs():
    """Delete all log files in the logs directory."""
    import glob
    import os

    log_dir = os.path.join(os.path.dirname(__file__), "logs")
    if os.path.exists(log_dir):
        # Find all log files (captn.log, captn.log.1, captn.log.2, etc.)
        log_pattern = os.path.join(log_dir, "captn.log*")
        log_files = glob.glob(log_pattern)

        deleted_count = 0
        for log_file in log_files:
            try:
                # Delete the file completely
                os.remove(log_file)
                deleted_count += 1
                print(f"Deleted log file: {os.path.basename(log_file)}")
            except Exception as e:
                print(f"Failed to delete log file {log_file}: {e}")

        if deleted_count > 0:
            print(f"Successfully deleted {deleted_count} log file(s)")
        else:
            print("No log files found to delete")
    else:
        print("Log directory not found")

def parse_args():
    parser = argparse.ArgumentParser(
        prog="captn.io/captn",
        description=(
            "A rule-driven container updater that automates Docker container upgrades based on semantic versioning and registry metadata."
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
        "--force", "-f",
        action="store_true",
        help="Force lock acquisition"
    )
    parser.add_argument(
        "--run", "-r",
        action="store_true",
        help="Force actual execution without dry-run, overriding the configuration"
    )
    parser.add_argument(
        "--dry-run", "-t",
        action="store_true",
        help="Run Container Updater in dry-run/test mode to review what it would do (default is set in config)"
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

    if argcomplete:
        argcomplete.autocomplete(parser)

    return parser.parse_args()


def main():
    args = parse_args()
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

    # Check if this is a new container instance that needs to complete a self-update
    if not dry_run:
        self_update.complete_self_update(client, dry_run)

    containers = engines.get_containers(args.filter, client)

    if not containers:
        logging.info("No containers found matching the specified filters")
        return

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
            continue

        try:
            container_inspect_data = client.api.inspect_container(container.id)
            image = client.images.get(container_inspect_data.get("Image"))
            image_metadata = engines.get_local_image_metadata(image, container_inspect_data)
            if not image_metadata:
                logging.error(f"Failed to get image metadata for container '{container.name}'", extra={"indent": 2})
                continue
            image_inspect_data = client.api.inspect_image(container_inspect_data.get("Image"))
            remote_image_tags = registries.get_image_tags(
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
            logging.error(f"Failed to inspect container '{container.name}': {e}", extra={"indent": 2})
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

                        # 1. Pull new image
                        new_image = engines.pull_image(client, new_image_reference, dry_run)
                        if not new_image and not dry_run:
                            continue

                        # 2. Run Pre-Scripts (Backups, etc.)

                        # 3. Recreate container
                        if engines.is_self_container(container.name, container.id):
                            # Handle self-update if this is the self container
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

                            logging.debug(
                                "Progressive upgrades are not supported for self-updates - skipping remaining updates for actual execution",
                                extra={"indent": 4},
                            )
                            break
                        else:
                            new_container = engines.recreate_container(
                                client, container, new_image_reference, container_inspect_data, dry_run
                            )
                            if new_container:
                                try:
                                    # Refresh container and used image information
                                    container = new_container
                                    container_inspect_data = client.api.inspect_container(container.id)
                                    image = client.images.get(container_inspect_data.get("Image"))
                                    image_metadata = engines.get_local_image_metadata(image, container_inspect_data)
                                    image_inspect_data = client.api.inspect_image(container_inspect_data.get("Image"))

                                    # In dry-run mode, update the virtual image tag to simulate a successful upgrade and ensure accurate logging
                                    if dry_run and virtual_image_metadata:
                                        virtual_image_metadata["tag"] = remote_image_tag.get("name")

                                    logging.info(
                                        f"{'Would have replaced' if dry_run else 'Successfully replaced'} container '{new_container.name}' with updated image '{new_image_reference}'",
                                        extra={"indent": 4},
                                    )

                                except Exception as e:
                                    logging.error(f"Update failed for container '{new_container.name}': {e}", extra={"indent": 4})
                            else:
                                logging.error(f"Failed to replace container '{container.name}'", extra={"indent": 4})

                        # 4. Run Post-Scripts (Customizations, etc.)

                        # 5. Wait for some seconds
                        if (config.update.delayBetweenUpdates and remote_image_tag != remote_image_tags[0] and json.loads(config.rules._values.get(effective_rule, "{}")).get("progressiveUpgrade", True)):
                            delay_s = common.parse_duration(config.update.delayBetweenUpdates, "s")
                            logging.info( f"Waiting {delay_s} second{'s' if delay_s != 1 else ''} before processing the next update for the same container", extra={"indent": 4}, )
                            if not dry_run:
                                time.sleep(delay_s)

                        if (not json.loads(config.rules._values.get(effective_rule, "{}")).get("progressiveUpgrade", True) and i < len(remote_image_tags) - 1):
                            logging.info( f"Progressive upgrade disabled by rule '{effective_rule}' - skipping remaining updates for actual execution", extra={"indent": 4}, )
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
        else:
            logging.error(
                f"Missing required data for container '{container.name if container else 'UNKNOWN'}': "
                f"{'container ' if not container else ''}"
                f"{'inspect_data ' if not container_inspect_data else ''}"
                f"{'image ' if not image else ''}"
                f"{'image_metadata ' if not image_metadata else ''}"
                f"{'image_inspect_data ' if not image_inspect_data else ''}"
                f"{'remote_image_tags' if not remote_image_tags else ''}",
                extra={"indent": 2},
            )

    # Handle self-updates at the very end to avoid interrupting other container updates
    if hasattr(main, "self_update_info") and main.self_update_info:
        container = main.self_update_info["container"]
        new_image_reference = main.self_update_info["new_image_reference"]

        logging.info(f"{'Would trigger' if dry_run else 'Triggering'} self-update", extra={"indent": 2})

        # Create a marker file to indicate self-update is in progress
        marker_file = os.path.join(tempfile.gettempdir(), "container_updater_self_update_marker")
        if not dry_run:
            try:
                with open(marker_file, "w") as f:
                    f.write(f"Self-update in progress for {container.name} at {datetime.now(timezone.utc).isoformat()}")
                logging.info("Created self-update marker file", extra={"indent": 4})
            except Exception as e:
                logging.error(f"Failed to create self-update marker: {e}", extra={"indent": 4})
        else:
            logging.info(f"Would create self-update marker file: {marker_file}", extra={"indent": 4})

        # Create helper container to perform the self-update
        helper_container = self_update.create_self_update_helper_container(
            client=client, container_name=container.name, new_image_reference=new_image_reference, dry_run=dry_run
        )

        if helper_container:
            logging.info("Helper container created successfully for self-update", extra={"indent": 4})
        elif not dry_run:
            logging.error("Failed to create helper container for self-update", extra={"indent": 4})

    # Cleanup unused images and containers based on prune settings
    cleanup.perform_cleanup(client, dry_run)


if __name__ == "__main__":
    main()
