from . import docker


def get_client():
    engine = "docker"

    if engine == "docker":
        return docker.get_client()


def get_containers(filters, client):
    engine = "docker"

    if engine == "docker":
        return docker.get_containers(filters, client)


def get_local_image_metadata(image, container_inspect_data):
    engine = "docker"

    if engine == "docker":
        return docker.get_local_image_metadata(image, container_inspect_data)


def pull_image(client, image_reference, dry_run):
    engine = "docker"

    if engine == "docker":
        return docker.pull_image(client, image_reference, dry_run)


def get_container_spec(client, container, container_inspect_data, image):
    engine = "docker"

    if engine == "docker":
        return docker.get_container_spec(
            client, container, container_inspect_data, image
        )


def recreate_container(client, container, image, spec, dry_run):
    engine = "docker"

    if engine == "docker":
        return docker.recreate_container(client, container, image, spec, dry_run)


def is_self_container(container_name, container_id):
    engine = "docker"

    if engine == "docker":
        return docker.is_self_container(container_name, container_id)
