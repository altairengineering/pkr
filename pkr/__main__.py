#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright© 1986-2018 Altair Engineering Inc.

"""Main module.

This calls the main function. This is designed to be used as a command line.
To display the help, run: pkr --help.
"""
import sys
import traceback

from pkr.cli import log
from pkr.cli.parser import get_parser
from pkr.driver import set_use_env_var


def main():
    """Main function"""
    try:
        parser = get_parser()
        cli_args = parser.parse_args()
        log.set_debug(cli_args.debug)
        set_use_env_var(not cli_args.no_env_var)
        cli_args.func(cli_args)
    except Exception as exc:  # pylint: disable=W0703
        # Here we do exception catching on parser as our parser
        # is dynamic to current directory (kard mostly), thus
        # we cannot ensure it will not fail
        if "--debug" in sys.argv or "-d" in sys.argv:
            log.set_debug(True)
        log.write("ERROR: ({}) {}".format(type(exc).__name__, exc), error=True)
        log.debug("".join(traceback.format_exception(*sys.exc_info())))
        return 1
    return 0


sys.exit(main())
