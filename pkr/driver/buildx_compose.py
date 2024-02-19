# Copyright© 1986-2024 Altair Engineering Inc.

"""pkr functions for managing containers lifecycle with buildx and compose"""

from .docker_compose import ComposePkr
from .buildx import BuildxDriver


# pylint: disable=abstract-method
class BuildxComposeDriver(ComposePkr, BuildxDriver):
    """Driver using `docker buildx` subcommands with compose"""

    def get_templates(self):
        return ComposePkr.get_templates(self)

    def build_images(self, *args, **kwargs):
        return BuildxDriver.build_images(self, *args, **kwargs)
