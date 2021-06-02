# -*- coding: utf-8 -*-
# Copyright© 1986-2018 Altair Engineering Inc.

import unittest
from mock import call, patch

import os

from pkr.environment import Environment
import pkr.environment
from pkr.utils import PATH_ENV_VAR
import pkr.utils

from .utils import get_test_files_path


class TestEnvironment(unittest.TestCase):
    def setUp(self):
        self.env_path = get_test_files_path()
        os.environ[PATH_ENV_VAR] = str(self.env_path)
        pkr.utils.ENV_FOLDER = pkr.environment.ENV_FOLDER = "path2/env"

    def test_load_dev_environment(self):
        env = Environment("dev", features=["first", "second", "auto-volume"])

        expected_env = {
            "containers": {"backend": {"dockerfile": "backend.dockerfile"}},
            "default_features": ["auto-volume"],
            "default_meta": {
                "from": "env",
                "driver": {
                    "docker_compose": {"compose_file": "templates/docker-compose.yml.template"}
                },
            },
            "import": ["common/env"],
            "use_volume": True,
        }

        self.assertEqual(env.env, expected_env)
        self.assertEqual(env.features, ["first", "second", "auto-volume"])

    def test_load_prod_environment(self):
        self.maxDiff = None
        env = Environment("prod")

        expected_env = {
            "containers": {"backend": {"dockerfile": "backend.dockerfile"}},
            "default_features": ["auto-volume"],
            "default_meta": {
                "driver": {
                    "docker_compose": {"compose_file": "templates/docker-compose.yml.template"},
                    "k8s": {"k8s_files": ["templates/k8s.yml.template"]},
                    "name": "k8s",
                },
                "from": "import",
                "registry": False,
            },
            "import": ["common/env"],
            "use_volume": False,
        }

        self.assertEqual(env.env, expected_env)

    def test_load_required_meta_environment(self):
        env = Environment("required_meta")

        expected_env = {
            "containers": {"backend": {"dockerfile": "backend.dockerfile"}},
            "default_features": ["auto-volume"],
            "default_meta": {
                "driver": {
                    "docker_compose": {"compose_file": "templates/docker-compose.yml.template"}
                },
                "from": "import",
            },
            "import": ["common/env"],
            "required_meta": ["simple_meta", {"dict_meta": ["dict_meta_value"]}],
        }

        self.assertEqual(env.env, expected_env)

        metas = {
            "simple_meta": "simple_meta_value",
            "dict_meta/dict_meta_value": "dict_meta_value",
        }

        with patch("pkr.utils.ask_input", side_effect=metas.get) as std_mock:
            extra = {}
            values = env.get_meta(extra)

            for func_call in [call(m) for m in metas.keys()]:
                self.assertIn(func_call, std_mock.call_args_list)

        expected_values = {
            "driver": {
                "docker_compose": {"compose_file": "templates/docker-compose.yml.template"}
            },
            "features": ["auto-volume"],
            "from": "import",
        }
        self.assertEqual(values, expected_values)

        expected_extra = {
            "simple_meta": "simple_meta_value",
            "dict_meta": {"dict_meta_value": "dict_meta_value"},
        }
        self.assertEqual(extra, expected_extra)
