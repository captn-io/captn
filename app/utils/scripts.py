#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import os
import subprocess
import time
from typing import Dict, Optional, Tuple

from .config import config
from .common import parse_duration


def execute_pre_script(container_name: str, dry_run: bool = False) -> Tuple[bool, str]:
    """
    Execute the pre-update script for a container.

    This function executes the pre-update script associated with a specific container.
    Pre-scripts are executed before container updates and can perform tasks like
    backups, health checks, or other preparatory actions.

    Parameters:
        container_name (str): Name of the container to execute the script for
        dry_run (bool): If True, only log what would be done without actually executing

    Returns:
        Tuple[bool, str]: (success, output) - success indicates if script executed successfully,
                         output contains the script output or error message
    """
    return _execute_script("pre", container_name, dry_run)


def execute_post_script(container_name: str, dry_run: bool = False) -> Tuple[bool, str]:
    """
    Execute the post-update script for a container.

    This function executes the post-update script associated with a specific container.
    Post-scripts are executed after successful container updates and can perform
    tasks like health checks, notifications, or cleanup actions.

    Parameters:
        container_name (str): Name of the container to execute the script for
        dry_run (bool): If True, only log what would be done without actually executing

    Returns:
        Tuple[bool, str]: (success, output) - success indicates if script executed successfully,
                         output contains the script output or error message
    """
    return _execute_script("post", container_name, dry_run)


def _execute_script(script_type: str, container_name: str, dry_run: bool = False) -> Tuple[bool, str]:
    """
    Execute a script with timeout and logging.

    This internal function handles the actual execution of pre/post scripts with
    comprehensive error handling, timeout management, and logging integration.

    Parameters:
        script_type (str): Type of script ("pre" or "post")
        container_name (str): Name of the container
        dry_run (bool): If True, only log what would be done without actually executing

    Returns:
        Tuple[bool, str]: (success, output) - success indicates if script executed successfully,
                         output contains the script output or error message
    """
    script_config = _get_script_config(script_type)

    if not script_config.get("enabled", False):
        logging.debug(f"{script_type.capitalize()}-script execution is disabled", extra={"indent": 4})
        return True, "Script execution disabled"

    script_path = _get_script_path(script_type, container_name)
    if not script_path or not os.path.exists(script_path):
        logging.debug(f"No {script_type}-script found at '{script_path}'", extra={"indent": 4})
        return True, f"No {script_type}-script found"

    if dry_run:
        logging.info(f"Would execute {script_type}-script: '{script_path}'", extra={"indent": 4})
        return True, f"Would execute {script_type}-script (dry-run)"

    timeout_str = script_config.get("timeout", "5m")
    timeout = int(parse_duration(timeout_str, "s"))
    logging.info(f"Executing {script_type}-script: '{script_path}' (timeout: {timeout}s)", extra={"indent": 4})

    try:
        env_vars = _prepare_environment(container_name, script_type)
        result = _run_script_with_timeout(script_path, env_vars, timeout)

        if result["success"]:
            logging.info(f"{script_type.capitalize()}-script completed successfully", extra={"indent": 6})
        else:
            logging.error(f"{script_type.capitalize()}-script failed: {result['error']}", extra={"indent": 6})

        return result["success"], result["output"] or result["error"]

    except Exception as e:
        error_msg = f"Failed to execute {script_type}-script: {e}"
        logging.error(error_msg, extra={"indent": 6})
        return False, error_msg


def _get_script_config(script_type: str) -> Dict:
    """
    Get configuration for script execution.

    This function retrieves the configuration settings for a specific script type
    (pre or post) from the application configuration.

    Parameters:
        script_type (str): Type of script ("pre" or "post")

    Returns:
        Dict: Configuration dictionary containing script settings
    """
    config_key = f"{script_type}Scripts"
    if hasattr(config, config_key):
        config_section = getattr(config, config_key)
        result = {}
        if hasattr(config_section, '_values'):
            for key, value in config_section._values.items():
                result[key] = config_section.auto_cast(value)
        return result
    return {}


def _get_script_path(script_type: str, container_name: str) -> Optional[str]:
    """
    Get the path to the script for a container.

    This function determines the path to the script file for a specific container
    and script type. It first looks for container-specific scripts, then falls back
    to generic scripts.

    Parameters:
        script_type (str): Type of script ("pre" or "post")
        container_name (str): Name of the container

    Returns:
        Optional[str]: Path to the script file, or None if no script found
    """
    script_config = _get_script_config(script_type)
    scripts_dir = script_config.get("scriptsDirectory", "/app/conf/scripts")

    # Try container-specific script first
    container_script = os.path.join(scripts_dir, f"{container_name}_{script_type}.sh")
    if os.path.exists(container_script):
        return container_script

    # Try generic script
    generic_script = os.path.join(scripts_dir, f"{script_type}.sh")
    if os.path.exists(generic_script):
        return generic_script

    return None


