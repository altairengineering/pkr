from .utils import pkrTestCase
import re


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

        expected = (
            b"Removing context1 ... Done !\n"
            b"Removing docker-context ... Done !\n"
            b"Building container1:123 image...\n"
        )
        self.assertEqual(stdout, expected)
        expected = re.compile(b".*: unknown instruction: [Ff][Ll][Aa][Gg]_[Vv][Aa][Ll][Uu][Ee]")
        assert re.match(expected, stderr)
