# -*- coding: utf-8 -*-
# Copyright© 1986-2018 Altair Engineering Inc

from argparse import Action, OPTIONAL
import copy


class ExtendAction(Action):
    """CLI argument extend action"""

    def __init__(
        self,
        option_strings,
        dest,
        nargs=None,
        const=None,
        default=None,
        type=None,
        choices=None,
        required=False,
        help=None,
        metavar=None,
    ):
        if nargs == 0:
            raise ValueError(
                "nargs for append actions must be != 0; if arg string are not "
                "supplying the value to append, the append const action may "
                "be more appropriate"
            )
        if const is not None and nargs != OPTIONAL:
            raise ValueError("nargs must be %r to supply const" % OPTIONAL)

        super(ExtendAction, self).__init__(
            option_strings=option_strings,
            dest=dest,
            nargs=nargs,
            const=const,
            default=default,
            type=type,
            choices=choices,
            required=required,
            help=help,
            metavar=metavar,
        )

    def __call__(self, parser, namespace, values, option_string=None):
        items = getattr(namespace, self.dest, None)

        if items is None:
            items = []
        elif isinstance(items, list):
            items = items[:]
        else:
            items = copy.copy(items)

        items.extend(values)
        setattr(namespace, self.dest, items)
