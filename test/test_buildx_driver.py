import sys
from .utils import pkrTestCase


class TestBuildxDriver(pkrTestCase):
    PKR = "pkr"
    pkr_folder = "docker_driver"
    kard_env = "dev"
    kard_driver = "buildx_compose"
    kard_extra = {
        "tag": "123",
        "flag": "flag_value",
        "buildx.cache_registry": "dummy",
        "buildx.builder_name": "testpkrbuilder",
    }

    def test_docker_driver_values(self):
        self.kard_extra["src_path"] = self.src_path
        self.generate_kard()
        self.make_kard()

        out_dir = self.pkr_path / "kard" / "test"
        expected = sorted(
            [
                out_dir / "buildx" / "folder2_dst" / "copy",
                out_dir / "buildx" / "file1" / "file2",
                out_dir / "buildx" / "file1.dockerfile",
                out_dir / "meta.yml",
            ]
        )

        def walk(path):
            for p in path.iterdir():
                if p.is_dir():
                    yield from walk(p)
                    continue
                yield p.resolve()

        self.assertEqual(sorted(list(walk(out_dir))), expected)

    def test_docker_multiple_contexts(self):
        self.kard_extra["src_path"] = self.src_path
        self.generate_kard(env="contexts")
        self.make_kard()

        out_dir = self.pkr_path / "kard" / "test"
        self.assertTrue((out_dir / "buildx" / "folder2_dst" / "copy").exists())
        self.assertTrue((out_dir / "context1" / "folder2_dst" / "copy").exists())

        self.assertTrue((out_dir / "buildx" / "file1.dockerfile").exists())
        self.assertTrue((out_dir / "context1" / "file1.dockerfile").exists())

        cmd = "{} image build -s container1 -c".format(self.PKR)
        prc = self._run_cmd(cmd)
        stdout = prc.stdout.read()
        stderr = prc.stderr.read()

        # Python 3.6
        if sys.version_info < (3, 7):
            self.assertEqual(stdout, b"", stdout)
            self.assertEqual(
                stderr, b"ERROR: (Exception) buildx is not supported for python < 3.6\n"
            )
            return

        expected = (
            b"Warning: No docker-compose file is provided with this environment.\n"
            b"Removing context1 ... Done !\n"
            b"Removing buildx ... Done !\n"
            b"Start buildx builder testpkrbuilder\n"
            b"Building docker images...\n\n"
            b"Building container1:123 image...\n\n"
        )
        self.assertTrue("unknown instruction: flag_value" in stderr.decode("utf-8"), stderr)
        self.assertEqual(stdout, expected, stdout)
        self.assertRegex(
            stderr.decode("utf-8"),
            r"docker buildx build --progress plain --builder testpkrbuilder --load "
            r"--file /tmp/.*/file1.dockerfile --cache-from type=registry,ref=dummy/cache "
            r"--cache-to type=registry,mode=max,ref=dummy/cache --tag container1:123 "
            r"/tmp/.*/context1",
        )
