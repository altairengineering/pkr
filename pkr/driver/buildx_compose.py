from .docker_compose import ComposePkr
from .buildx import BuildxDriver


class BuildxComposeDriver(ComposePkr, BuildxDriver):
    def get_templates(self):
        return ComposePkr.get_templates(self)

    def build_images(self, *args, **kwargs):
        return BuildxDriver.build_images(self, *args, **kwargs)
