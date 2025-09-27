# Copyright© 1986-2024 Altair Engineering Inc.

"""pkr functions for managing containers lifecycle with buildx"""

from __future__ import annotations

from contextlib import redirect_stdout, redirect_stderr
import copy
import io
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from python_on_whales import docker

from pkr.cli.log import write
from pkr.driver.docker import DockerDriver

BUILDKIT_ENV = {
    "env.BUILDKIT_STEP_LOG_MAX_SIZE": 1000000,
    "env.BUILDKIT_STEP_LOG_MAX_SPEED": 100000000,
}
BUILDX_BUILDER_NAME = "pkrbuilder"


# pylint: disable=abstract-method,too-many-instance-attributes
class BuildxDriver(DockerDriver):
    """Driver using `docker buildx` subcommands (included in docker CE 19.03 and newer) to build
    images. Inherited from docker driver (for get_templates/pull/push/download/import/list)

    Buildx provides builkit features to the build and distributed cache
    mechanism (using registry as layer storage)
    """

    DOCKER_CONTEXT = "contexts"

    def __init__(self, kard, **kwargs):
        super().__init__(kard=kard, **kwargs)
        self.metas = {"tag": None, "buildx": ["cache_registry"]}
        self.buildkit_env = BUILDKIT_ENV
        self.buildx_options = None
        self.platform = os.environ.get("DOCKER_DEFAULT_PLATFORM")
        self.builder_name = None
        self.registry_url = None
        self.registry_username = None
        self.registry_password = None

    def _load_conf(self):

        buildx_meta = self.kard.meta.get("buildx", {})

        if bk_env := buildx_meta.get("buildkit_env"):
            self.buildkit_env.update(bk_env)

        self.builder_name = buildx_meta.get("builder_name", BUILDX_BUILDER_NAME)

        self.buildx_options = {
            "builder": self.builder_name,
            "progress": "plain",
        }
        self.registry_url = buildx_meta.get("cache_registry")
        if self.registry_url:
            self.buildx_options.update(
                {
                    "cache_from": {
                        "ref": self.registry_url,
                        "type": "registry",
                    },
                }
            )
            if buildx_meta.get("push_cache", False):
                self.buildx_options.update(
                    {
                        "cache_to": {
                            "ref": self.registry_url,
                            "mode": "max",
                            "type": "registry",
                        },
                    }
                )
            self.registry_username = buildx_meta.get("cache_registry_username")
            self.registry_password = buildx_meta.get("cache_registry_password")

    def _create_builder(self, purge=False):
        """Create the buildkit builder, never to be purged"""
        for builder in docker.buildx.list():
            if builder.name == self.builder_name:
                if purge:
                    builder.remove()
                else:
                    break
        else:
            docker.buildx.create(name=self.builder_name, driver_options=self.buildkit_env)

        write(f"Start buildx builder {self.builder_name}")
        docker.buildx.inspect(x=self.builder_name, bootstrap=True)

    # pylint: disable=arguments-renamed,too-many-arguments,too-many-locals
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
        clean_builder=False,
        target=None,
        **kwargs,
    ):
        """Build docker images with buildx.

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

        self._load_conf()

        if self.registry_username:
            write(f"Logging to {self.registry_url}")
            docker.login(
                server=self.registry_url,
                username=self.registry_username,
                password=self.registry_password,
            )
        self._create_builder(purge=clean_builder)

        tag = tag or self.kard.meta["tag"]

        if parallel:
            if len(services) >= 1:
                write(f"Building docker images using {parallel} threads ...\n")
            futures = []
            with ThreadPoolExecutor(max_workers=parallel) as executor:
                for service in services:
                    if build_desc := self._build_image(
                        service,
                        tag,
                        verbose,
                        logfile,
                        nocache,
                        no_rebuild,
                        True,
                        target,
                    ):
                        futures.append(executor.submit(*build_desc))
            for future in futures:
                future.result(timeout=1800)
        else:
            if len(services) >= 1:
                write("Building docker images...\n")
            for service in services:
                execution = self._build_image(
                    service,
                    tag,
                    verbose,
                    logfile,
                    nocache,
                    no_rebuild,
                    False,
                    target,
                )
                if execution is not None:
                    execution[0](*execution[1:])

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
          * no_rebuild: do not build if destination image exists
          * bufferize: keep log to print when ended
          * target: name of the build-stage to build in a multi-stage Dockerfile
        """
        image_name = self.make_image_name(service, tag)
        container = self.kard.env.get_container(service)

        # Handle container format v1
        container_desc = container.get("build") or container

        target = target or container_desc.get("target")
        dockerfile = container_desc.get("dockerfile")
        context = container_desc.get("subfolder", container.get("context", self.DOCKER_CONTEXT))

        if not dockerfile:
            return None

        if not no_rebuild or len(self.docker.images(image_name)) != 1:

            buildx_options = copy.deepcopy(self.buildx_options)
            buildx_options.update(
                {
                    "context_path": str(self.kard.path / context),
                    "file": str(Path(self.kard.path / context, dockerfile)),
                    "load": True,  # load to docker repository
                    "push": False,  # push to registry
                    "tags": image_name,
                    "target": target,
                }
            )

            if self.platform is not None:
                buildx_options.update({"platforms": [self.platform]})

            if "cache_from" in buildx_options:
                buildx_options["cache_from"].update({"ref": f"{self.registry_url}/{service}"})
            if "cache_to" in buildx_options:
                buildx_options["cache_to"].update({"ref": f"{self.registry_url}/{service}"})

            # Handle args
            if nocache:
                buildx_options.pop("cache_from", None)
                buildx_options.pop("cache_to", None)

            return (
                self._do_build_image,
                copy.deepcopy(buildx_options),
                verbose,
                logfile,
                bufferize,
            )
        return None

    @staticmethod
    def _do_build_image(
        buildx_options, verbose=True, logfile=None, bufferize=None
    ):  # pylint: disable=too-many-branches
        out_buffer = None
        file_handle = None
        text_buffer = None

        if bufferize or logfile or not verbose:
            if logfile:
                # pylint: disable=consider-using-with
                file_handle = open(logfile, "a+", encoding="utf-8")  # a+ so we can read
                stdout = file_handle
                stderr = file_handle
            else:
                text_buffer = io.StringIO()
                stdout = text_buffer
                stderr = text_buffer
        else:
            stdout = None
            stderr = None

        target_name = f'({buildx_options["target"]})"' if buildx_options.get("target") else ""
        write(f'Building {buildx_options["tags"]}{target_name} image...\n')

        try:
            if stdout:
                with redirect_stdout(stdout), redirect_stderr(stderr):
                    docker.buildx.build(**buildx_options)
            else:
                docker.buildx.build(**buildx_options)
        except Exception:
            # Flush & rethrow
            if file_handle:
                file_handle.flush()
            raise
        finally:
            if text_buffer and bufferize:
                out_buffer = text_buffer.getvalue()
            elif file_handle and bufferize:
                file_handle.flush()
                file_handle.seek(0)
                out_buffer = file_handle.read()
            if file_handle:
                file_handle.close()

        if out_buffer:
            write(out_buffer)
        write("done.\n")
