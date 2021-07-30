# -*- coding: utf-8 -*-
# Copyright© 1986-2018 Altair Engineering Inc.

"""Module with the pkr environment"""

import yaml
from builtins import object

from pkr.cli.log import write
from .utils import (
    HashableDict,
    ensure_definition_matches,
    get_pkr_path,
    merge,
    dedup_list,
    merge_lists,
)

ENV_FOLDER = "env"


class Environment(object):
    """Class for loading and holding pkr environment"""

    IMPORT_KEY = "import"
    DEFAULT_TEMPLATE_DIR = "templates"

    def __init__(self, env_name, features=None, path=None):
        self.env_name = env_name
        self.pkr_path = get_pkr_path()
        self.path = path or self.default_path

        # First load the main file to add eventual dependencies
        env_path = self.path / env_name
        env_file_path = env_path / "env.yml"

        self.env = self._load_env_file(env_file_path)

        self.features = features or []
        for feature in dedup_list(self.env.get("default_features", [])):
            write(
                "WARNING: Feature {} is duplicated in env {}".format(feature, env_name), error=True
            )
        merge_lists(self.env.get("default_features", []), self.features)

        for feature in self.features:
            f_path = env_path / (feature + ".yml")
            if f_path.is_file():
                content = self._load_env_file(f_path)
                feature_features = content.pop("default_features", [])
                for dup in dedup_list(feature_features):
                    write(
                        f"WARNING: Feature {dup} is duplicated in feature {feature} from env {env_name}",
                        error=True,
                    )
                merge_lists(feature_features, self.features)
                content["default_features"] = feature_features
                merge(content, self.env)

    def _load_env_file(self, path):
        """Load an environment with its dependencies recursively"""
        with path.open() as env_file:
            content = yaml.safe_load(env_file)
            if content is None:
                content = {}
            if "default_features" not in content:
                content["default_features"] = []

        for imp_name in content.get(self.IMPORT_KEY, ()):
            imp_path = self.path / (imp_name + ".yml")
            imp_data = self._load_env_file(imp_path)
            imp_data.pop(self.IMPORT_KEY, None)
            imp_features = imp_data.pop("default_features", [])
            for dup in dedup_list(imp_features):
                write(
                    f"WARNING: Feature {dup} is duplicated in import {imp_name} from env {self.env_name}",
                    error=True,
                )
            merge_lists(imp_features, content["default_features"])
            content = merge(content, imp_data)
        return content

    def get_meta(self, extra):
        """Ensure that all metadata are present"""
        default = self.env.get("default_meta")

        if "driver" in self.env:
            write(
                f"DEPRECATION: driver should be under default_meta in env {self.env_name}",
                error=True,
            )
            merge(self.env["driver"], default.setdefault("driver", {}), overwrite=False)

        if not default:  # This prevent an empty value in the YAML
            default = {}

        ret = default.copy()
        merge(extra, ret)

        required_values = ensure_definition_matches(
            definition=self.env.get("required_meta", []), defaults=ret, data=extra
        )
        merge(required_values, extra)

        # Feature
        ret["features"] = self.env.get("default_features", [])
        return ret

    @property
    def default_path(self):
        """Return the default path"""
        return self.pkr_path / ENV_FOLDER

    def _containers(self, template=False):
        """Method for fetching the containers dict as the schema might
        evolve.

        Args:
          - template: a bool specifying if templates should be returned
        """

        containers = self.env["containers"]

        if template:
            return containers

        if not containers:
            return {}

        return {
            name: value
            for name, value in containers.items()
            if value and not value.get("template", False)
        }

    @property
    def context_dir(self):
        """Return the context folder name"""
        return self.env["context_dir"]

    @property
    def template_dir(self):
        """Return the template folder name"""
        return self.env.get("template_dir", self.DEFAULT_TEMPLATE_DIR)

    def get_container(self, name=None):
        """Return a compiled dictionary representing a container, or a list of
        all if name is not specified.

        Args:
          - name: the name of the container to retrieve
        """
        if name is None:
            ret = {}
            for c_name, cont in self._containers().items():
                if not cont.get("template", False):
                    ret[c_name] = self.get_container(c_name)
            return ret

        container = self._containers(template=True)[name] or {}
        if "parent" in container and container["parent"] is not None:
            parent = self.get_container(container["parent"])
            return merge(container, parent.copy())

        return container

    def get_requires(self, containers=None):
        """Returns a list of required files for the provided containers.

        The result is returned as a list of dicts with 3 values: origin, src
        and dst.

        Args:
          - containers: a list of containers name
        """

        if containers is None:
            containers = list(self._containers().keys())

        requirements = {}
        # We first put them in a dict containing sets to avoid having doubles
        for name in containers:
            env = self.get_container(name)
            for key, value in env.get("requires", {}).items():
                dst_set = requirements.get(key, set())
                dst_set.add(HashableDict(value))
                requirements[key] = dst_set

        # then we transform it to a list of dicts
        ret = []
        for key, values in requirements.items():
            for value in values:
                item = {"origin": key}
                item.update(value)
                ret.append(item)

        return ret

    def __getitem__(self, item):
        return self.env.__getitem__(item)

    def get(self, item, default):
        try:
            return self.__getitem__(item)
        except KeyError:
            return default
