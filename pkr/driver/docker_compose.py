# -*- coding: utf-8 -*-
# Copyright© 1986-2018 Altair Engineering Inc.

"""pkr functions for managing containers lifecycle with compose"""

from builtins import next
import sys
import re
import subprocess
import time
import traceback

from compose import config as docker_config
import docker
from pathlib import Path
import yaml

from pkr.driver import docker
from pkr.cli.log import write
from pkr.utils import (
    PkrException,
    merge,
    get_current_container,
)


class ComposePkr:
    """Implements pkr functions for docker-compose"""

    COMPOSE_BIN = "docker-compose"
    COMPOSE_FILE = "docker-compose.yml"

    def __init__(self, kard, **kwargs):
        super().__init__(kard, **kwargs)
        self.metas["project_name"] = None
        self._base_path = None
        if self.kard is not None:
            self.compose_file = self.kard.path / self.COMPOSE_FILE
            self.driver_meta = self.kard.meta["driver"].get("docker_compose", {})

    def get_meta(self, extras, kard):
        values = super().get_meta(extras, kard)
        # Retrieve the real_kard_path which is different if pkr run in container
        kard.meta["real_kard_path"] = str(self.get_real_kard_path())
        return values

    def _call_compose(self, *args):
        compose_cmd = [
            self.COMPOSE_BIN,
            "-f",
            str(self.compose_file),
            "-p",
            self.kard.meta["project_name"],
        ] + list(args)
        subprocess.call(compose_cmd)

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

    def populate_kard(self):
        """Populate context for compose"""
        if "compose_file" not in self.driver_meta:
            return
        merged_compose = {}
        compose_path = self.kard.path / "compose"
        for file in compose_path.iterdir():
            # Merge the compose_file
            merge(yaml.safe_load(file.open("r")), merged_compose)

        with self.compose_file.open("w") as dcf:
            yaml.safe_dump(merged_compose, dcf, default_flow_style=False)

    def _load_compose_config(self):
        with self.compose_file.open("r") as cp_file:
            compose_data = yaml.safe_load(cp_file)

        return docker_config.load(
            docker_config.config.ConfigDetails(
                str(self.kard.path),
                [docker_config.config.ConfigFile(self.COMPOSE_FILE, compose_data)],
            )
        )

    def get_real_kard_path(self):
        """Get the matching host kard path if running in a container"""
        container = get_current_container()
        if container is None:
            return self.kard.path

        try:
            mount = next(
                (c for c in container.attrs["Mounts"] if c["Destination"] == str(self.kard.path))
            )
            return Path(mount["Source"])
        except StopIteration:
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

        # Image names may be different from service names (e.g. image re-use)
        images = set(
            s["image"].partition(":")[0]  # without ":tag" suffix
            for s in self._load_compose_config().services
            if s["name"] in eff_modules
        )

        self.build_images(images, rebuild_context=False, verbose=verbose, logfile=build_log)

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

    def cmd_status(self):
        """Check all containers are up and healthy"""
        services = self._load_compose_config().services
        status = []
        for service in [s["name"] for s in services]:
            container = self.get_container(self.make_container_name(service))
            if container is None:
                status.append(2)
                write(" - {}: {}".format(service, "stopped"))
            else:
                container_status = self.get_status(container)
                status.append(container_status[0])
                write(" - {}: {}".format(service, container_status[1]))
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
        If -w option set, also remove all environement files
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


class ComposeDriver(ComposePkr, docker.DockerDriver):
    pass
