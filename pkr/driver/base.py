# -*- coding: utf-8 -*-
# Copyright© 1986-2018 Altair Engineering Inc.

import sys
import re
from builtins import object
from pathlib import Path

from ..utils import (
    merge,
    ensure_definition_matches,
)


class AbstractDriver(object):
    """Abstract class for a driver"""

    SERVICE_VAR = "%SERVICE%"

    def __init__(self, kard, **kwargs):
        """Save the kard to driver

        args and kwargs passed to driver
        """
        self.kard = kard

    def get_meta(self, extras, kard):
        """Ensure that the required meta are present.

        Args:
          * extras(dict): extra values
          * kard: the current kard
        """
        default = kard.env.get("default_meta", {}).copy()
        default.setdefault("project_name", re.sub(r"[^-_a-z0-9]", "", str(kard.path.name).lower()))
        merge(extras, default)

        values = ensure_definition_matches(definition=self.metas, defaults=default, data=kard.meta)
        merge(values, extras)
        return values

    def get_templates(self):
        """Return files or folders to be templated by pkr

        Format:
        [
            {
                "source": full_path,
                "origin": base_template_path (use to get relative path),
                "destination": relative_path,
                "subfolder": name of first level folder (driver specific),
                "excluded_paths": exclude those paths if source is a dir,
            }
            ...
        ]
        """
        raise NotImplementedError()

    def populate_kard(self):
        """Driver method executed after templating

        Might create some more files in kard_path, but must take care of cleaning it.
        """
        pass

    def context_path(self, sub_path, container):
        """AbstractDriver hook for driver to compute and return path
        relative to container name
        """
        raise NotImplementedError()

    #
    # Image related functions
    #
    def make_image_name(self, service, tag=None):
        """Return the image name formatted with the pattern in metas."""
        image_pattern = self.kard.meta.get("image_pattern", self.SERVICE_VAR)
        image_name = image_pattern.replace(self.SERVICE_VAR, service)
        if tag is not None:
            image_name = ":".join((image_name, tag))
        return image_name

    def build_images(self, *args, **kwargs):
        raise NotImplementedError()

    def push_images(self, *args, **kwargs):
        raise NotImplementedError()

    def push_images(self, *args, **kwargs):
        raise NotImplementedError()

    def download_images(self, *args, **kwargs):
        raise NotImplementedError()

    def import_images(self, *args, **kwargs):
        raise NotImplementedError()

    def list_images(self, *args, **kwargs):
        raise NotImplementedError()

    def purge_images(self, *args, **kwargs):
        raise NotImplementedError()

    #
    # Deploy related functions
    #
    def make_container_name(self, name):
        """Return the container name formatted with the pattern in metas."""
        container_pattern = self.kard.meta.get("container_pattern", self.SERVICE_VAR)
        return container_pattern.replace(self.SERVICE_VAR, name)

    def start(self, services, yes):
        """Starts services

        Args:
          * services: a list with the services name to start
        """
        raise NotImplementedError()

    def stop(self, services=None):
        """Starts services

        Args:
          * services: a list with the services name to start
        """
        raise NotImplementedError()

    def restart(self, services, yes):
        """Starts services

        Args:
          * services: a list with the services name to start
        """
        raise NotImplementedError()

    def execute(self, container_name, *args):
        """Execute a command on a container

        Args:
          * container_name: the name of the container
          * *args: the command, like 'ps', 'aux'
        """
        raise NotImplementedError()

    def cmd_up(self, services=None, verbose=False, build_log=None):
        raise NotImplementedError()

    def cmd_ps(self):
        """Hook for drivers to provide a listing process feature"""
        raise NotImplementedError()

    def cmd_status(self):
        """Hook for drivers to provide a check process feature"""
        raise NotImplementedError()

    def clean(self, kill=False):
        """Hook for drivers to provide a clean/stop process feature"""
        NotImplementedError()


class BaseDriver(AbstractDriver):
    metas = []

    def get_templates(self):
        templates = []
        templates_path = self.kard.env.pkr_path / self.kard.env.template_dir

        # Process templates
        for container in self.kard.env.get_container():
            for template in self.kard.env.get_container(container)["templates"]:
                templates.append(
                    {
                        "source": templates_path / template,
                        "origin": templates_path,
                        "destination": "",
                        "subfolder": "templated",
                    }
                )

        # Process requirements
        for src in self.kard.env.get_requires():
            templates.append(
                {
                    "source": src["origin"],
                    "origin": src["origin"],
                    "destination": src["dst"],
                    "subfolder": "templated",
                    "excluded_paths": src.get("exclude", []),
                    "gen_template": False,
                }
            )

        return templates
