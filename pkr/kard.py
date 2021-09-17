# -*- coding: utf-8 -*-
# Copyright© 1986-2018 Altair Engineering Inc.

"""pkr Kard"""

import shutil
import copy

import yaml
from pathlib import Path
from builtins import object

from .driver import load_driver
from .environment import Environment
from .ext import Extensions
from .cli.log import write
from .utils import (
    PkrException,
    TemplateEngine,
    get_kard_root_path,
    merge,
    diff,
    dedup_list,
    merge_lists,
)


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
                self.clean_meta = yaml.safe_load(meta_file)
        else:
            self.clean_meta = meta

        if self.clean_meta["env"] is None:
            return

        self.env = Environment(
            env_name=self.clean_meta["env"], features=self.clean_meta["features"].copy()
        )

        self._compute_meta(self.clean_meta)
        self.template_meta(self.meta)

        self.real_path = Path(self.meta.get("real_kard_path", self.path))

    @property
    def extensions(self):
        """Return the Extension class loaded with the correct instance"""
        return Extensions(self.meta["features"])

    def make(self, reset=True):
        """Make the kard"""
        templates = self.driver.get_templates()

        # Reset/create all subfolders
        subfolder_list = list(map(lambda a: a.get("subfolder"), templates))
        for subfolder in [i for n, i in enumerate(subfolder_list) if i not in subfolder_list[:n]]:
            # set(map(lambda a: a.get("subfolder"), templates)):
            folder = self.path / subfolder
            if reset:
                write(f"Removing {subfolder} ... ", add_return=False)
                if folder.exists():
                    shutil.rmtree(str(self.path / subfolder))
                    write("Done !")
                else:
                    write("Ok !")
            folder.mkdir(exist_ok=True)

        # Copy_file / templating
        tpl_engine = self.get_template_engine()
        for template in templates:
            source = Path(self.replace_var(str(template["source"])))
            origin = Path(self.replace_var(str(template["origin"])))
            tpl_engine.copy(
                path=source,
                origin=origin,
                local_dst=self.path / template["subfolder"] / template["destination"],
                excluded_paths=[self.replace_var(e) for e in template.get("excluded_paths", [])],
                gen_template=template.get("gen_template", True),
            )

        self.extensions.populate_kard()
        self.driver.populate_kard()

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
            kards += load_driver("k8s").list_kards()

        return kards

    @classmethod
    def create(cls, name, env, driver, extra, features=None, meta=None, **kwargs):
        """Factory method to create a new kard"""
        extras = {"features": []}
        if meta is not None:
            extras.update(yaml.safe_load(meta))
        extras.update(extra)
        for feature in dedup_list(extras["features"]):
            write("WARNING: Feature {} is duplicated in passed meta".format(feature), error=True)

        try:
            extra_features = features
            if extra_features is not None:
                extra_features = extra_features.split(",")
                for feature in dedup_list(extra_features):
                    write("WARNING: Feature {} is duplicated in args".format(feature), error=True)
                merge_lists(extra_features, extras["features"], insert=False)
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
            if driver is not None:
                extras.setdefault("driver", {})["name"] = driver
            extras["env"] = env
            # If a path is provided, we take it. Otherwise, we use a src folder
            # in the kard folder.
            src_path = extras.pop("src_path", None)
            if src_path is not None:
                extras.update({"src_path": src_path})

            kard = cls(name, kard_path, extras)

            if env is not None:
                kard.update()
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
            load_driver(driver, kard).load_kard()
        dst_path = kard_name

        if not cls._build_kard_path(dst_path).exists():
            raise KardNotFound('Kard "{}" not found.'.format(kard_name))

        # Remove the link if it exists
        try:
            current_path = cls._build_kard_path(cls.CURRENT_NAME)
            current_path.unlink()
        except OSError:
            pass

        # Link the new context
        current_path.symlink_to(dst_path)
        write("Current kard is now: {}".format(kard_name))

    def update(self):
        """Update the kard"""
        with self.meta_file.open("w") as meta_file:
            yaml.safe_dump(self.clean_meta, meta_file, default_flow_style=False)

    def dump(self, cleaned=True, **kwargs):
        """Dump overall templating context meta"""
        return yaml.safe_dump(self.clean_meta if cleaned else self.meta, default_flow_style=False)

    def _compute_meta(self, extra):
        """
        Compute meta

        Process:
         - Compute meta context (env + driver + kard specific)
         - Save meta for later diff
         - Call extensions `setup` which may alter meta
         - Diff what has been changed by extensions
         - Apply command line meta(s) on top
        """
        # Extract features to push them later (ensure precedence)
        features = extra.pop("features", [])

        # Copy extra to meta
        self.meta = copy.deepcopy(extra)

        # Add env to overall context in kard.meta
        merge(self.env.get_meta(extra), self.meta)  # Extra receiving ask_input values

        # Load driver an add it to overall context
        self.meta.setdefault("driver", {}).setdefault("name", "compose")  # Default value
        driver_args = self.meta.get("driver", {}).get("args", [])
        driver_kwargs = self.meta.get("driver", {}).get("kwargs", {})
        self.driver = load_driver(self.meta["driver"]["name"], self, *driver_args, **driver_kwargs)
        merge(self.driver.get_meta(extra, self), self.meta)  # Extra receiving ask_input values

        # Populate src_path before extension call
        self._process_src_path()

        # Copy overall context as diff base
        overall_context = copy.deepcopy(self.meta)

        # Extensions (give them a copy of extra, ext should not interact with it)
        self.extensions.setup(copy.deepcopy(extra), self)

        # Making a diff and apply it to extra without overwrite (we want cli to superseed extensions)
        merge(diff(overall_context, self.meta), extra, overwrite=False)

        # We add all remaining extra to the meta(s) (cli superseed all)
        merge(extra, self.meta)
        self._process_src_path()

        # Append features
        merge_lists(features, self.meta["features"], insert=False)
        extra["features"] = features

        return extra

    def _process_src_path(self):
        if "src_path" not in self.meta:
            self.meta["src_path"] = str(self.path / self.LOCAL_SRC)
        if not Path(self.meta["src_path"]).is_absolute():
            self.meta["src_path"] = str((self.env.pkr_path / self.meta["src_path"]).resolve())

    @classmethod
    def template_meta(cls, meta, context=None):
        context = context or meta
        tpl_engine = TemplateEngine(context)
        for key, value in meta.items():
            if isinstance(value, dict):
                cls.template_meta(value, context)
            elif isinstance(value, list):
                tmp = []
                for item in value:
                    if isinstance(item, str):
                        tmp.append(tpl_engine.process_string(item))
                    elif isinstance(item, dict):
                        tmp.append(cls.template_meta(item, context))
                meta[key] = tmp
            elif isinstance(value, str):
                meta[key] = tpl_engine.process_string(value)
                if meta[key].startswith("---\n"):
                    meta[key] = yaml.safe_load(meta[key])

        return meta

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

        def get_data_path(path):
            """Prefix the given path with the path to data volumes.

            Resolves a (Kard-relative or absolute) given data_path
            or goes with the default "<kard>/data"."""

            data_path = Path(self.meta.get("data_path", "data"))

            if data_path.is_absolute():
                return str(data_path / path)

            return str(self.real_path / data_path / path)

        data.update(
            {
                "env": self.env.env_name,
                "kard_file_content": read_kard_file,
                "format_image": format_image,
                "context_path": lambda p="", c=None: str(self.driver.context_path(p, c)),
                "kard_path": lambda p="": str(self.real_path / p),
                "src_path": lambda p="": str(Path(self.meta["src_path"]) / p),
                "make_container_name": self.driver.make_container_name,
                "make_image_name": lambda n, t=None: self.driver.make_image_name(n, t),
                "data_path": get_data_path,
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

    def replace_var(self, path):
        """Replace the Kard var if present, elsif return full path"""
        kard_path_var = "$KARD_PATH"
        src_path_var = "$SRC_PATH"
        if kard_path_var in path:
            return path.replace(kard_path_var, str(self.path))
        if src_path_var in path:
            return path.replace(src_path_var, self.meta["src_path"])
        return Path(self.env.pkr_path / path)
