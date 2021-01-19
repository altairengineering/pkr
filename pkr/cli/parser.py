#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright© 1986-2019 Altair Engineering Inc.

"""pkr CLI parser"""
from __future__ import absolute_import

import argparse

from pathlib2 import Path
import stevedore
import yaml

from .log import write
from .shell import PkrShell
from ..ext import Extensions
from ..kard import Kard
from ..utils import PkrException, create_pkr_folder
from ..version import __version__


def _build_images(args):
    kard = Kard.load_current()
    if args.rebuild_context:
        kard.make()

    # Build images
    services = args.services or list(kard.env.get_container().keys())
    kard.docker_cli.build_images(
        services, tag=args.tag, nocache=args.nocache, parallel=args.parallel,
        no_rebuild=args.no_rebuild)


def _push_images(args):
    kard = Kard.load_current()

    # Push images
    services = args.services or list(kard.env.get_container().keys())
    registry = kard.docker_cli.get_registry(url=args.registry,
                                            username=args.username,
                                            password=args.password)
    kard.docker_cli.push_images(
        services, registry, tag=args.tag, other_tags=args.other_tags, parallel=args.parallel)


def _pull_images(args):
    kard = Kard.load_current()

    # Push images
    services = args.services or list(kard.env.get_container().keys())
    registry = kard.docker_cli.get_registry(url=args.registry,
                                            username=args.username,
                                            password=args.password)
    kard.docker_cli.pull_images(
        services, registry, tag=args.tag, parallel=args.parallel)


def _download_images(args):
    kard = Kard.load_current()
    services = args.services or list(kard.env.get_container().keys())
    registry = kard.docker_cli.get_registry(url=args.registry,
                                            username=args.username,
                                            password=args.password)
    kard.docker_cli.download_images(
        services, registry, tag=args.tag, nopull=args.nopull)


def _import_images(args):
    kard = Kard.load_current()
    services = args.services or list(kard.env.get_container().keys())
    kard.docker_cli.import_images(services, tag=args.tag)


def _list_images(args):
    kard = Kard.load_current()
    services = args.services or list(kard.env.get_container().keys())
    if args.tag is None:
        args.tag = kard.meta['tag']
    for service in services:
        write(kard.docker_cli.make_image_name(service, args.tag))


def _purge(args):
    kard = Kard.load_current()
    kard.docker_cli.purge(args.except_tag, args.tag, args.repository)


def _list_kards(*_):
    kards = Kard.list()
    if kards:
        write('Kards:')
        for kard in kards:
            write(' - {}'.format(kard))
    else:
        write('No kard found.')


def _create_kard(args):
    extras = {}
    if args.meta:
        extras.update(yaml.safe_load(args.meta))
    extras.update({a[0]: a[1] for a in [a.split('=', 1) for a in args.extra]})

    try:
        extra_features = args.features
        if extra_features is not None:
            extras.update({'features': extra_features.split(',')})
    except AttributeError:
        pass

    for key, value in list(extras.items()):

        if isinstance(value, str) and value.lower() in ('true', 'false'):
            extras[key] = value = value.lower() == 'true'

        if '.' in key:
            extras.pop(key)
            dict_it = extras
            sub_keys = key.split('.')
            for sub_key in sub_keys[:-1]:
                dict_it = dict_it.setdefault(sub_key, {})
            dict_it[sub_keys[-1]] = value

    Kard.create(args.name, args.env, args.driver, extras)
    Kard.set_current(args.name)
    write('Current kard is now: {}'.format(args.name))


