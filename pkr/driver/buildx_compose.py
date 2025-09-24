# Copyright© 1986-2024 Altair Engineering Inc.

"""pkr functions for managing containers lifecycle with buildx and compose"""

from __future__ import annotations

from .buildx import BuildxDriver
from .docker_compose import ComposePkr


# pylint: disable=abstract-method
class BuildxComposeDriver(ComposePkr, BuildxDriver):
    """Driver using `docker buildx` subcommands with compose"""

    def get_templates(self, phase: str | None = None):
        return ComposePkr.get_templates(self, phase)

    def build_images(self, *args, **kwargs):
        return BuildxDriver.build_images(self, *args, **kwargs)
