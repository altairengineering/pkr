# -*- coding: utf-8 -*-
# Copyright© 1986-2018 Altair Engineering Inc.

"""pkr shell"""

import cmd

import argparse
import shlex
import sys

from pkr.kard import Kard
from pkr.cli.log import write


class PkrShell(cmd.Cmd):
    intro = 'Welcome to the pkr shell.   Type help or ? to list commands.\n'
    prompt = '(pkr) '

    def __init__(self, parser, **kwargs):
        cmd.Cmd.__init__(self, **kwargs)
        self.parser = parser
        self.kard = Kard.load_current()

    def default(self, line):
        """Call the parser func method"""
        if line != 'EOF':
            try:
                args = self.parser.parse_args(shlex.split(line))
            except argparse.ArgumentError as exc:
                write((exc, '\n', exc.args))
                return
            except SystemExit as exc:
                write(exc)
                return
            if hasattr(args, 'func'):
                try:
                    args.func(self.kard.env, args)
                    return
                except SystemExit as exc:
                    write(exc)
                    return
        cmd.Cmd.default(self, line)

    @staticmethod
    def do_EOF(*_):  # pylint: disable=C0103
        write('')
        sys.exit()

    def emptyline(self):
        """Do nothing if enter is pressed twice"""