def get_parser():
    """Return the pkr parser"""
    pkr_parser = argparse.ArgumentParser()
    pkr_parser.add_argument('-v', '--version', action='version',
                            version='%(prog)s ' + __version__)

    pkr_parser.add_argument('-d', '--debug', action='store_true')

    sub_p = pkr_parser.add_subparsers(
        title="Commands", metavar="<command>", help='<action>')

    # Shell
    sub_p.add_parser('shell', help='Launch pkr shell').set_defaults(
        func=lambda *_: PkrShell(pkr_parser).cmdloop())

    # Stop parser
    stop_parser = sub_p.add_parser('stop', help='Stop pkr')
    add_service_argument(stop_parser)

    stop_parser.set_defaults(
        func=lambda a: Kard.load_current().docker_cli.stop(a.services))

    # Restart parser
    restart_parser = sub_p.add_parser('restart', help='Restart pkr')
    add_service_argument(restart_parser)

    restart_parser.set_defaults(
        func=lambda a: Kard.load_current().docker_cli.restart(a.services))

    # Start
    start_parser = sub_p.add_parser('start', help='Start pkr')
    add_service_argument(start_parser)
    start_parser.add_argument(
        '-y', '--yes', action='store_true', help="Answer yes to questions")
    start_parser.set_defaults(
        func=lambda a: Kard.load_current().docker_cli.start(a.services, a.yes))

    # Up parser
    up_parser = sub_p.add_parser(
        'up', help='Rebuild context, images and start pkr')
    add_service_argument(up_parser)
    up_parser.add_argument(
        '-v',
        '--verbose',
        action='store_true',
        help='verbose mode',
        default=False)

    up_parser.add_argument(
        '--build-log',
        help='Log file for image building',
        default=None)

    up_parser.set_defaults(
        func=lambda a: Kard.load_current().docker_cli.cmd_up(
            a.services, verbose=a.verbose, build_log=a.build_log))

    # Ps parser
    parser = sub_p.add_parser(
        'ps',
        help='List containers defined in the current kard')
    parser.set_defaults(
        func=lambda *a: Kard.load_current().docker_cli.cmd_ps())

    # Clean parser
    parser = sub_p.add_parser(
        'clean',
        help='Stop and remove containers of current kard')
    parser.add_argument(
        '-k', '--kill', action='store_true', help="Kill (SIGKILL) before clean")
    parser.set_defaults(func=lambda a: Kard.load_current().docker_cli.clean(a.kill))

    # Kard parser
    configure_kard_parser(
        sub_p.add_parser('kard', help='CLI for kards manipulation'))

    # Image parser
    configure_image_parser(
        sub_p.add_parser('image', help='Manage docker images'))

    # List available extensions
    list_extension_parser = sub_p.add_parser(
        'listext', help='ListExt')
    list_extension_parser.set_defaults(
        func=lambda *_: Kard.load_current().extensions.list())

    # Ext parser
    configure_ext_parser(
        sub_p.add_parser('ext', help='Manage extensions images'))

    # Init
    init_parser = sub_p.add_parser(
        'init', help='Build a base tree structure for pkr.')
    init_parser.add_argument(
        'path',
        help='The path in which to init the pkr environment.',
        default=None)

    def create_env(args):
        pkr_path = Path(args.path)
        create_pkr_folder(pkr_path)
        write(
            'File structure created in : {}'.format(str(pkr_path.absolute())))

    init_parser.set_defaults(func=create_env)

    return pkr_parser


def configure_image_parser(parser):
    sub_p = parser.add_subparsers(
        title="Commands", metavar="<command>", help='<action>')

    # Build parser
    build_parser = sub_p.add_parser('build', help='Build docker images')
    build_parser.add_argument('-t',
                              '--tag',
                              default=None,
                              help='The tag for images')
    build_parser.add_argument('-r',
                              '--rebuild-context',
                              action='store_true',
                              default=True,
                              help='Rebuild the context')
    build_parser.add_argument(
        '-n', '--nocache',
        action='store_true',
        help='Pass nocache to docker for the build')
    build_parser.add_argument(
        '-p', '--parallel',
        type=int, default=None,
        help='Number of parallel image build')
    build_parser.add_argument(
        '-b', '--no-rebuild',
        action='store_true',
        help='Disable rebuild if image already exists')
    add_service_argument(build_parser)
    build_parser.set_defaults(func=_build_images)

    # Push parser
    push_parser = sub_p.add_parser('push', help='Push docker images')
    add_service_argument(push_parser)
    push_parser.add_argument('-r', '--registry',
                             default=None,
                             help='The docker registry')
    push_parser.add_argument('-u', '--username',
                             default=None,
                             help='The docker registry username')
    push_parser.add_argument('-p', '--password',
                             default=None,
                             help='The docker registry password')
    push_parser.add_argument('-t', '--tag',
                             default=None,
                             help='The tag for images')
    push_parser.add_argument('-o', '--other-tags',
                             default=[], nargs='+',
                             help='Supplemental tags for images')
    push_parser.add_argument(
        '--parallel',
        type=int, default=None,
        help='Number of parallel image push')
    push_parser.set_defaults(func=_push_images)

    # Pull parser
    pull_parser = sub_p.add_parser('pull', help='Pull docker images')
    add_service_argument(pull_parser)
    pull_parser.add_argument('-r', '--registry',
                             default=None,
                             help='The docker registry')
    pull_parser.add_argument('-u', '--username',
                             default=None,
                             help='The docker registry username')
    pull_parser.add_argument('-p', '--password',
                             default=None,
                             help='The docker registry password')
    pull_parser.add_argument('-t', '--tag',
                             default=None,
                             help='The tag for images')
    pull_parser.add_argument(
        '--parallel',
        type=int, default=None,
        help='Number of parallel image pull')
    pull_parser.set_defaults(func=_pull_images)

    # Purge parser
    purge_parser = sub_p.add_parser(
        'purge',
        help='Delete all images for containers of the current kard')
    purge_parser.add_argument(
        '--tag',
        default=None,
        help='Delete images with the given tag')
    purge_parser.add_argument(
        '--except-tag',
        default=None,
        help='Do not delete images with the given tag')
    purge_parser.add_argument(
        '--repository',
        default=None,
        help='Delete image reference in a specified repository')
    purge_parser.set_defaults(func=_purge)

    # List parser
    list_parser = sub_p.add_parser(
        'list',
        help='List all images for containers of the current kard')
    list_parser.add_argument(
        '--tag',
        default=None,
        help='List images with the given tag')
    add_service_argument(list_parser)

    list_parser.set_defaults(func=_list_images)

    # Download parser
    download_parser = sub_p.add_parser(
        'download',
        help='Download all images for containers of the current kard')
    download_parser.add_argument(
        '-r', '--registry',
        default=None,
        help='The docker registry')
    download_parser.add_argument(
        '-u', '--username',
        default=None,
        help='The docker registry username')
    download_parser.add_argument(
        '-p', '--password',
        default=None,
        help='The docker registry password')
    download_parser.add_argument(
        '--tag',
        default=None,
        help='Download images with the given tag')
    download_parser.add_argument(
        '--nopull',
        default=False,
        action='store_true',
        help='Do not pull before export')
    add_service_argument(download_parser)
    download_parser.set_defaults(func=_download_images)

    # Import parser
    import_parser = sub_p.add_parser(
        'import',
        help='Import all images from kard to docker')
    import_parser.add_argument(
        '--tag',
        default=None,
        help='Import images to the given tag')
    add_service_argument(import_parser)
    import_parser.set_defaults(func=_import_images)


