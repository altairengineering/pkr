# -*- coding: utf-8 -*-
# Copyright© 1986-2018 Altair Engineering Inc.

import sys

_DEBUG = False


def set_debug(debug=False):
    global _DEBUG
    _DEBUG = debug


def write(msg, add_return=True):
    """Print the `msg` to the stdout"""
    if add_return:
        msg += '\n'
    sys.stdout.write(msg)
    sys.stdout.flush()


def debug(msg):
    """Print the `msg` to the stdout if debug mode is set"""
    if _DEBUG:
        write(msg)
