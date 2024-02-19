# Copyright© 1986-2024 Altair Engineering Inc.

"""Utilities for logging on TTY"""

import sys

_DEBUG = False


def set_debug(dbg=False):
    """Activate debug mode"""
    # pylint: disable=global-statement
    global _DEBUG
    _DEBUG = dbg


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
