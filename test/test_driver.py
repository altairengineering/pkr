import unittest
import yaml
from pkr import driver
from .utils import pkrTestCase


class TestDriver(unittest.TestCase):
    def test_list_drivers(self):
        self.assertEqual(
            driver.list_drivers(),
            ("base", "buildx", "buildx_compose", "buildx_k8s", "docker", "docker_compose", "k8s"),
        )

    def test_load_driver(self):
        self.assertTrue(
            repr(driver.load_driver("compose")).startswith(
                "<pkr.driver.docker_compose.ComposeDriver object"
            )
        )

    def test_load_driver_by_alias(self):
        self.assertTrue(
            repr(driver.load_driver("compose")).startswith(
                "<pkr.driver.docker_compose.ComposeDriver object"
            )
        )


class TestCompose(pkrTestCase):
    pkr_folder = "path3"
    kard_env = "dev"

    def test_expand_var(self):
        # Copy pkr_path (from requires)
        self.kard_extra["src_path"] = self.pkr_path
        self.generate_kard()
        self.make_kard()

        out_dir = self.pkr_path / "kard" / "test"
        self.assertTrue((out_dir / "docker-compose.yml").exists())

        # Check replacement of $SRC_PATH and $KARD_PATH in requires
        self.assertTrue((out_dir / "docker-context" / "copy" / "env").exists())
        self.assertFalse((out_dir / "docker-context" / "copy" / "kard" / "test").exists())
        self.assertTrue((out_dir / "docker-context" / "copied_meta.yml").exists())

        expected = [
            str(self.pkr_path / "kard" / "test" / "docker-context" / "test"),
            str(self.pkr_path / "test"),
            str(self.pkr_path / "kard" / "test" / "test"),
            str(self.pkr_path / "kard" / "test" / "data" / "test"),
            "container-test",
            "image-test",
        ]
        with open((out_dir / "docker-compose.yml"), "r") as f:
            dump = yaml.load(f, Loader=yaml.FullLoader)

        self.assertEqual(dump["paths"], expected)
