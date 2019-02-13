# -*- coding: utf-8 -*-
# Copyright© 1986-2018 Altair Engineering Inc.

"""Git extension to allow fetching a git repository when creating a Kard"""

from __future__ import absolute_import

from builtins import str
import os

from git import Repo

from pkr.cli.log import write
from . import ExtMixin


class Git(ExtMixin):
    """Mixin for an extension implementation"""

    @staticmethod
    def setup(args, kard):
        """Populate build_data with extension specific values

        Args:
          - args: the args passed in the env
          - kard: the kard object
        """
        git_repo = args.get('git_repo', kard.meta.get('git_repo'))
        if git_repo is not None:
            src_path = kard.meta['src_path']
            git_branch = args.get('git_branch',
                                  kard.meta.get('git_branch', 'master'))
            if not os.path.isdir(src_path):
                write('Fetching sources from {}:{} to {}'.format(git_repo,
                                                                 git_branch,
                                                                 src_path))
                try:
                    repo = Repo.clone_from(git_repo, src_path,
                                           branch=git_branch,
                                           single_branch=True,
                                           depth=1)

                    for sub_module in repo.submodules:
                        sub_module.update()

                except Exception as exc:
                    write('Could not fetch repository: {}'.format(str(exc)))
                    raise exc

            else:
                write('Using sources from {}'.format(src_path))
