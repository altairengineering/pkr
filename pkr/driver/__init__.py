# -*- coding: utf-8 -*-
# Copyright© 1986-2018 Altair Engineering Inc.

"""pkr drivers"""

from stevedore.driver import DriverManager


def load_driver(driver_name):
    """Return the loaded driver"""
    return DriverManager(namespace='drivers', name=driver_name).driver
