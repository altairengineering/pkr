# Copyright© 1986-2025 Altair Engineering Inc.

import os
import unittest

import yaml
from mock import call, patch

from pkr.kard import Kard

from .utils import pkrTestCase


class TestKard(pkrTestCase):

    pkr_folder = "path1"

    def test_kard_dump(self):
        kard = Kard.create(
            name="test",
            env="dev",
            driver="docker",
            extra={"tag": 123},
            features="c,d,c",
            meta=(self.env_test.path / "meta1.yml").open(),
        )

        dump = yaml.safe_load(kard.dump())

        expected_dump = {
            "driver": {
                "name": "docker",
            },
            "env": "dev",
            "features": ["b", "a", "d", "c"],
            "tag": 123,
        }

        self.assertEqual(dump, expected_dump)


class TestKardWithInput(pkrTestCase):

    pkr_folder = "path2"

    def test_with_ask_input(self):

        metas = {
            "simple_meta": "simple_meta_value",
            "dict_meta/dict_meta_value": "dict_meta_value",
        }

        with patch("pkr.utils.ask_input", side_effect=metas.get) as std_mock:
            kard = Kard.create(
                name="test",
                env="required_meta",
                driver="docker",
                extra={"tag": 123},
                meta=(self.env_test.path / "meta1.yml").open(),
            )

        for func_call in [call(m) for m in metas.keys()]:
            self.assertIn(func_call, std_mock.call_args_list)

        expected_values = {
            "containers": {"backend": {"dockerfile": "backend.dockerfile"}},
            "default_meta": {
                "from": "import",
                "project_name": "test",
                "driver": {
                    "docker_compose": {
                        "compose_file": "templates/docker-compose.yml.template",
                        "compose_extension_files": ["templates/empty.yml.template"],
                    },
                    "name": "docker",
                },
                "features": ["auto-volume", "b", "a"],
                "tag": 123,
                "env": "required_meta",
                "simple_meta": "simple_meta_value",
                "dict_meta": {"dict_meta_value": "dict_meta_value"},
                "src_path": f"{ self.pkr_path }/kard/test/src",
            },
            "import": ["common/env"],
            "required_meta": ["simple_meta", {"dict_meta": ["dict_meta_value"]}],
            "default_features": ["auto-volume"],
        }
        self.assertEqual(kard.env.env, expected_values)
