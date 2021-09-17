# -*- coding: utf-8 -*-
# Copyright© 1986-2018 Altair Engineering Inc.

"""pkr drivers"""

from importlib import import_module
import pkgutil
import os

from .base import AbstractDriver

_USE_ENV_VAR = True

DRIVER_MAPPING = {
    "compose": "docker_compose",
    "kubernetes": "k8s",
}


def set_use_env_var(use_env_var=True):
    global _USE_ENV_VAR
    _USE_ENV_VAR = use_env_var


def _get_driver_class(module):
    for attr in dir(module):
        ext_cls = getattr(module, attr)
        try:
            if issubclass(ext_cls, AbstractDriver) and ext_cls is not AbstractDriver:
                return ext_cls
        except TypeError:
            pass


def load_driver(driver_name, kard=None, *args, **kwargs):
    """Return the loaded driver"""
    if driver_name in DRIVER_MAPPING:
        driver_name = DRIVER_MAPPING[driver_name]
    module = import_module(f"pkr.driver.{driver_name}", "pkr.driver")
    return _get_driver_class(module)(kard, *args, **kwargs)


def list_drivers():
    drivers_dir = os.path.dirname(os.path.realpath(__file__))
    return tuple(package_name for _, package_name, _ in pkgutil.iter_modules([drivers_dir]))
