# Copyright© 1986-2024 Altair Engineering Inc.

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
    """Activate the usage of environment variable for Docker"""
    # pylint: disable=global-statement
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
    return None


def load_driver(driver_name, kard=None, password=None, **kwargs):
    """Return the loaded driver"""
    driver_name = DRIVER_MAPPING.get(driver_name, driver_name)
    module = import_module(f"pkr.driver.{driver_name}", "pkr.driver")
    return _get_driver_class(module)(kard, password, **kwargs)


def list_drivers() -> tuple:
    """Return a list of drivers"""
    drivers_dir = os.path.dirname(os.path.realpath(__file__))
    return tuple(package_name for _, package_name, _ in pkgutil.iter_modules([drivers_dir]))
