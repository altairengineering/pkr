# Copyright© 1986-2024 Altair Engineering Inc.

"""pkr functions for managing containers lifecycle with buildx and k8s"""

from __future__ import annotations

from .buildx import BuildxDriver
from .k8s import KubernetesPkr


# pylint: disable=abstract-method
class BuildxComposeDriver(KubernetesPkr, BuildxDriver):
    """Driver using `docker buildx` subcommands with k8s"""

    def get_templates(self, phase: str | None = None):
        return KubernetesPkr.get_templates(self, phase)

    def build_images(self, *args, **kwargs):
        return BuildxDriver.build_images(self, *args, **kwargs)
