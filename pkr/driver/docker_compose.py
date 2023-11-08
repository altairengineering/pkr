# -*- coding: utf-8 -*-
# Copyright© 1986-2018 Altair Engineering Inc.

"""pkr functions for managing containers lifecycle with compose"""

from builtins import next
import sys
import os
import re
import subprocess
import time
import traceback

from pathlib import Path
import yaml

from pkr.driver import docker
from pkr.cli.log import write, debug
from pkr.utils import (
    PkrException,
    PasswordException,
    merge,
    get_current_container,
    encrypt_swap,
    decrypt_swap,
    decrypt_file,
    encrypt_with_key,
    decrypt_with_key,
)


class ComposeConfig:
    """
    Replacement for compose.Config object.
    """

    def __init__(self, compose_config: dict):
        self.compose_config = compose_config
        self.services = [
            {"name": name, **service}
            for name, service in self.compose_config.get("services", {}).items()
        ]


class ComposePkr:
    """Implements pkr functions for docker-compose"""

    COMPOSE_BIN = "docker-compose"
    COMPOSE_FILE = "docker-compose.yml"
    COMPOSE_FILE_ENC = "docker-compose.enc"

    def __init__(self, kard, password=None, *args, **kwargs):
        super().__init__(kard, **kwargs)
        self.metas["project_name"] = None
        self._base_path = None
        self.password = password
        if self.kard is not None:
            self.compose_file = self.kard.path / self.COMPOSE_FILE
            self.compose_file_enc = self.kard.path / self.COMPOSE_FILE_ENC
            self.driver_meta = self.kard.meta.get("driver", {}).get("docker_compose", {})

    def get_meta(self, extras, kard):
        values = super().get_meta(extras, kard)
        # Retrieve the real_kard_path which is different if pkr run in container
        kard.meta["real_kard_path"] = str(self.get_real_kard_path())
        return values

    def _call_compose(self, *args):
        compose_cmd = [
            self.COMPOSE_BIN,
            "-f",
            "-",
            "-p",
            self.kard.meta["project_name"],
        ] + list(args)

        debug("driver: _call_compose: cmd={}".format(compose_cmd))
        compose = self._get_compose_data()
        return subprocess.run(compose_cmd, input=compose)

    def _get_compose_data(self):
        if self.compose_file.exists():
            with self.compose_file.open("rb") as cp_file:
                data = cp_file.read()
        elif self.compose_file_enc.exists():
            if not self.password:
                raise PasswordException()
            data = decrypt_file(self.compose_file_enc, self.password)
        else:
            raise PkrException("Neither docker compose yaml nor encrypted file found")
        return data

    def get_templates(self):
        templates = super().get_templates()

        # Cleanup merged file
        if self.compose_file.exists():
            self.compose_file.unlink()

        if "compose_file" not in self.driver_meta:
            write("Warning: No docker-compose file is provided with this environment.")
            return templates

        for file in [self.driver_meta["compose_file"]] + self.driver_meta.get(
            "compose_extension_files", []
        ):
            templates.append(
                {
                    "source": self.kard.env.pkr_path / file,
                    "origin": (self.kard.env.pkr_path / file).parent,
                    "destination": "",
                    "subfolder": "compose",
                }
            )

        return templates

    def populate_kard(self, meta_txt=True):
        """Populate context for compose"""
        if "compose_file" not in self.driver_meta:
            return
        merged_compose = {}
        compose_path = self.kard.path / "compose"
        for file in compose_path.iterdir():
            # Merge the compose_file
            merge(yaml.safe_load(file.open("r")), merged_compose)

        if meta_txt:
            with self.compose_file.open("w") as dcf:
                os.chmod(self.compose_file, 0o600)
                yaml.safe_dump(merged_compose, dcf, default_flow_style=False)
        else:
            if self.password is None:
                raise PasswordException()
            yaml_str = yaml.dump(merged_compose)
            with self.compose_file_enc.open("wb") as compose_file_enc:
                compose_enc = encrypt_with_key(
                    self.password.encode("utf-8"), yaml_str.encode("utf-8")
                )
                os.chmod(self.compose_file_enc, 0o600)
                compose_file_enc.write(compose_enc)

    def _load_compose_config(self, password=None):
        if self.compose_file_enc.exists():
            pw = self.password if self.password is not None else password
            if pw is None:
                raise PasswordException()
            with self.compose_file_enc.open("rb") as compose_file_enc:
                compose_enc = compose_file_enc.read()
                compose = decrypt_with_key(pw.encode("utf-8"), compose_enc)
                compose_data = yaml.load(compose, Loader=yaml.Loader)
        else:
            with self.compose_file.open("r") as cp_file:
                compose_data = yaml.safe_load(cp_file)
        return ComposeConfig(compose_data)

    def get_real_kard_path(self):
        """Get the matching host kard path if running in a container"""
        container = get_current_container()
        kard_path = str(self.kard.path)
        if container is None:
            return self.kard.path

        mount = None
        for c in container.attrs["Mounts"]:
            if kard_path.startswith(c["Destination"]):
                if mount is None or len(c["Destination"]) > len(mount["Destination"]):
                    mount = c

        if mount is not None:
            return Path(mount["Source"]) / self.kard.path.relative_to(mount["Destination"])
        else:
            return self.kard.path  # We are in container, but not a pkr one

    def _resolve_services(self, services=None):
        """Return a generator of actual services, or all if None is provided"""

        compose_config = self._load_compose_config()
        all_services = [c["name"] for c in compose_config.services]
        if services is None:
            return all_services

        # Resolve * regexp based service names
        for service in set(services):
            if "*" in service:
                reg = re.compile(service)
                services.extend([m for m in all_services if reg.match(m)])
                services.remove(service)

        # Remove unexisting services
        return set(services) & set(all_services)

    def start(self, services=None, yes=False):
        self._call_compose("up", "-d", *(services or ()))

    def cmd_up(self, services=None, verbose=False, build_log=None):
        """Start PCLM in a the docker environement.

        Use parameters stored in meta.yml to generate the
        docker-compose.yml file, and then up the container via docker-compose.

        If bare_metal support activated, configure the given host network
        interface and add an interface bridged on the host to all the
        containers that need to communicate with bare metal machines on
        the given network.
        """

        # Re-populating the context...
        self.kard.make()

        eff_modules = self._resolve_services(services)

        # This pattern is used to detect the remote image
        pattern = re.compile("^\S+\/\S+$")

        # Image names may be different from service names (e.g. image re-use)
        build_images = set(
            s["image"].partition(":")[0]  # without ":tag" suffix
            for s in self._load_compose_config().services
            if s["name"] in eff_modules and not pattern.match(s["image"])
        )

        # Revert the image name if possible
        image_pattern = self.kard.meta.get("image_pattern", self.SERVICE_VAR)
        if image_pattern:
            pattern_regex = image_pattern.replace(self.SERVICE_VAR, "(.*)")
            images_renamed = set()
            for image in build_images:
                match = re.search(pattern_regex, image)
                images_renamed.add(image if not match else match.group(1))
            build_images = images_renamed

        pull_images = []
        for s in self._load_compose_config().services:
            if s["name"] in eff_modules and pattern.match(s["image"]):
                image = s["image"].split("/")[1]
                registry = self.get_registry(
                    url=s["image"].split("/")[0], username=None, password=None
                )
                image_name = image.split(":")[0]
                remote_tag = image.split(":")[1]
                pull_images.append((image, image_name, registry, remote_tag))

        tag = self.kard.meta["tag"]

        if len(pull_images) != 0:
            self.pull_images(pull_images, tag=tag)
        if len(build_images) != 0:
            self.build_images(
                build_images, rebuild_context=False, verbose=verbose, logfile=build_log
            )

        self.start(services)

        # Do a nap while the containers are launching before calling
        # post_compose
        time.sleep(5)

        # Call post run handlers on extensions
        self.kard.extensions.post_up(eff_modules)

    def stop(self, services=None):
        """Stop the containers"""
        self._call_compose("stop", *(services or ()))

    def restart(self, services=None):
        """Restart containers"""
        self._call_compose("restart", *(services or ()))

    def get_container(self, container_name):
        """Get infos for a container"""
        containers = [
            container
            for container in self.docker.containers(filters={"name": container_name})
            if f"/{container_name}" in container["Names"]
        ]

        if len(containers) == 0:
            return None
        if len(containers) != 1:
            raise ValueError(
                'ERROR: {} containers named "{}"'.format(len(containers), container_name)
            )

        return self.docker.inspect_container(containers.pop().get("Id"))

    def get_ip(self, container):
        """Return the first IP of a container"""
        networks = container["NetworkSettings"]["Networks"]
        return next(iter(networks.values()))["IPAddress"]

    def get_status(self, container):
        """Return status of a container"""
        state = container["State"]["Status"]
        health = container["State"].get("Health", {}).get("Status")
        if health is None:
            if state == "running":
                return 0, "started"
            else:
                return 2, "stopped"
        elif health == "healthy":
            return 0, "started"
        else:
            if state == "running":
                return 1, "starting"
            else:
                return 2, "stopped"

    def cmd_ps(self):
        """List containers with ips"""
        services = self._load_compose_config().services

        for service in [s["name"] for s in services]:
            container = self.get_container(self.make_container_name(service))
            if container is None:
                container_ip = "stopped"
            else:
                container_ip = self.get_ip(container)
            write(" - {}: {}".format(service, container_ip))

    def cmd_status(self, password=None):
        """Check all containers are up and healthy"""
        services = self._load_compose_config(password).services
        status = []

        for service in services:
            service_name = service["name"]
            container = self.get_container(self.make_container_name(service_name))
            if container is None:
                if service.get("scale", 1) == 0:
                    # Ignore services that are not started by the `up` command (scale=0)
                    continue
                status.append(2)
                write(" - {}: {}".format(service_name, "stopped"))
            else:
                container_status = self.get_status(container)
                status.append(container_status[0])
                write(" - {}: {}".format(service_name, container_status[1]))
        if 1 in status:
            status = (1, "starting")
        elif 2 in status:
            status = (2, "down")
        else:
            status = (0, "started")
        write("Global status: {}".format(status[1]))
        sys.exit(status[0])

    def clean(self, kill=False):
        """Remove the containers and the build data file.
        If -w option set, also remove all environment files
        """
        if kill:
            self._call_compose("kill")
        self._call_compose("down", "-v")

    def execute(self, container_name, *args):
        """Execute a command on a container

        Args:
          * container_name: the name of the container
          * *args: the command, like 'ps', 'aux'
        """
        execution = self.docker.exec_create(container=container_name, cmd=args, tty=True)

        return self.docker.exec_start(exec_id=execution["Id"])

    def launch_container(self, command, image, volumes, v1=False, links=None):
        """Generic method to launch a container"""

        if v1:
            host_config = self.docker.create_host_config(
                binds=[":".join((v, k)) for k, v in volumes.items()],
                links={l: l for l in [self.make_container_name(s) for s in links]},
            )
            networking_config = None
        else:
            host_config = self.docker.create_host_config(
                binds=[":".join((v, k)) for k, v in volumes.items()]
            )
            network_name = self.kard.meta["project_name"] + "_default".format()
            networking_config = self.docker.create_networking_config(
                {network_name: self.docker.create_endpoint_config()}
            )

        container = self.docker.create_container(
            image=image,
            name=self.make_container_name("init"),
            command=command,
            host_config=host_config,
            networking_config=networking_config,
        )

        try:
            started = False
            ret = {"StatusCode": 1}
            attempt = 10
            container_id = container.get("Id")
            while started not in ("running", "exited"):
                self.docker.start(container=container_id)
                info = self.docker.inspect_container(container=container_id)
                started = info["State"]["Status"]

            while ret["StatusCode"] != 0 and attempt > 0:
                attempt -= 1
                time.sleep(3)
                ret = self.docker.wait(container=container_id)

            logs = self.docker.logs(container=container_id)
            write(logs)
        except:
            write(traceback.format_exc())
            raise
        finally:
            self.docker.remove_container(container=container_id)

        if ret["StatusCode"] != 0:
            raise PkrException("Container exited with non-zero status code {}".format(ret))

    def encrypt(self, password):
        encrypt_swap(self.compose_file, self.compose_file_enc, password)

    def decrypt(self, password):
        decrypt_swap(self.compose_file, self.compose_file_enc, password)


class ComposeDriver(ComposePkr, docker.DockerDriver):
    pass
