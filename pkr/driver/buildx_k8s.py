# Copyright© 1986-2024 Altair Engineering Inc.

"""pkr functions for managing containers lifecycle with buildx and k8s"""

from .k8s import KubernetesPkr
from .buildx import BuildxDriver


# pylint: disable=abstract-method
class BuildxComposeDriver(KubernetesPkr, BuildxDriver):
    """Driver using `docker buildx` subcommands with k8s"""

    def get_templates(self):
        return KubernetesPkr.get_templates(self)

    def build_images(self, *args, **kwargs):
        return BuildxDriver.build_images(self, *args, **kwargs)
