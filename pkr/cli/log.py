# -*- coding: utf-8 -*-
# Copyright© 1986-2018 Altair Engineering Inc.

import sys

_DEBUG = False


def set_debug(debug=False):
    global _DEBUG
    _DEBUG = debug


def write(msg, add_return=True, error=False):
    """Print the `msg` to the stdout"""
    if add_return:
        msg = str(msg) + "\n"
    fd = sys.stdout
    if error:
        fd = sys.stderr
    fd.write(msg)
    fd.flush()


def debug(msg):
    """Print the `msg` to the stdout if debug mode is set"""
    if _DEBUG:
        write(msg, error=True)
