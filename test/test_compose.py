from unittest.mock import patch

from pkr.driver.docker_compose import ComposeDriver

from .utils import pkrTestCase


class TestDockerComposeDriver(pkrTestCase):
    PKR = "pkr"
    pkr_folder = "path4"
    kard_env = "dev"
    kard_driver = "compose"

    kard_extra = {"tag": "123"}

    def test_cmd_up(self):
        self.kard_extra["src_path"] = self.src_path
        self.generate_kard()

        with patch.object(ComposeDriver, "build_images", return_value=None) as mock_build:
            with patch.object(ComposeDriver, "start", return_value=None) as mock_start:
                self.up()

                mock_build.assert_called_once_with(
                    {"backend"}, rebuild_context=False, verbose=False, logfile=None
                )
                mock_start.assert_called_once()

    def test_cmd_up_with_image_pattern(self):
        self.kard_extra["src_path"] = self.src_path
        self.kard_extra["image_pattern"] = "prefix-%SERVICE%"
        self.generate_kard()

        with patch.object(ComposeDriver, "build_images", return_value=None) as mock_build:
            with patch.object(ComposeDriver, "start", return_value=None) as mock_start:
                self.up()

                mock_build.assert_called_once_with(
                    {"backend"}, rebuild_context=False, verbose=False, logfile=None
                )
                mock_start.assert_called_once()
