# -*- coding: utf-8 -*-
# Copyright© 1986-2018 Altair Engineering Inc.

import unittest

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
        pkr.utils.ENV_FOLDER = pkr.environment.ENV_FOLDER = 'env2'

    def test_load_dev_environment(self):
        env = Environment('dev')

        expected_env = {
            'containers': {'backend': {'dockerfile': 'backend.dockerfile'}},
            'default_features': ['auto-volume'],
            'driver': {
                'docker_compose': {
                    'compose_file': 'templates/docker-compose.yml.template'}},
            'import': ['common/env'],
            'use_volume': True
        }

        self.assertEqual(env.env, expected_env)

    def test_load_prod_environment(self):
        env = Environment('prod')

        expected_env = {
            'containers': {'backend': {'dockerfile': 'backend.dockerfile'}},
            'default_features': ['auto-volume'],
            'driver': {
                'docker_compose': {
                    'compose_file': 'templates/docker-compose.yml.template'}},
            'import': ['common/env'],
            'use_volume': False
        }

        self.assertEqual(env.env, expected_env)
