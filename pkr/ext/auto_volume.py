# -*- coding: utf-8 -*-
# Copyright© 1986-2018 Altair Engineering Inc.

"""Git extension to allow using sources from volumes or build them into the
image"""
import os

import jinja2

from pkr.kard import Kard
from . import ExtMixin


class AutoVolume(ExtMixin):
    """Macro for dockerfiles templating which allows either mounting or
    adding files according to the meta `use_volume`.
    """

    @staticmethod
    def get_context_template_data():
        kard = Kard.load_current()
        return {"add_file": add_file, "use_volume": kard.env.get("use_volume", False)}


@jinja2.contextfunction
def add_file(context, paths):
    """This function is used inside the dockerfiles templates to
    render them by using either the ADD or VOLUME instruction."""
    if context["use_volume"]:
        paths = paths.get("common", {})
        paths = ['"{}"'.format(path) for path in list(paths.keys())]
        if len(paths):
            return "VOLUME [{}]".format(", ".join(paths))
        else:
            return ""

    lines = []
    paths = dict(list(paths.get("common", {}).items()) + list(paths.get("copied", {}).items()))
    for remote, local in sorted(paths.items()):
        lines.append('ADD "{}" "{}"'.format(local, remote))
    return os.linesep.join(lines)
