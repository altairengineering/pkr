# -*- coding: utf-8 -*-
# Copyright© 1986-2021 Altair Engineering Inc.

import sys
import os
import tempfile
import copy
from concurrent.futures import ProcessPoolExecutor

try:
    from python_on_whales import docker, DockerException
except:
    docker = None
    DockerException = None

from pkr.driver.docker import DockerDriver
from pkr.cli.log import write
from pkr.utils import merge
from pathlib import Path

BUILDKIT_ENV = {
    "env.BUILDKIT_STEP_LOG_MAX_SIZE": 1000000,
    "env.BUILDKIT_STEP_LOG_MAX_SPEED": 100000000,
}
BUILDX_OPTIONS = {
    "cache_to": {
        "type": "registry",
        "mode": "max",
    },
    "cache_from": {
        "type": "registry",
    },
    "progress": "plain",
}
BUILDX_BUILDER_NAME = "pkrbuilder"


class BuildxDriver(DockerDriver):
    """Driver using `docker buildx` subcommands (included in docker CE 19.03 and newer) to build images.
    Inherited from docker driver (for get_templates/pull/push/download/import/list)

    Buildx provides builkit features to the build and distributed cache
    mechanism (using registry as layer storage)
    """

    DOCKER_CONTEXT = "buildx"

    def __init__(self, kard, **kwargs):
        super().__init__(kard=kard, **kwargs)
        self.metas = {"tag": None, "buildx": ["cache_registry"]}
        self.buildkit_env = BUILDKIT_ENV
        self.buildx_options = BUILDX_OPTIONS

    def get_meta(self, extras, kard):
        values = super().get_meta(extras, kard)
        if "tag" in extras:
            extras["tag"] = str(values["tag"])

        # Get values from meta if defined
        self.buildkit_env.update(kard.meta.get("buildx", {}).get("buildkit_env", {}))
        self.builder_name = kard.meta.get("buildx", {}).get("builder_name", BUILDX_BUILDER_NAME)

        # Force cache_registry to be a sub-repo (saved in metafile)
        if extras["buildx"]["cache_registry"] == "None":
            extras["buildx"]["cache_registry"] = None
        if (
            extras["buildx"]["cache_registry"] is not None
            and "/" not in extras["buildx"]["cache_registry"]
        ):
            extras["buildx"]["cache_registry"] += "/cache"

        # Compute options
        builded_options = {
            "builder": self.builder_name,
            "cache_to": {
                "ref": extras["buildx"]["cache_registry"],
            },
            "cache_from": {
                "ref": extras["buildx"]["cache_registry"],
            },
        }
        self.buildx_options = kard.meta.get("buildx", {}).get("options", self.buildx_options)

        # Handle null cache_registry
        if extras["buildx"]["cache_registry"] is None:
            del builded_options["cache_from"]
            del builded_options["cache_to"]

        merge(builded_options, self.buildx_options, overwrite=False)

        return values

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
            with open("/dev/null", "a") as devnull:
                os.dup2(sys.stdout.fileno(), 3)
                os.dup2(devnull.fileno(), sys.stdout.fileno())
                try:
                    docker.buildx.build(self.kard.path, progress=False, builder=self.builder_name)
                except DockerException:
                    pass  # Build was never intended to success, just to force builder start
                os.dup2(3, sys.stdout.fileno())

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
        """
        if docker is None:
            # Handle python 3.6 here, to not impact child drivers
            raise Exception("buildx is not supported for python < 3.6")

        services = services or list(self.kard.env.get_container().keys())
        if rebuild_context:
            self.kard.make()

        buildx_meta = self.kard.meta.get("buildx", {})
        if "cache_registry_username" in buildx_meta and buildx_meta["cache_registry"] is not None:
            registry_url = buildx_meta["cache_registry"].split("/")[0]
            print(f"Logging to {registry_url}")
            docker.login(
                server=registry_url,
                username=buildx_meta.get("cache_registry_username", None),
                password=buildx_meta.get("cache_registry_password", None),
            )
        self._create_builder(purge=clean_builder)

        tag = tag or self.kard.meta["tag"]

        if parallel:
            if len(services) >= 1:
                write("Building docker images using {} threads ...\n".format(parallel))
            futures = []
            with ProcessPoolExecutor(max_workers=parallel) as executor:
                for service in services:
                    futures.append(
                        executor.submit(
                            *self._build_image(
                                service,
                                tag,
                                verbose,
                                logfile,
                                nocache,
                                no_rebuild,
                                True,
                            )
                        )
                    )
            for future in futures:
                future.result(timeout=1800)
        else:
            if len(services) >= 1:
                write("Building docker images...\n")
            for service in services:
                exec = self._build_image(
                    service, tag, verbose, logfile, nocache, no_rebuild, False
                )
                if exec is not None:
                    exec[0](*exec[1:])

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
          * no_rebuild: do not build if destination image exists
          * bufferize: keep log to print when ended
        """
        image_name = self.make_image_name(service, tag)

        dockerfile = self.kard.env.get_container(service).get("dockerfile")
        if not dockerfile:
            return

        if no_rebuild:
            image = len(self.docker.images(image_name)) == 1

        if not no_rebuild or image is False:
            context = self.kard.env.get_container(service).get("context", self.DOCKER_CONTEXT)
            self.buildx_options.update(
                {
                    "context_path": str(self.kard.path / context),
                    "file": str(Path(self.kard.path / context, dockerfile)),
                    "load": True,  # load to docker repository
                    "push": False,  # push to registry
                    "tags": image_name,
                }
            )

            # Handle args
            if nocache and "cache_from" in self.buildx_options:
                del self.buildx_options["cache_from"]

            return (
                self._do_build_image,
                copy.deepcopy(self.buildx_options),
                verbose,
                logfile,
                bufferize,
            )
        return None

    @staticmethod
    def _do_build_image(
        buildx_options,
        verbose=True,
        logfile=None,
        bufferize=None,
    ):
        """Method compatible with pickle to handle build
        with multiprocessing
        """
        # Handle log output
        if bufferize or logfile or not verbose:
            # Replace stdout/stderr by a file (for subprocess)
            # Equivalent of exec 3>&1 4>&2 1>$(mktemp) 2>&1
            if logfile:
                out_file = open(logfile, "a")
            else:
                out_file = tempfile.TemporaryFile()
            os.dup2(sys.stdout.fileno(), 3)
            os.dup2(sys.stderr.fileno(), 4)
            os.dup2(out_file.fileno(), sys.stdout.fileno())
            os.dup2(out_file.fileno(), sys.stderr.fileno())

        write("Building {} image...\n".format(buildx_options["tags"]))

        error = None
        try:
            docker.buildx.build(**buildx_options)
        except Exception as exc:
            error = exc
        finally:
            if bufferize:
                out_file.seek(0)
                buffer = out_file.read()
            if bufferize or logfile or not verbose:
                os.dup2(3, sys.stdout.fileno())
                os.dup2(4, sys.stderr.fileno())
                out_file.close()
            if bufferize:
                write(buffer.decode("utf-8"))

        if error is None:
            write("done.\n")
        else:
            raise error
