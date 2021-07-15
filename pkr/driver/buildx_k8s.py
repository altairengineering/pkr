from .k8s import KubernetesPkr
from .buildx import BuildxDriver


class BuildxComposeDriver(KubernetesPkr, BuildxDriver):
    def get_templates(self):
        return KubernetesPkr.get_templates(self)

    def build_images(self, *args, **kwargs):
        return BuildxDriver.build_images(self, *args, **kwargs)
