from .utils import pkrTestCase


class TestDockerDriver(pkrTestCase):
    PKR = "pkr"
    pkr_folder = "docker_driver"
    kard_env = "dev"
    kard_driver = "docker"
    kard_extra = {"tag": "123", "flag": "flag_value"}

    def test_docker_driver_values(self):
        self.kard_extra["src_path"] = self.src_path
        self.generate_kard()
        self.make_kard()

        out_dir = self.pkr_path / "kard" / "test"
        expected = [
            out_dir / "docker-context" / "folder2_dst" / "copy",
            out_dir / "docker-context" / "file1" / "file2",
            out_dir / "docker-context" / "file1.dockerfile",
            out_dir / "meta.yml",
        ]

        def walk(path):
            for p in path.iterdir():
                if p.is_dir():
                    yield from walk(p)
                    continue
                yield p.resolve()

        self.assertEqual(list(walk(out_dir)), expected)