def _prepare_environment(container_name: str, script_type: str) -> Dict[str, str]:
    """
    Prepare environment variables for script execution.

    This function creates a comprehensive environment for script execution by
    combining system environment variables with captn-specific variables.

    Parameters:
        container_name (str): Name of the container
        script_type (str): Type of script ("pre" or "post")

    Returns:
        Dict[str, str]: Environment variables dictionary for script execution
    """
    env = os.environ.copy()
    env.update({
        "CAPTN_CONTAINER_NAME": container_name,
        "CAPTN_SCRIPT_TYPE": script_type,
        "CAPTN_DRY_RUN": str(config.general.dryRun).lower(),
        "CAPTN_LOG_LEVEL": config.logging.level,
        "CAPTN_CONFIG_DIR": "/app/conf",
        "CAPTN_SCRIPTS_DIR": _get_script_config(script_type).get("scriptsDirectory", "/app/conf/scripts"),
    })
    return env


def _run_script_with_timeout(script_path: str, env_vars: Dict[str, str], timeout: int) -> Dict:
    """
    Run a script with timeout and capture output.

    This function executes a script with a specified timeout, capturing both
    stdout and stderr output. It handles timeout termination and provides
    comprehensive error reporting.

    Parameters:
        script_path (str): Path to the script file to execute
        env_vars (Dict[str, str]): Environment variables for script execution
        timeout (int): Timeout in seconds

    Returns:
        Dict: Dictionary containing success status, output, and error information
    """
    process = None

    try:
        os.chmod(script_path, 0o755)
        logging.info(f"Starting script: '{script_path}'", extra={"indent": 8})

        process = subprocess.Popen(
            [script_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env_vars,
            text=True,
            bufsize=1,
            universal_newlines=True
        )

        logging.info(f"Script process started with PID: {process.pid}", extra={"indent": 8})
        logging.info(f"Waiting for script completion (timeout: {timeout}s)...", extra={"indent": 8})

        stdout_lines = []
        start_time = time.time()

        # Simple approach: read output line by line until process completes
        while True:
            # Check timeout
            if time.time() - start_time > timeout:
                logging.error(f"Script execution timed out after {timeout} seconds", extra={"indent": 8})
                process.terminate()
                time.sleep(2)
                if process.poll() is None:
                    process.kill()
                return {
                    "success": False,
                    "output": '\n'.join(stdout_lines),
                    "error": f"Script execution timed out after {timeout} seconds"
                }

            # Try to read a line
            line = process.stdout.readline()

            if line:
                # Got output
                line = line.rstrip()
                stdout_lines.append(line)
                logging.info(f"| {line}", extra={"indent": 10})
            elif process.poll() is not None:
                # No more output and process is done
                break
            else:
                # No output but process still running, wait a bit
                time.sleep(0.1)

        stdout = '\n'.join(stdout_lines)
        logging.info(f"Script completed with return code: {process.returncode}", extra={"indent": 8})

        return {
            "success": process.returncode == 0,
            "output": stdout,
            "error": None if process.returncode == 0 else f"Script exited with code {process.returncode}"
        }

    except Exception as e:
        if process:
            try:
                process.terminate()
                time.sleep(2)
                if process.poll() is None:
                    process.kill()
            except Exception:
                pass

        return {
            "success": False,
            "output": "",
            "error": str(e)
        }


def should_continue_on_pre_failure() -> bool:
    """
    Check if the update process should continue if pre-script fails.

    This function determines whether the container update process should continue
    even if the pre-script fails, based on the configuration settings.

    Returns:
        bool: True if the update should continue despite pre-script failure, False otherwise
    """
    pre_config = _get_script_config("pre")
    return pre_config.get("continueOnFailure", False)


def should_rollback_on_post_failure() -> bool:
    """
    Check if the update process should rollback if post-script fails.

    This function determines whether the container should be rolled back to its
    previous state if the post-script fails, based on the configuration settings.

    Returns:
        bool: True if the container should be rolled back on post-script failure, False otherwise
    """
    post_config = _get_script_config("post")
    return post_config.get("rollbackOnFailure", True)