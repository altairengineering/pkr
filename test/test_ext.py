from pkr.kard import Kard
from .utils import pkrTestCase


class TestExt(pkrTestCase):
    pkr_folder = "ext"

    def test_kard_features_order_is_deterministic(self):
        res = []
        for i in range(3):
            with open(str(self.env_test.path / "meta1.yml"), "r") as f:
                kard = Kard.create(
                    name="test", env="test", driver="compose", features="a,b", extra={}, meta=f
                )
            res.append((kard.meta["features"], kard.extensions.extensions))
            self.assertEqual(repr(res[-1]), repr(res[0]))
        self.assertEqual(res[0][0], ["auto-volume", "a", "ext_mock", "b"])

    def test_ext_loaded_from_pkr_path(self):
        with open(str(self.env_test.path / "meta1.yml"), "r") as f:
            kard = Kard.create(
                name="test", env="test", driver="compose", features="a,b", extra={}, meta=f
            )
        self.assertIn("ext_mock", kard.extensions.extensions)
        self.assertIn({"test": "Ok"}, kard.extensions.get_context_template_data())

    def test_ext_loaded_from_entrypoints_group_pkr_extensions(self):
        with open(str(self.env_test.path / "meta1.yml"), "r") as f:
            kard = Kard.create(
                name="test", env="test", driver="compose", features="a,b", extra={}, meta=f
            )
        self.assertIn("auto-volume", kard.extensions.extensions)
        self.assertIn("use_volume", kard.extensions.get_context_template_data()[0])
