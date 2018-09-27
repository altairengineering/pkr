#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright© 1986-2018 Altair Engineering Inc.

"""Main module.

This calls the main function. This is designed to be used as a command line.
To display the help, run: pkr --help.
"""
import sys
import traceback

from builtins import str

from pkr.cli import log
from pkr.cli.parser import get_parser
from pkr.utils import KardInitializationException


def main():
    """Main function"""
    try:
        cli_args = get_parser().parse_args()

        # Setting the log mode
        debug = cli_args.__dict__.pop('debug')
        log.set_debug(debug)

        func = cli_args.__dict__.pop('func')
        func(cli_args)
    except KardInitializationException as exc:
        log.write(str(exc))
        return 1
    except Exception as exc:  # pylint: disable=W0703
        log.write('ERROR: ({}) {}'.format(type(exc).__name__, exc))
        log.debug(''.join(traceback.format_exception(*sys.exc_info())))
        return 1
    return 0


sys.exit(main())
