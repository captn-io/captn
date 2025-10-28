from . import docker


def get_client():
    """
    Get the Docker client instance.

    This function provides a unified interface to get the appropriate
    container engine client. Currently supports Docker engine.

    Returns:
        Docker client instance or None if connection fails
    """
    engine = "docker"

    if engine == "docker":
        return docker.get_client()


def get_containers(filters, client):
    """
    Get containers based on specified filters.

    This function retrieves containers from the container engine based on
    the provided filters (name, status, etc.).

    Parameters:
        filters: Container filters to apply
        client: Container engine client instance

    Returns:
        list: List of containers matching the filters
    """
    engine = "docker"

    if engine == "docker":
        return docker.get_containers(filters, client)


def get_local_image_metadata(image, container_inspect_data):
    """
    Get metadata for a local container image.

    This function extracts metadata from a local container image including
    registry information, image name, and tags.

    Parameters:
        image: Container image object
        container_inspect_data: Container inspection data

    Returns:
        dict: Image metadata including registry, name, and reference information
    """
    engine = "docker"

    if engine == "docker":
        return docker.get_local_image_metadata(image, container_inspect_data)


def pull_image(client, image_reference, dry_run):
    """
    Fetch a container image from the registry.

    This function downloads a container image from the registry to the local
    system for use in container updates.

    Parameters:
        client: Container engine client instance
        image_reference: Full image reference (e.g., "nginx:1.23.4")
        dry_run (bool): If True, only log what would be done without actually pulling

    Returns:
        Image object if successful, None otherwise
    """
    engine = "docker"

    if engine == "docker":
        return docker.pull_image(client, image_reference, dry_run)


def get_container_spec(client, container, container_inspect_data, image, image_inspect_data=None):
    """
    Get container specification for recreation.

    This function extracts the container configuration needed to recreate
    a container with the same settings but a new image.

    Parameters:
        client: Container engine client instance
        container: Container object
        container_inspect_data: Container inspection data
        image: New image object
        image_inspect_data: Image inspection data (optional)

    Returns:
        dict: Container specification for recreation
    """
    engine = "docker"

    if engine == "docker":
        return docker.get_container_spec(
            client, container, container_inspect_data, image, image_inspect_data
        )


def recreate_container(client, container, image, container_inspect_data, dry_run, image_inspect_data=None, notification_manager=None):
    """
    Recreate a container with a new image.

    This function stops the existing container, creates a backup, and starts
    a new container with the same configuration but using the new image.

    Parameters:
        client: Container engine client instance
        container: Original container object
        image: New image object
        container_inspect_data: Container inspection data
        dry_run (bool): If True, only log what would be done without actually recreating
        image_inspect_data: Image inspection data (optional)

    Returns:
        Container object if successful, None otherwise
    """
    engine = "docker"

    if engine == "docker":
        return docker.recreate_container(client, container, image, container_inspect_data, dry_run, image_inspect_data, notification_manager)


def is_self_container(container_name, container_id):
    """
    Check if a container is the self-update container.

    This function determines if the specified container is the captn
    application container itself, which requires special handling during updates.

    Parameters:
        container_name: Name of the container
        container_id: ID of the container

    Returns:
        bool: True if this is the self-update container, False otherwise
    """
    engine = "docker"

    if engine == "docker":
        return docker.is_self_container(container_name, container_id)
