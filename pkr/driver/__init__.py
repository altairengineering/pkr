# -*- coding: utf-8 -*-
# Copyright© 1986-2018 Altair Engineering Inc.

"""pkr drivers"""

from importlib import import_module
import pkgutil
import os

DRIVER_MAPPING = {
    "compose": "docker_compose",
    "kubernetes": "k8s",
}


def load_driver(driver_name):
    """Return the loaded driver"""
    if driver_name in DRIVER_MAPPING:
        driver_name = DRIVER_MAPPING[driver_name]
    module = import_module(f"pkr.driver.{driver_name}", "pkr.driver")
    return module.Driver


def list_drivers():
    drivers_dir = os.path.dirname(os.path.realpath(__file__))
    return tuple(package_name for _, package_name, _ in pkgutil.iter_modules([drivers_dir]))
