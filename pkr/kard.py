# -*- coding: utf-8 -*-
# Copyright© 1986-2018 Altair Engineering Inc.

"""pkr Kard"""

import os
import shutil

import yaml
from pathlib import Path
from builtins import object

from .context import Context
from .driver import load_driver
from .environment import Environment
from .ext import Extensions
from .cli.log import write
from .utils import PkrException, TemplateEngine, get_kard_root_path, merge, features_merge


class KardNotFound(PkrException):
    """Exception raised if the kard is not found"""

    pass


class Kard(object):
    """Object representing the kard"""

    META_FILE = "meta.yml"
    CURRENT_NAME = "current"
    LOCAL_SRC = "./src"
    CURRENT_KARD = None

    def __init__(self, name, path, meta=None):
        self.path = path
        self.name = name
        self.meta_file = path / self.META_FILE

        if meta is None:
            with self.meta_file.open() as meta_file:
                self.meta = yaml.safe_load(meta_file)
        else:
            self.meta = meta

        if self.meta["env"] is None:
            return

        self.env = Environment(env_name=self.meta["env"], features=self.meta["features"])

        if not Path(self.meta["src_path"]).is_absolute():
            self.meta["src_path"] = str((self.env.pkr_path / self.meta["src_path"]).resolve())

        self.driver = load_driver(self.meta["driver"]["name"])

        self.context = Context(self)

    @property
    def docker_cli(self):
        """Return the instance of docker client loaded"""
        return self.driver.get_docker_client(self)

    @property
    def extensions(self):
        """Return the Extension class loaded with the correct instance"""
        return Extensions(self.meta["features"])

    def save_meta(self):
        """Persist the kard to the meta file"""
        with self.meta_file.open("w") as meta_file:
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
    def list(cls, kubernetes=False):
        """Return a list of all kards"""
        try:
            kards = [p.name for p in get_kard_root_path().iterdir()]
        except OSError:
            return None
        try:
            kards.pop(kards.index(cls.CURRENT_NAME))
        except ValueError:
            pass

        if kubernetes:
            kards += load_driver("k8s").get_docker_client(None).list_kards()

        return kards

    @classmethod
    def create(cls, name, env, driver, features, meta, extra, **kwargs):
        """Factory method to create a new kard"""
        extras = {"features": []}
        if meta:
            extras.update(yaml.safe_load(meta))
        extras.update({a[0]: a[1] for a in [a.split("=", 1) for a in extra]})
        for feature in features_merge(extras["features"]):
            write("WARNING: Feature {} is duplicated in passed meta".format(feature))

        try:
            extra_features = features
            if extra_features is not None:
                extra_features = extra_features.split(",")
                for feature in features_merge(extra_features, extras["features"], False):
                    write("WARNING: Feature {} is duplicated in args".format(feature))
        except AttributeError:
            pass

        # Sanitize input metas
        for key, value in list(extras.items()):
            if isinstance(value, str) and value.lower() in ("true", "false"):
                extras[key] = value = value.lower() == "true"
            if "." in key:
                extras.pop(key)
                dict_it = extras
                sub_keys = key.split(".")
                for sub_key in sub_keys[:-1]:
                    dict_it = dict_it.setdefault(sub_key, {})
                dict_it[sub_keys[-1]] = value

        # Create the folder
        get_kard_root_path().mkdir(exist_ok=True)

        kard_path = cls._build_kard_path(name)
        kard_path.mkdir(exist_ok=True)

        try:
            features = extras.pop("features") if "features" in extras else []
            meta = {"env": env, "driver": {"name": driver}, "features": features}

            # If a path is provided, we take it. Otherwise, we use a src folder
            # in the kard folder.
            meta.update({"src_path": extras.pop("src_path", str(kard_path / cls.LOCAL_SRC))})

            kard = cls(name, kard_path, meta)

            if env is not None:
                cls.set_meta(kard, extras)
        except Exception:
            # If anything happened, we remove the folder
            shutil.rmtree(str(kard_path))
            raise

        Kard.set_current(kard.name)
        return kard

    @classmethod
    def _build_kard_path(cls, name):
        return get_kard_root_path() / name

    @classmethod
    def get_current(cls):
        """Return the current kard name"""
        current_kard_path = cls._build_kard_path(cls.CURRENT_NAME)
        name = current_kard_path.resolve().name
        return name

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
        if "/" in kard_name:
            driver, kard_name = kard_name.split("/")
            kard = cls.create(kard_name, None, driver, {})
            load_driver(driver).get_docker_client(kard).load_kard()
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
        write("Current kard is now: {}".format(kard_name))

    def update(self):
        """Update the kard"""
        self.set_meta(self, self.meta)

    @staticmethod
    def set_meta(kard, extra):
        """Set/update the meta"""
        merge(kard.env.get_meta(extra), kard.meta)
        merge(kard.driver.get_meta(extra, kard), kard.meta)

        # Extensions
        kard.extensions.setup(extra, kard)

        # We add all remaining extra to the meta
        merge(extra, kard.meta)

        kard.save_meta()

    def get_template_engine(self, extra_data=None):
        data = self.meta.copy()

        def read_kard_file(conf_file_name):
            conf_path = self.path / Path(conf_file_name).expanduser()
            return conf_path.read_text()

        def format_image(image_name):
            image = "{}:{}".format(image_name, self.meta["tag"])
            registry = self.meta.get("registry")
            if not registry:
                return image
            return "{}/{}".format(registry, image)

        data.update(
            {
                "env": self.env.env_name,
                "kard_file_content": read_kard_file,
                "format_image": format_image,
            }
        )

        # Get custom template data from extensions
        for custom_data in self.extensions.get_context_template_data():
            if custom_data:
                data.update(custom_data)

        if extra_data:
            data.update(extra_data)

        tpl_engine = TemplateEngine(data)

        return tpl_engine

    def build_images(
        self, services, tag, nocache, parallel, no_rebuild, rebuild_context, **kwargs
    ):
        """Build images"""
        if rebuild_context:
            self.make()

        services = services or list(self.env.get_container().keys())
        self.docker_cli.build_images(
            services,
            tag=tag,
            nocache=nocache,
            parallel=parallel,
            no_rebuild=no_rebuild,
        )

    def push_images(
        self, services, registry, username, password, tag, other_tags, parallel, **kwargs
    ):
        """Push images"""
        services = services or list(self.env.get_container().keys())
        registry = self.docker_cli.get_registry(url=registry, username=username, password=password)
        self.docker_cli.push_images(
            services, registry, tag=tag, other_tags=other_tags, parallel=parallel
        )

    def pull_images(self, services, registry, username, password, tag, parallel, **kwargs):
        """Pull images"""
        services = services or list(self.env.get_container().keys())
        registry = self.docker_cli.get_registry(url=registry, username=username, password=password)
        self.docker_cli.pull_images(services, registry, tag=tag, parallel=parallel)

    def download_images(self, **args):
        """Download images"""
        services = args.services or list(self.env.get_container().keys())
        registry = self.docker_cli.get_registry(
            url=args.registry, username=args.username, password=args.password
        )
        self.docker_cli.download_images(services, registry, tag=args.tag, nopull=args.nopull)

    def import_images(self, services, tag, **kwargs):
        services = services or list(self.env.get_container().keys())
        self.docker_cli.import_images(services, tag=tag)

    def list_images(self, services, tag, **kwargs):
        """List images"""
        services = services or list(self.env.get_container().keys())
        if tag is None:
            tag = self.meta["tag"]
        for service in services:
            write(self.docker_cli.make_image_name(service, tag))

    def purge_images(self, tag, except_tag, repository, **kwargs):
        """Purge images"""
        self.docker_cli.purge(except_tag, tag, repository)
