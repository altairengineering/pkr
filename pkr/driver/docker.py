# Copyright© 1986-2024 Altair Engineering Inc.

"""pkr functions for creating the context"""

from __future__ import annotations

import os
import re
import sys
import traceback
from collections import namedtuple
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import docker
import tenacity

from pkr.cli.log import write
from pkr.driver import _USE_ENV_VAR
from pkr.driver.base import AbstractDriver
from pkr.utils import HashableDict, PkrException

DOCKER_SOCK = "unix://var/run/docker.sock"
DOCKER_CLIENT_TIMEOUT = int(os.environ.get("DOCKER_CLIENT_TIMEOUT", 300))


class ImagePullError(PkrException):
    """Raise when error occurs while pulling image"""


class DockerRegistry(namedtuple("DockerRegistry", ("url", "username", "password"))):
    """A Docker registry representation

    Args:
      * url: the URL of the registry
      * username: the username for authenticating on the registry
      * password: the password for authenticating on the registry
    """


# pylint: disable=abstract-method
class DockerDriver(AbstractDriver):
    """Context object used to manipulate the context used to generate
    docker images
    """

    DOCKER_CONTEXT = "docker-context"
    DOCKER_CONTEXT_SOURCE = "dockerfiles"

    def __init__(self, kard, password=None, **kwargs):
        super().__init__(kard=kard, password=password, **kwargs)
        self.metas = {"tag": None}
        # Both of these options work with APIClient and from_env
        kwargs.setdefault("timeout", DOCKER_CLIENT_TIMEOUT)
        kwargs.setdefault("version", "auto")
        if _USE_ENV_VAR:
            self.docker = docker.from_env(**kwargs).api
        else:
            self.docker = docker.APIClient(**kwargs)
        self.platform = os.environ.get("DOCKER_DEFAULT_PLATFORM")

    def get_meta(self, extras, kard):
        values = super().get_meta(extras, kard)
        if "tag" in extras:
            extras["tag"] = str(values["tag"])
        return values

    # pylint: disable= too-many-locals
    def get_templates(self, phase: str | None = None):
        """Use the environment information to return files and folder to template
        or copy to templated directory according to the 'requires' sections of the
        containers description
        """
        templates = set()
        templates_path = (
            self.kard.env.pkr_path / self.kard.env.template_dir / self.DOCKER_CONTEXT_SOURCE
        )

        # Process dockerfiles
        for container_name, container in self.kard.env.get_container().items():
            # pkr v2 mode
            build_cfg = container.get("build")
            run_cfg = container.get("run")
            if build_cfg and (phase in ("build", None)):
                # First populate the build config
                try:
                    subfolder = build_cfg["subfolder"]
                except KeyError as exc:
                    raise PkrException(
                        f"Container '{container_name}' is missing a 'build' subfolder"
                    ) from exc
                for req in build_cfg.get("requires", []):
                    templates.add(
                        HashableDict(
                            {
                                "source": req["src"],
                                "origin": req["src"],
                                "destination": req["dst"],
                                "subfolder": subfolder,
                                "excluded_paths": req.get("exclude", []),
                                "gen_template": req.get("template", True),
                            }
                        )
                    )

                dockerfile = build_cfg.get("dockerfile")
                if dockerfile:
                    # We add 2 potential templates, one with '.template' suffix, one without
                    # This could be optimized with regex, because glob would include too many files
                    for tpl in (True, False):
                        templates.add(
                            HashableDict(
                                {
                                    "source": str(
                                        templates_path
                                        / f"{dockerfile}{'.template' if tpl else ''}"
                                    ),
                                    "origin": str(templates_path),
                                    "destination": "",
                                    "subfolder": subfolder,
                                    "gen_template": tpl,
                                }
                            )
                        )

            if run_cfg and (phase in ("run", None)):
                # Then deal with the run config
                try:
                    subfolder = run_cfg["subfolder"]
                except KeyError as exc:
                    raise PkrException(
                        f"Container '{container_name}' is missing a 'run' subfolder"
                    ) from exc

                for req in run_cfg.get("requires", []):
                    templates.add(
                        HashableDict(
                            {
                                "source": req["src"],
                                "origin": req["src"],
                                "destination": req["dst"],
                                "subfolder": subfolder,
                                "excluded_paths": req.get("exclude", []),
                                "gen_template": req.get("template", True),
                            }
                        )
                    )

            # Legacy format
            if build_cfg is run_cfg is None:
                context = container.get("context", self.DOCKER_CONTEXT)

                # Process requirements
                for src in self.kard.env.get_requires([container_name]):
                    template = {
                        "source": src["origin"],
                        "origin": src["origin"],
                        "destination": src["dst"],
                        "subfolder": context,
                        "excluded_paths": src.get("exclude", []),
                        "gen_template": False,
                    }
                    templates.add(HashableDict(template))

                try:
                    dockerfile = container["dockerfile"]
                except KeyError:
                    # In this case, we use an image provided by the hub
                    continue

                # Automatically add dockerfile name matching folder to the context
                dockerfile = Path(dockerfile).stem
                templates.add(
                    HashableDict(
                        {
                            "source": str(templates_path / f"{dockerfile}"),  # Match template
                            "origin": str(templates_path),
                            "destination": "",
                            "subfolder": context,
                        }
                    )
                )

                # Also add anything matching dockerfile name stem with an extension
                # suffix of some kind
                templates.add(
                    HashableDict(
                        {
                            "source": str(templates_path / f"{dockerfile}.*"),  # Match template
                            "origin": str(templates_path),
                            "destination": "",
                            "subfolder": context,
                        }
                    )
                )

        return list(templates)

    def context_path(self, sub_path, container):
        """Return absolute path for sub_path relative to container context"""
        ctn = self.kard.env.get_container(container)
        context = ctn.get("build", {}).get("subfolder") or ctn.get("context", self.DOCKER_CONTEXT)

        context_path = self.kard.real_path / context
        return context_path / sub_path

    def mount_path(self, sub_path, container):
        """Return absolute path for sub_path relative to container mount path"""
        ctn = self.kard.env.get_container(container)
        subfolder = ctn.get("run", {}).get("subfolder") or ctn.get("context", self.DOCKER_CONTEXT)

        context_path = self.kard.real_path / subfolder
        return context_path / sub_path

    def get_registry(self, **kwargs):
        """Return a DockerRegistry instance with either the provided values, or
        those present in the meta.
        """
        for var in ("url", "username", "password"):
            if var not in kwargs and var in self.kard.meta:
                kwargs[var] = self.kard.meta[var]

        return DockerRegistry(**kwargs)

    # pylint: disable=arguments-differ,too-many-arguments,too-many-locals
    def build_images(
        self,
        services,
        rebuild_context,
        tag=None,
        verbose=True,
        logfile=None,
        nocache=False,
        parallel=None,
        no_rebuild=False,
        target=None,
        **kwargs,
    ):
        """Build docker images.

        Args:
          * services: the name of the images to build
          * tag: the tag on which the image will be saved
          * verbose: verbose logs
          * logfile: separate log file for the underlying build
          * nocache: disable docker cache
          * parallel: (int|None) Number of concurrent build
          * no_rebuild: do not build if destination image exists
          * target: name of the build-stage to build in a multi-stage Dockerfile
        """
        services = services or list(self.kard.env.get_container().keys())
        if rebuild_context:
            self.kard.make()

        tag = tag or self.kard.meta["tag"]

        with LogOutput(logfile) as logfh:
            if parallel:
                if len(services) > 1:
                    logfh.write(f"Building docker images using {parallel} threads ...\n")
                futures = []
                with ThreadPoolExecutor(max_workers=parallel) as executor:
                    for service in services:
                        futures.append(
                            executor.submit(
                                self._build_image,
                                service,
                                tag,
                                verbose,
                                logfile,
                                nocache,
                                no_rebuild,
                                True,
                                target,
                            )
                        )
                for future in futures:
                    future.result(timeout=1800)
            else:
                if len(services) > 1:
                    logfh.write("Building docker images...\n")
                for service in services:
                    self._build_image(
                        service, tag, verbose, logfile, nocache, no_rebuild, False, target
                    )

    # pylint: disable=too-many-arguments
    def _build_image(
        self,
        service,
        tag=None,
        verbose=True,
        logfile=None,
        nocache=False,
        no_rebuild=False,
        bufferize=None,
        target=None,
    ):
        """Build docker image.

        Args:
          * service: service to build
          * tag: the tag on which the image will be saved
          * verbose: verbose logs
          * logfile: separate log file for the underlying build
          * nocache: disable docker cache
          * parallel: (int|None) Number of concurrent build
          * no_rebuild: do not build if destination image exists
          * target: name of the build-stage to build in a multi-stage Dockerfile
        """
        image_name = self.make_image_name(service, tag)

        with LogOutput(logfile, bufferize=bufferize) as logfh:
            container = self.kard.env.get_container(service)
            if not (dockerfile := container.get("build", {}).get("dockerfile")):
                dockerfile = container.get("dockerfile")

            if not dockerfile:
                return

            if not target:
                if not (target := container.get("build", {}).get("target")):
                    target = container.get("target")

            logfh.write(f"Building {image_name}{f'({target})' if target else ''} image...\n")

            if not no_rebuild or len(self.docker.images(image_name)) != 1:
                if not (context := container.get("build", {}).get("subfolder")):
                    context = container.get("context", self.DOCKER_CONTEXT)
                stream = self.docker.build(
                    path=str(self.kard.path / context),
                    dockerfile=str(Path(self.kard.path / context, dockerfile)),  # Relative Path
                    tag=image_name,
                    decode=True,
                    nocache=nocache,
                    forcerm=True,
                    target=target,
                    platform=self.platform,
                )

                self.print_docker_stream(
                    stream, verbose=verbose, logfile=logfile, bufferize=bufferize
                )

            logfh.write("done.\n")

    def _logon_remote_registry(self, registry):
        """Push images to a remote registry

        Args:
          * registry: a DockerRegistry instance
        """
        if registry.username is None:
            return
        write(f"Logging to {registry.url}...")
        self.docker.login(
            username=registry.username, password=registry.password, registry=registry.url
        )

    # pylint: disable=arguments-differ,too-many-arguments,too-many-locals
    def push_images(
        self,
        services,
        registry,
        username,
        password,
        tag=None,
        other_tags=None,
        parallel=None,
        **kwargs,
    ):
        """Push images to a remote registry

        Args:
          * services: the name of the images to push
          * registry: a DockerRegistry instance
          * tag: the tag of the version to push
          * parallel: push parallelism
        """
        services = services or list(self.kard.env.get_container().keys())
        tag = tag or self.kard.meta["tag"]

        registry = self.get_registry(url=registry, username=username, password=password)
        if registry.username is not None:
            self._logon_remote_registry(registry)

        tags = [tag]
        tags.extend(other_tags)

        todos = []
        for service in services:
            image_name = self.make_image_name(service)
            image = self.make_image_name(service, tag)
            rep_tag = f"{registry.url}/{image_name}"
            todos.append((image, rep_tag, tags))

        if parallel:
            futures = []
            with ThreadPoolExecutor(max_workers=parallel) as executor:
                for todo in todos:
                    futures.append(executor.submit(self._push_image, *todo, buffer=True))
            for future in futures:
                future.result()
        else:
            for todo in todos:
                self._push_image(*todo)

    def _push_image(self, image, rep_tag, tags, buffer=False):
        """Push image to a remote registry

        Args:
          * image: the name of the image to push
          * rep_tag: distant image name
          * tags: list of tags to push to
        """
        for dest_tag in tags:
            if not buffer:
                write(f"Pushing {image} to {rep_tag}:{dest_tag}")
                sys.stdout.flush()

            try:
                self.docker.tag(image=image, repository=rep_tag, tag=dest_tag, force=True)

                ret = self.docker.push(repository=rep_tag, tag=dest_tag, decode=True, stream=True)

                error = ""
                for stream in ret:
                    if "error" in stream:
                        error += "\n" + stream["errorDetail"]["message"]

                if buffer:
                    write(f"Pushing {image} to {rep_tag}:{dest_tag}")
                    sys.stdout.flush()
                write(" Done !")
            except docker.errors.APIError as error:
                raise error

    def logon_remote_registry(self, registry, username=None, password=None):
        """Login to a remote registry

        Args:
          * registry: a DockerRegistry instance
          * username: username
          * password: password
        """
        registry = self.get_registry(url=registry, username=username, password=password)
        self._logon_remote_registry(registry)

    # pylint: disable=too-many-arguments,too-many-locals
    def pull_images(
        self,
        services,
        registry=None,
        username=None,
        password=None,
        tag=None,
        parallel=None,
        ignore_errors=False,
        **_,
    ):
        """Pull images from a remote registry

        Args:
          * services: the name of the images to pull
          * registry: a docker registry url
          * tag: the tag of the version to pull
          * parallel: pull parallelism
        """
        if registry is not None:
            services = services or list(self.kard.env.get_container().keys())
            remote_tag = tag or self.kard.meta["tag"]
            tag = self.kard.meta["tag"]

            docker_registry = self.get_registry(url=registry, username=username, password=password)
            self._logon_remote_registry(docker_registry)

            todos = []
            for service in services:
                image_name = self.make_image_name(service)
                image = self.make_image_name(service, tag)
                todos.append((image, image_name, docker_registry, remote_tag))
        else:
            todos = services
        if parallel:
            futures = []
            with ThreadPoolExecutor(max_workers=parallel) as executor:
                for image, image_name, reg, remote_tag in todos:
                    futures.append(
                        (
                            image,
                            executor.submit(
                                self._pull_image,
                                image_name,
                                reg.url,
                                tag,
                                remote_tag,
                                ignore_errors,
                            ),
                            image_name,
                            remote_tag,
                        )
                    )
            for image, future, image_name, remote_tag in futures:
                future.result()
                write(f"Pulling {image} from {registry.url}/{image_name}:{remote_tag}...")
                write(" Done !\n")
                sys.stdout.flush()
        else:
            for image, image_name, reg, remote_tag in todos:
                write(f"Pulling {image} from {reg.url}/{image_name}:{remote_tag}...")
                sys.stdout.flush()
                self._pull_image(image_name, reg.url, tag, remote_tag, ignore_errors)
                write(" Done !\n")

        write("All images have been pulled successfully !\n")

    def download_images(
        self, services, registry, username, password, tag=None, nopull=False, **kwargs
    ):
        """Download images from a remote registry and save to kard

        Args:
          * services: the name of the images to download
          * registry: a DockerRegistry instance
          * tag: the tag of the version to download
        """
        services = services or list(self.kard.env.get_container().keys())
        tag = tag or self.kard.meta["tag"]

        save_path = Path(self.kard.path) / "images"
        write(f"Cleaning images destination {save_path}")
        save_path.mkdir(exist_ok=True)
        for child in save_path.iterdir():
            child.unlink()

        if not nopull:
            self.pull_images(services, registry, username, password, tag=tag)

        for service in services:
            image_path = save_path / f"{service}.tar"
            image_name = self.make_image_name(service, tag)
            write(f"Saving {image_name} to {image_path}")
            sys.stdout.flush()

            with open(image_path, "wb") as f:
                for chunk in self.docker.get_image(image_name):
                    f.write(chunk)

            write(" Done !\n")
        write("All images have been saved successfully !\n")

    def import_images(self, services, **_):
        """Import images from kard to local docker

        Args:
          * services: the name of the images to load
          * tag: the tag of the version to load
        """
        services = services or list(self.kard.env.get_container().keys())

        save_path = Path(self.kard.path) / "images"
        for child in save_path.iterdir():
            service = child.name[:-4]
            if service not in services:
                continue
            write(f"Importing {child} ...")
            with open(child, "rb") as f:
                rsp = self.docker.load_image(f.read())
            for message in rsp:
                write(message.get("stream", ""))
            write("\n")
        write("All images have been loaded successfully !\n")

    @tenacity.retry(
        wait=tenacity.wait_fixed(1),
        stop=tenacity.stop_after_attempt(3),
        reraise=True,
        retry=tenacity.retry_if_exception_type(ImagePullError),
    )
    def _pull_image(self, image_name, registry_url, tag, remote_tag, ignore_errors):
        """
        Pull one image, retry few times to be robust to registry or network
        related issues.
        Usually, if an attempt fails, the next one will succeed.

        Args:
          * image_name: the name of the image to pull
          * registry_url: the DockerRegistry instance url
          * tag: the tag of the version to pull
        """

        rep_tag = f"{registry_url}/{image_name}"

        try:
            # Check whether we already have the image locally, using the full
            # image name (repo/image:tag format). Don't pull try to pull images
            # if we already have them because it can take a non-negligible
            # amount of time.
            full_image_name = self.make_image_name(rep_tag, tag=remote_tag)
            if len(self.docker.images(full_image_name)) != 1:
                self.docker.pull(repository=rep_tag, tag=remote_tag)

            # Strip the repository tag
            self.docker.tag(
                image=":".join((rep_tag, remote_tag)), repository=image_name, tag=tag, force=True
            )

        except docker.errors.APIError as error:
            error_msg = f"Error while pulling the image {tag}: {error}"
            write(error_msg)
            if not ignore_errors:
                # pylint: disable=raise-missing-from
                raise ImagePullError(error_msg)

    @staticmethod
    def print_docker_stream(stream, verbose=True, logfile=None, bufferize=False):
        """Util method to print docker logs"""
        with LogOutput(logfile, bufferize=bufferize) as logfh:
            log_keys = set(("status", "stream"))
            all_logs = []
            last_log_id = [None]

            def print_log(log):
                for key in log_keys & set(log):
                    try:
                        if key == "status" and log.get(key) in ("Downloading", "Extracting"):
                            status_id = log.get("id")

                            if last_log_id[0] is None:
                                last_log_id[0] = status_id
                            if last_log_id[0] != status_id:
                                last_log_id[0] = status_id
                                logfh.writeln(log["progress"])
                            else:
                                logfh.write_console(log["progress"] + "\r")
                        else:
                            logfh.write_console("\n")
                            logfh.writeln(log.get(key))
                    except:
                        write(traceback.format_exc())
                        raise

            for log in stream:
                last_logs = []
                if log is None:
                    continue

                if isinstance(log, list):
                    last_logs.extend(log)
                    all_logs.extend(log)
                else:
                    last_logs.append(log)
                    all_logs.append(log)

                for last_log in last_logs:
                    if verbose:
                        print_log(last_log)

                    # Catch errors
                    if "error" in last_log:
                        for log_it in all_logs:
                            print_log(log_it)
                        raise Exception(
                            f"Error during docker process: {last_log['errorDetail']['message']}"
                        )

    def encrypt(self, password=None):
        """Hook for drivers to provide a kard encrypt feature"""
        raise NotImplementedError()

    def decrypt(self, password=None):
        """Hook for drivers to provide a kard decrypt feature"""
        raise NotImplementedError()

    def purge_images(self, tag=None, except_tag=None, repository=None, **kwargs):
        """Delete all images of this project.

        Only tag or except_tag can be specified simultaneously.

        Args:
          * except_tag: delete all image but this tag
          * tag: only delete this tag
          * repository: delete image reference in a specified repository
        """
        services = list(self.kard.env.get_container().keys())
        if except_tag is None:
            tag = tag or self.kard.meta["tag"]
        else:
            tag = f"(?!{except_tag})$"

        images_to_del = [self.make_image_name(s, tag) for s in services]

        if repository:
            tmp = []
            for image in images_to_del:
                tmp.append(image)
                tmp.append("/".join((repository, image)))
            images_to_del = tmp

        images_regex = "(" + ")|(".join(images_to_del) + ")"

        for img in self.docker.images():
            for repo_tag in img.get("RepoTags", []):
                if re.match(images_regex, repo_tag):
                    write("Deleting image " + repo_tag)
                    try:
                        self.docker.remove_image(repo_tag)
                    # pylint: disable=broad-exception-caught
                    except BaseException as exc:
                        write(exc)

    def list_images(self, services, tag, **kwargs):
        """List images"""
        services = services or list(self.kard.env.get_container().keys())
        if tag is None:
            tag = self.kard.meta["tag"]
        for service in services:
            write(self.make_image_name(service, tag))


