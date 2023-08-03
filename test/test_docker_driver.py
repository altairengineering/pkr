import re

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
        expected = sorted(
            [
                out_dir / "docker-context" / "folder2_dst" / "copy",
                out_dir / "docker-context" / "file1" / "file2",
                out_dir / "docker-context" / "file1.dockerfile",
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
        self.assertTrue((out_dir / "docker-context" / "folder2_dst" / "copy").exists())
        self.assertTrue((out_dir / "context1" / "folder2_dst" / "copy").exists())

        self.assertTrue((out_dir / "docker-context" / "file1.dockerfile").exists())
        self.assertTrue((out_dir / "context1" / "file1.dockerfile").exists())

        cmd = "{} image build -s container1".format(self.PKR)
        prc = self._run_cmd(cmd)
        stdout = prc.stdout.read()
        stderr = prc.stderr.read()

        expected = b"Building container1:123 image...\n"
        self.assertEqual(stdout, expected)

        expected = re.compile(b".*: unknown instruction: [Ff][Ll][Aa][Gg]_[Vv][Aa][Ll][Uu][Ee]")
        assert re.match(expected, stderr)

        expected_err = "unknown instruction: flag_value"
        received_err = stderr.decode("utf-8")
        self.assertTrue(
            expected_err in received_err,
            "Did not find the string {} inside {}".format(expected_err, received_err),
        )


class TestDockerDriverV2(pkrTestCase):
    PKR = "pkr"
    pkr_folder = "container_format_v2"
    kard_env = "dev"
    kard_driver = "docker"
    kard_extra = {"tag": "123", "flag": "flag_value"}

    def test_kard_make_build_phase(self):
        self.kard_extra["src_path"] = self.src_path
        self.generate_kard()
        self.make_kard(["--phase", "build"])

        out_dir = self.pkr_path / "kard" / "test"
        expected = sorted(
            [
                out_dir / "contexts" / "container1" / "file1.dockerfile",
                out_dir / "contexts" / "container1" / "build.sh",
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

    def test_kard_make_run_phase(self):
        self.kard_extra["src_path"] = self.src_path
        self.generate_kard()
        self.make_kard(["--phase", "run"])

        out_dir = self.pkr_path / "kard" / "test"
        expected = sorted(
            [
                out_dir / "mounts" / "container1" / "run.sh",
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

    def test_kard_make_none_phase(self):
        self.kard_extra["src_path"] = self.src_path
        self.generate_kard()
        self.make_kard()

        out_dir = self.pkr_path / "kard" / "test"
        expected = sorted(
            [
                out_dir / "contexts" / "container1" / "file1.dockerfile",
                out_dir / "contexts" / "container1" / "build.sh",
                out_dir / "mounts" / "container1" / "run.sh",
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
