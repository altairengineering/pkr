# -*- coding: utf-8 -*-
# Copyright© 1986-2018 Altair Engineering Inc.

"""pkr Kard"""

import os
import shutil

import yaml
from pathlib2 import Path
from builtins import object

from .context import Context
from .driver import load_driver
from .environment import Environment
from .ext import Extensions
from .utils import PkrException, TemplateEngine, get_kard_root_path, merge


class KardNotFound(PkrException):
    """Exception raised if the kard is not found"""
    pass


class Kard(object):
    """Object representing the kard"""

    META_FILE = 'meta.yml'
    CURRENT_NAME = 'current'
    LOCAL_SRC = './src'
    CURRENT_KARD = None

    def __init__(self, name, path, meta=None):
        self.path = path
        self.name = name

        if meta is None:
            with (path / self.META_FILE).open() as meta_file:
                self.meta = yaml.safe_load(meta_file)
        else:
            self.meta = meta

        self.env = Environment(
            env_name=self.meta['env'],
            features=self.meta['features'])

        if not Path(self.meta['src_path']).is_absolute():
            self.meta['src_path'] = str(
                (self.env.pkr_path / self.meta["src_path"]).resolve())

        self.driver = load_driver(self.meta['driver']['name'])

        self.context = Context(self)

    @property
    def docker_cli(self):
        """Return the instance of docker client loaded"""
        return self.driver.get_docker_client(self)

    @property
    def extensions(self):
        """Return the Extension class loaded with the correct instance"""
        return Extensions(self.meta['features'])

    def save_meta(self):
        """Persist the kard to the meta file"""
        with (self.path / self.META_FILE).open('w') as meta_file:
            yaml.safe_dump(self.meta, meta_file, default_flow_style=False)

    def make(self, reset=True):
        """Make the kard"""
        self.context.populate_context(reset)
        self.generate_configuration()
        self.extensions.populate_kard()
        self.docker_cli.populate_kard()

    def generate_configuration(self):
        """Generate configuration files for docker (outside the Docker context,
        as they will be integrated as volumes).

        Merges the file from the pclm directory, and merge them with the
        default
        in the default_config folder.
        """

    @classmethod
    def list(cls):
        """Return  a list of all kards"""
        try:
            kards = [p.name for p in get_kard_root_path().iterdir()]
        except OSError:
            return None
        try:
            kards.pop(kards.index(cls.CURRENT_NAME))
        except ValueError:
            pass
        return kards

    @classmethod
    def create(cls, kard_name, env_name, driver_name, extra):
        """Factory method to create a new kard"""
        # Create the folder
        get_kard_root_path().mkdir(exist_ok=True)

        kard_path = cls._build_kard_path(kard_name)
        kard_path.mkdir(exist_ok=True)

        try:
            features = extra.pop('features') if 'features' in extra else []
            meta = {'env': env_name,
                    'driver': {'name': driver_name},
                    'features': features}

            # PBS Cloud source code
            # If a path is provided, we take it. Otherwise, we use a src folder
            # in the kard folder.
            meta.update({'src_path': extra.pop(
                'src_path', str(kard_path / cls.LOCAL_SRC))})

            kard = cls(kard_name, kard_path, meta)

            cls.set_meta(kard, extra)

        except Exception:
            # If anything happened, we remove the folder
            shutil.rmtree(str(kard_path))
            raise

        return kard

    @classmethod
    def _build_kard_path(cls, name):
        return get_kard_root_path() / name

    @classmethod
    def get_current(cls):
        """Return the current kard name"""
        current_kard_path = cls._build_kard_path(cls.CURRENT_NAME)
        return current_kard_path.resolve().name

    @classmethod
    def load(cls, name):
        """Return a loaded context"""
        try:
            return cls(name, cls._build_kard_path(name))
        except IOError as ioe:
            raise KardNotFound('Kard "{}" not found: {}'.format(name, ioe))

    @classmethod
    def load_current(cls):
        """Load the last used kard"""
        if cls.CURRENT_KARD is None:
            cls.CURRENT_KARD = cls.load(cls.get_current())
        return cls.CURRENT_KARD

    @classmethod
    def set_current(cls, kard_name):
        """Set the current kard by making the symlink pointing to the correct
        folder.
        """
        dst_path = kard_name

        if not cls._build_kard_path(dst_path).exists():
            raise KardNotFound('Kard "{}" not found.'.format(kard_name))

        # Remove the link if it exists
        try:
            current_path = cls._build_kard_path(cls.CURRENT_NAME)
            os.unlink(str(current_path))
        except OSError:
            pass

        # Link the new context
        current_path.symlink_to(dst_path)

    def update(self):
        """Update the kard"""
        self.set_meta(self, self.meta)

    @staticmethod
    def set_meta(kard, extra):
        """Set/update the meta"""
        merge(kard.env.get_meta(extra), kard.meta)
        merge(kard.driver.get_meta(extra, kard), kard.meta)

        # Prevent duplication of features in case of update
        kard.meta['features'] = list(set(kard.meta['features']))

        # Extensions
        kard.extensions.setup(extra, kard)

        # We add all remaining extra to the meta
        merge(extra, kard.meta)
        kard.meta['features'] = list(set(kard.meta['features']))

        kard.save_meta()

    def get_template_engine(self, extra_data=None):

        data = self.meta.copy()
        data.update({'env': self.env.env_name})

        # Get custom template data from extensions
        for custom_data in self.extensions.get_context_template_data():
            if custom_data:
                data.update(custom_data)

        if extra_data:
            data.update(extra_data)

        tpl_engine = TemplateEngine(data)

        return tpl_engine
