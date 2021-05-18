# -*- coding: utf-8 -*-
# Copyright© 1986-2018 Altair Engineering Inc.

"""
This module provide utilities to write tests
"""
from builtins import str
from builtins import object
import unittest
import tempfile
import os
import shutil
import sys

from pathlib import Path

from pkr.cli.parser import get_parser
from pkr import utils


class _EnvTest(object):
    """
    Allow you to enable/disable environment test where
    pkr dir is in temporary directory.
    """

    PKR_SRC = Path(__file__).absolute().parents[1]

    def __init__(self):
        self.tmp_kard = None
        self.original_pkr_path = utils.get_pkr_path()

    def enable(self):
        """
        Set PKR_PATH to created temporary directory and link
        `env` and `templates` directories to new env.
        """
        reload(sys.modules['pkr.kard'])
        reload(sys.modules['pkr.parser'])

        self.tmp_kard = Path(tempfile.mkdtemp())
        os.environ['PKR_PATH'] = str(self.tmp_kard)
        for dir_name in ('env', 'templates'):
            (self.tmp_kard / dir_name).symlink_to(self.PKR_SRC / dir_name)

    def disable(self):
        """
        Removes temporary directory and reset `PKR_PATH`
        """
        if self.original_pkr_path is not None:
            os.environ['PKR_PATH'] = self.original_pkr_path
        shutil.rmtree(str(self.tmp_kard))


class pkrTestCase(unittest.TestCase):
    """
    Class to test pkr extension or environment.

    To write test, subclass this class and define `kard_env` class attribute
    to an environment name.

    You can redefine in your subclasses the attributes:
        - kard_env (str): Name of environment
        - kard_driver (str): Name of driver
        - kard_features (List[str]): The list of features to enable
        - kard_extra (dict): default is {'tag': 'test'}

    This class provides attributes:
        - kard (Path): The path to the created kard directory.
        - src (Path): The path to the src directory.
    """

    kard_env = None
    kard_driver = 'none'
    kard_features = ()
    kard_extra = {'tag': 'test'}

    @classmethod
    def generate_kard(cls):
        """pkr kard create pkr-test ..."""

        if cls.kard_env is None:
            raise ValueError(
                '{} should define `kard_env` attribute'.format(cls))

        cmd_args = [
            'kard', 'create', 'pkr-test',
            '-d', cls.kard_driver,
            '-e', cls.kard_env
        ]

        if cls.kard_features:
            cmd_args.extend(
                ['--with', ','.join(cls.kard_features)]
            )

        cmd_args.extend(
            ('--extra', ' '.join('{}={}'.format(k, v)
                                 for k, v
                                 in list(cls.kard_extra.items())))
        )

        pkr_args = get_parser().parse_args(cmd_args)
        func = vars(pkr_args).pop('func')
        func(pkr_args)

        # set utilities variable.
        cls.kard = old_div(Path(utils.get_kard_root_path()), 'current')
        cls.src = old_div(cls.kard, 'src')

    @classmethod
    def regenerate_kard(cls):
        """pkr kard make"""
        cmd_args = [
            'kard', 'make'
        ]

        pkr_args = get_parser().parse_args(cmd_args)
        func = vars(pkr_args).pop('func')
        func(pkr_args)

    @classmethod
    def generate_src(cls):
        """
        This method should be owerwrite in order to create element in
        src directory.

        You can use `cls.src` Path object.
        """

    @classmethod
    def setUpClass(cls):
        """
        Create kard.
        """
        cls._env_test = _EnvTest()
        cls._env_test.enable()
        cls.generate_kard()
        cls.generate_src()
        cls.regenerate_kard()

    @classmethod
    def tearDownClass(cls):
        """
        Remove kard
        """
        cls._env_test.disable()

def get_test_files_path():
    return Path(os.path.dirname(os.path.abspath(__file__))) / 'files'