class LogOutput:
    """Manage printing docker logs"""

    def __init__(self, filename=None, bufferize=False):
        """Context manager for writing to files or to stdout."""
        if filename is None:
            self.handler = sys.stdout
        else:
            self.handler = None
            self.filename = filename
        self.buffer = []
        self.bufferize = bufferize

    def __enter__(self):
        if self.handler != sys.stdout:
            self.handler = open(self.filename, "a", encoding="utf-8")
        return self

    def __exit__(self, *_):
        self.flush()
        if self.handler != sys.stdout:
            self.handler.close()
            self.handler = None

    def write(self, line):
        """Write a string to the configured output."""
        if self.bufferize:
            self.buffer.append(line)
            return
        print(line, file=self.handler, end="")
        self.handler.flush()

    def writeln(self, line):
        """Write a string followed by a newline to the configured output."""
        if self.bufferize:
            self.buffer.append(line + "\n")
            return
        print(line, file=self.handler)
        self.handler.flush()

    def write_console(self, line):
        """Write the string only when it's connected to a console."""
        if self.handler != sys.stdout:
            return
        if self.bufferize:
            self.buffer.append(line)
            return
        print(line, file=self.handler, end="")

    def flush(self):
        """Flush the handler"""
        self.handler.write("".join(self.buffer))
        self.handler.flush()
