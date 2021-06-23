from .utils import pkrTestCase


class TestBaseDriver(pkrTestCase):
    PKR = "pkr"
    pkr_folder = "base_driver"
    kard_env = "dev"
    kard_driver = "base"
    kard_extra = {"flag": "flag_value"}

    def test_base_driver_values(self):
        self.kard_extra["src_path"] = self.src_path
        self.generate_kard()
        self.make_kard()

        out_dir = self.pkr_path / "kard" / "test"
        expected = sorted(
            [
                out_dir / "templated" / "folder2_dst" / "copy",
                out_dir / "templated" / "folder1" / "file2",
                out_dir / "templated" / "file1",
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