def configure_kard_parser(parser):
    """
    pkr - A CI tool for Cloud Manager

    Template directory:

        jinja2 template syntax can be used in template any file in
        templates/**/ directory.

        When kard is made, The jinja2 template engine will substitute the
        variable bellow:

            - driver: contains the given value to -d/--drive parameter
                      during the pkr kard make option.

            - env: contains the given value to -e/--env parameter
                   during the pkr kard make option.

            - features: a list containing given values to --features parameter
                        by default the list contains 'init'.

            - passwords: a dict containing passwords set in meta.yml

            - add_file: this function can be used inside the dockerfiles
                        templates to render them by using either the ADD
                        or VOLUME instruction

            note: All value set with --extra parameter are available in
                  template.
    """

    sub_p = parser.add_subparsers(
        title="Commands", metavar="<command>", help='<action>')

    make_context = sub_p.add_parser(
        'make',
        help='Generate or regenerate docker-context using the current pkr '
             'kard')
    make_context.add_argument('-u', '--update', action='store_false',
                              help='Update the previous docker-context, '
                                   'the files added in the docker-context '
                                   'after the previously pkr make will not '
                                   'be removed')
    make_context.set_defaults(func=lambda a: Kard.load_current().make(
        reset=a.update))

    create_kard_p = sub_p.add_parser('create', help='Create a new kard')
    create_kard_p.set_defaults(func=_create_kard)
    create_kard_p.add_argument('name', help='The name of the kard')
    create_kard_p.add_argument('-e', '--env',
                               default='dev',
                               help='The environment (dev/prod)')

    entry_points = stevedore.NamedExtensionManager(
        'drivers', []).list_entry_points()

    create_kard_p.add_argument('-d', '--driver',
                               default='compose',
                               help='The pkr driver to use {}'.format(
                                   tuple(entry_point.name
                                         for entry_point in entry_points)))

    create_kard_p.add_argument('-m', '--meta',
                               type=argparse.FileType('r'),
                               help='A file to load meta from')
    create_kard_p.add_argument(
        '--features',
        help='Comma-separated list of features to include in the deployment. '
             'Take one or more of: elk, protractor, salt',
        default=None)
    create_kard_p.add_argument(
        '--extra', nargs='*', default=[], help='Extra args')

    list_kard = sub_p.add_parser('list', help='List kards')
    list_kard.set_defaults(func=_list_kards)

    get_kard = sub_p.add_parser('get', help='Get current kard')
    get_kard.set_defaults(func=lambda *_: write(
        'Current Kard: {}'.format(Kard.get_current())))

    load_kard = sub_p.add_parser('load', help='Load a kard')
    load_kard.set_defaults(func=lambda a: Kard.set_current(a.name))
    load_kard.add_argument('name', help='The name of the kard')

    update_kard_p = sub_p.add_parser('update', help='Update the current kard')
    update_kard_p.set_defaults(func=lambda a: Kard.load_current().update())


def configure_ext_parser(parser):
    sub_p = parser.add_subparsers(
        title='Extensions', metavar='<extension>', help='<features>')

    # Build parser
    try:
        Kard.load_current()
    except PkrException:  # Catch missing PKR_PATH
        return

    for name, ext in Extensions.list_all():
        ext.configure_parser(sub_p.add_parser(
            name, help='{} extension features'.format(name.capitalize())))


def add_service_argument(parser):
    parser.add_argument(
        '-s',
        '--services',
        nargs='+',
        default=None,
        help='List of services (default to all)')
