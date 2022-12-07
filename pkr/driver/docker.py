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
from pkr.driver.docker_base import DockerBaseDriver, LogOutput
from pathlib import Path

from pkr.cli.log import write
from pkr.utils import PkrException


class DockerDriver(DockerBaseDriver):
    def get_templates(self):
        """Use the environment information to return files and folder to template
        or copy to templated directory according to the 'requires' section of the
        containers description
        """
        templates = super().get_templates()

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
            dockerfile = self.kard.env.get_container(service).get("dockerfile")
            if not dockerfile:
                return
            if not target:
                target = self.kard.env.get_container(service).get("target")

            logfh.write(
                "Building {}{} image...\n".format(
                    image_name, "({})".format(target) if target else ""
                )
            )

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
                    target=target,
                )

                self.print_docker_stream(
                    stream, verbose=verbose, logfile=logfile, bufferize=bufferize
                )

            logfh.write("done.\n")
