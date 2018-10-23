# -*- coding: utf-8 -*-
# Copyright© 1986-2018 Altair Engineering Inc.

"""pkr functions for creating the context"""

import os

from builtins import object
from compose.cli.command import get_project_name
from pathlib2 import Path

from .cli.log import write
from .utils import TemplateEngine, ensure_dir_absent, get_pkr_path


class Context(object):
    """Context object used to manipulate the context used to generate
    docker images
    """

    DOCKER_CONTEXT = 'docker-context'

    def __init__(self, kard):
        self.kard = kard
        self.env = kard.env
        self.path = Path(kard.path) / self.DOCKER_CONTEXT

        if self.kard.meta.get('project_name') is None:
            self.kard.meta['project_name'] = get_project_name(
                str(get_pkr_path()))

        self.tpl_context = None
        self.tpl_env = None

    def relative(self, *elements):
        """Gives the relative path to context"""
        return Path(self.path, *elements)

    def populate_context(self, reset=True):
        """Create the context according to the env"""
        if reset:
            write('Removing docker-context... ', add_return=False)
            ensure_dir_absent(self.path)
            write('done !')

        write('(Re)creating docker-context... ', add_return=False)
        self.path.mkdir(exist_ok=True)
        write('done !')

        self.copy_files()

    def copy_files(self):
        """Use the environment information to recreate the context according to
        the 'requires' section of the containers description
        """
        write('Recreating sources in pkr context... ', add_return=False)

        context_path = self.env.pkr_path / self.env.context_template_dir

        data = self.kard.meta.copy()
        data.update({'env': self.env.env_name})

        # Get custom template data from extensions
        for custom_data in self.kard.extensions.get_context_template_data():
            if custom_data:
                data.update(custom_data)

        tpl_engine = TemplateEngine(data)

        for container in self.env.get_container():
            try:
                dockerfile = self.env.get_container(container)['dockerfile']
            except KeyError:
                # In this case, we use an image provided by the hub
                continue
            name = os.path.splitext(dockerfile)[0] + '*'
            tpl_engine.copy(path=context_path / name,
                            origin=context_path,  # + os.path.sep,
                            # Separator is important to indicate a folder
                            local_dst=self.path,  # + os.path.sep,
                            excluded_paths=[],
                            gen_template=True)

        # Copying containers requirements
        for src in self.env.get_requires():
            origin = Path(self.replace_var(src['origin']))

            tpl_engine.copy(path=origin,
                            origin=origin,
                            local_dst=self.path / src['dst'],
                            excluded_paths=[self.replace_var(e)
                                            for e in src.get('exclude', [])])

        write('done !')

    def replace_var(self, path):
        """Replace the Kard var if present, elsif return full path"""
        kard_path_var = '$KARD_PATH'
        src_path_var = '$SRC_PATH'
        if kard_path_var in path:
            return path.replace(kard_path_var, str(self.kard.path))
        if src_path_var in path:
            return path.replace(src_path_var, self.kard.meta['src_path'])
        return Path(get_pkr_path() / path)
