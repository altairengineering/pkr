# -*- coding: utf-8 -*-
# Copyright© 1986-2020 Altair Engineering Inc.

"""pkr functions for creating the context"""

import sys
import os
import re
import traceback
import docker
import tenacity

from concurrent.futures import ThreadPoolExecutor

from collections import namedtuple
from pkr.driver import _USE_ENV_VAR
from pkr.driver.base import AbstractDriver
from pathlib import Path

from pkr.cli.log import write
from pkr.utils import PkrException

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


class DockerDriver(AbstractDriver):
    """Context object used to manipulate the context used to generate
    docker images
    """

    DOCKER_CONTEXT = "docker-context"
    DOCKER_CONTEXT_SOURCE = "dockerfiles"

    def __init__(self, kard, **kwargs):
        super().__init__(kard=kard, **kwargs)
        self.metas = {"tag": None}
        # Both of these options work with APIClient and from_env
        kwargs.setdefault("timeout", DOCKER_CLIENT_TIMEOUT)
        kwargs.setdefault("version", "auto")
        if _USE_ENV_VAR:
            self.docker = docker.from_env(**kwargs).api
        else:
            self.docker = docker.APIClient(**kwargs)

    def get_meta(self, extras, kard):
        values = super().get_meta(extras, kard)
        if "tag" in extras:
            extras["tag"] = str(values["tag"])
        return values

    def get_templates(self):
        """Use the environment information to return files and folder to template
        or copy to templated directory according to the 'requires' section of the
        containers description
        """
        templates = []
        templates_path = (
            self.kard.env.pkr_path / self.kard.env.template_dir / self.DOCKER_CONTEXT_SOURCE
        )

        # Process dockerfiles
        for container in self.kard.env.get_container():
            context = self.kard.env.get_container(container).get("context", self.DOCKER_CONTEXT)

            # Process requirements
            for src in self.kard.env.get_requires([container]):
                template = {
                    "source": src["origin"],
                    "origin": src["origin"],
                    "destination": src["dst"],
                    "subfolder": context,
                    "excluded_paths": src.get("exclude", []),
                    "gen_template": False,
                }
                if template not in templates:
                    # Dedup templates to avoid multi-copy
                    templates.append(template)

            try:
                dockerfile = self.kard.env.get_container(container)["dockerfile"]
            except KeyError:
                # In this case, we use an image provided by the hub
                continue

            # Automatically add dockerfile name matching folder to the context
            dockerfile = Path(dockerfile).stem
            templates.append(
                {
                    "source": templates_path / f"{dockerfile}*",  # Match template
                    "origin": templates_path,
                    "destination": "",
                    "subfolder": context,
                }
            )

        return templates

    def context_path(self, subpath, container):
        """Return absolute path for subpath relative to container context"""
        context = self.kard.env.get_container(container).get("context", self.DOCKER_CONTEXT)
        context_path = self.kard.real_path / context
        return context_path / subpath

    def get_registry(self, **kwargs):
        """Return a DockerRegistry instance with either the provided values, or
        those present in the meta.
        """
        for var in ("url", "username", "password"):
            if var not in kwargs and var in self.kard.meta:
                kwargs[var] = self.kard.meta[var]

        return DockerRegistry(**kwargs)

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
        """
        services = services or list(self.kard.env.get_container().keys())
        if rebuild_context:
            self.kard.make()

        tag = tag or self.kard.meta["tag"]

        with LogOutput(logfile) as logfh:
            if parallel:
                if len(services) > 1:
                    logfh.write("Building docker images using {} threads ...\n".format(parallel))
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
                            )
                        )
                for future in futures:
                    future.result(timeout=1800)
            else:
                if len(services) > 1:
                    logfh.write("Building docker images...\n")
                for service in services:
                    self._build_image(service, tag, verbose, logfile, nocache, no_rebuild, False)

    def _build_image(
        self,
        service,
        tag=None,
        verbose=True,
        logfile=None,
        nocache=False,
        no_rebuild=False,
        bufferize=None,
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
        """
        image_name = self.make_image_name(service, tag)

        with LogOutput(logfile, bufferize=bufferize) as logfh:
            dockerfile = self.kard.env.get_container(service).get("dockerfile")
            if not dockerfile:
                return

            logfh.write("Building {} image...\n".format(image_name))

            if no_rebuild:
                image = len(self.docker.images(image_name)) == 1

            if not no_rebuild or image is False:
                context = self.kard.env.get_container(service).get("context", self.DOCKER_CONTEXT)
                stream = self.docker.build(
                    path=str(self.kard.path / context),
                    dockerfile=str(Path(self.kard.path / context, dockerfile)),  # Relative Path
                    tag=image_name,
                    decode=True,
                    nocache=nocache,
                    forcerm=True,
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
        write("Logging to {}...".format(registry.url))
        self.docker.login(
            username=registry.username, password=registry.password, registry=registry.url
        )

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
            rep_tag = "{}/{}".format(registry.url, image_name)
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
                write("Pushing {} to {}:{}".format(image, rep_tag, dest_tag))
                sys.stdout.flush()

            try:
                self.docker.tag(image=image, repository=rep_tag, tag=dest_tag, force=True)

                ret = self.docker.push(repository=rep_tag, tag=dest_tag, decode=True, stream=True)

                error = ""
                for stream in ret:
                    if "error" in stream:
                        error += "\n" + stream["errorDetail"]["message"]

                if buffer:
                    write("Pushing {} to {}:{}".format(image, rep_tag, dest_tag))
                    sys.stdout.flush()
                write(" Done !")
            except docker.errors.APIError as error:
                error_msg = "\nError while pushing the image {}: {}\n".format(dest_tag, error)
                raise error

    def pull_images(
        self, services, registry, username, password, tag=None, parallel=None, **kwargs
    ):
        """Pull images from a remote registry

        Args:
          * services: the name of the images to pull
          * registry: a DockerRegistry instance
          * remote_tag: the tag of the version to pull
          * parallel: pull parallelism
        """
        services = services or list(self.kard.env.get_container().keys())
        remote_tag = tag or self.kard.meta["tag"]
        tag = self.kard.meta["tag"]

        registry = self.get_registry(url=registry, username=username, password=password)
        if registry.username is not None:
            self._logon_remote_registry(registry)

        todos = []
        for service in services:
            image_name = self.make_image_name(service)
            image = self.make_image_name(service, tag)
            todos.append((image, image_name))

        if parallel:
            futures = []
            with ThreadPoolExecutor(max_workers=parallel) as executor:
                for image, image_name in todos:
                    futures.append(
                        (
                            image,
                            executor.submit(
                                self._pull_image, image_name, registry.url, tag, remote_tag
                            ),
                        )
                    )
            for image, future in futures:
                future.result()
                write(
                    "Pulling {} from {}/{}:{}...".format(
                        image, registry.url, image_name, remote_tag
                    )
                )
                write(" Done !" + "\n")
                sys.stdout.flush()
        else:
            for image, image_name in todos:
                write(
                    "Pulling {} from {}/{}:{}...".format(
                        image, registry.url, image_name, remote_tag
                    )
                )
                sys.stdout.flush()
                self._pull_image(image_name, registry.url, tag, remote_tag)
                write(" Done !" + "\n")

        write("All images has been pulled successfully !" + "\n")

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
        write("Cleaning images destination {}".format(save_path))
        save_path.mkdir(exist_ok=True)
        for child in save_path.iterdir():
            child.unlink()

        if not nopull:
            self.pull_images(services, registry, username, password, tag=tag)

        for service in services:
            image_path = save_path / "{}.tar".format(service)
            image_name = self.make_image_name(service, tag)
            write("Saving {} to {}".format(image_name, image_path))
            sys.stdout.flush()

            with open(image_path, "wb") as f:
                for chunk in self.docker.get_image(image_name):
                    f.write(chunk)

            write(" Done !" + "\n")
        write("All images has been saved successfully !" + "\n")

    def import_images(self, services, tag=None, **kwargs):
        """Import images from kard to local docker

        Args:
          * services: the name of the images to load
          * tag: the tag of the version to load
        """
        services = services or list(self.kard.env.get_container().keys())
        tag = tag or self.kard.meta["tag"]

        save_path = Path(self.kard.path) / "images"
        for child in save_path.iterdir():
            service = child.name[:-4]
            if service not in services:
                continue
            write("Importing {} ...".format(child))
            with open(child, "rb") as f:
                rsp = self.docker.load_image(f.read())
            for message in rsp:
                write(message.get("stream", ""))
            write("\n")
        write("All images have been loaded successfully !" + "\n")

    @tenacity.retry(
        wait=tenacity.wait_fixed(1),
        stop=tenacity.stop_after_attempt(3),
        reraise=True,
        retry=tenacity.retry_if_exception_type(ImagePullError),
    )
    def _pull_image(self, image_name, registry_url, tag, remote_tag):
        """
        Pull one image, retry few times to be robust to registry or network
        related issues.
        Usually, if an attempt fails, the next one will succeed.

        Args:
          * image_name: the name of the image to pull
          * registry_url: the DockerRegistry instance url
          * tag: the tag of the version to pull
        """

        rep_tag = "{}/{}".format(registry_url, image_name)

        try:
            self.docker.pull(repository=rep_tag, tag=remote_tag)

            # Strip the repository tag
            self.docker.tag(
                image=":".join((rep_tag, remote_tag)), repository=image_name, tag=tag, force=True
            )

        except docker.errors.APIError as error:
            error_msg = "Error while pulling the image {}: {}".format(tag, error)
            write(error_msg)
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
                            "Error during docker process: " + last_log["errorDetail"]["message"]
                        )

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
            tag = "(?!{})$".format(except_tag)

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
                    except BaseException as exc:
                        write(exc)

    def list_images(self, services, tag, **kwargs):
        """List images"""
        services = services or list(self.kard.env.get_container().keys())
        if tag is None:
            tag = self.kard.meta["tag"]
        for service in services:
            write(self.make_image_name(service, tag))


class LogOutput(object):
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
            self.handler = open(self.filename, "a")
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
        self.handler.write("".join(self.buffer))
        self.handler.flush()
