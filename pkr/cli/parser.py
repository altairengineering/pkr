#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright© 1986-2019 Altair Engineering Inc.

"""pkr CLI parser"""

import argparse
from getpass import getpass

from pathlib import Path
import yaml

from .action import ExtendAction
from .log import write
from ..driver import list_drivers
from ..ext import ExtMixin, Extensions
from ..kard import Kard
from ..utils import PkrException, create_pkr_folder, Cmd
from ..version import __version__


def get_parser():
    """Return the pkr parser"""
    pkr_parser = argparse.ArgumentParser()
    pkr_parser.set_defaults(func=lambda _: pkr_parser.print_help())
    pkr_parser.add_argument("-v", "--version", action="version", version="%(prog)s " + __version__)

    pkr_parser.add_argument("-d", "--debug", action="store_true")
    pkr_parser.add_argument("--no-env-var", action="store_true")
    pkr_parser.add_argument(
        "-p",
        "--password",
        dest="crypt_password",
        help="password to encrypt/decrypt kard metadata with or '-' to input password from terminal",
    )

    sub_p = pkr_parser.add_subparsers(title="Commands", metavar="<command>", help="<action>")

    # Stop parser
    stop_parser = sub_p.add_parser("stop", help="Stop pkr")
    add_service_argument(stop_parser)
    add_kard_argument(stop_parser)
    stop_parser.set_defaults(
        func=lambda args: Kard.load_current(args.kard, args.crypt_password).driver.stop(
            args.services
        )
    )

    # Restart parser
    restart_parser = sub_p.add_parser("restart", help="Restart pkr")
    add_service_argument(restart_parser)
    add_kard_argument(restart_parser)
    restart_parser.set_defaults(
        func=lambda args: Kard.load_current(args.kard, args.crypt_password).driver.restart(
            args.services
        )
    )

    # Start
    start_parser = sub_p.add_parser("start", help="Start pkr")
    add_service_argument(start_parser)
    add_kard_argument(start_parser)
    start_parser.add_argument("-y", "--yes", action="store_true", help="Answer yes to questions")
    start_parser.set_defaults(
        func=lambda args: Kard.load_current(args.kard, args.crypt_password).driver.start(
            args.services, args.yes
        )
    )

    # Up parser
    up_parser = sub_p.add_parser("up", help="Rebuild context, images and start pkr")
    add_service_argument(up_parser)
    up_parser.add_argument(
        "-v", "--verbose", action="store_true", help="verbose mode", default=False
    )
    up_parser.add_argument("--build-log", help="Log file for image building", default=None)
    add_kard_argument(up_parser)
    up_parser.set_defaults(
        func=lambda args: Kard.load_current(args.kard, args.crypt_password).driver.cmd_up(
            args.services, verbose=args.verbose, build_log=args.build_log
        )
    )

    # Ps parser
    parser = sub_p.add_parser("ps", help="List containers defined in the current kard")
    add_kard_argument(parser)
    parser.set_defaults(
        func=lambda args: Kard.load_current(args.kard, args.crypt_password).driver.cmd_ps()
    )

    # Status parser
    parser = sub_p.add_parser("status", help="Check all containers of the kard are healthy")
    add_kard_argument(parser)
    parser.set_defaults(
        func=lambda args: Kard.load_current(args.kard, args.crypt_password).driver.cmd_status(
            args.crypt_password
        )
    )

    # Clean parser
    parser = sub_p.add_parser("clean", help="Stop and remove containers of current kard")
    parser.add_argument("-k", "--kill", action="store_true", help="Kill (SIGKILL) before clean")
    add_kard_argument(parser, add_short_option=False)
    parser.set_defaults(
        func=lambda args: Kard.load_current(args.kard, args.crypt_password).driver.clean(args.kill)
    )

    # Kard parser
    configure_kard_parser(sub_p.add_parser("kard", help="CLI for kards manipulation"))

    # Image parser
    configure_image_parser(sub_p.add_parser("image", help="Manage docker images"))

    # List available extensions
    list_extension_parser = sub_p.add_parser("listext", help="List extensions")
    list_extension_parser.add_argument(
        "-a", "--all", action="store_true", help="Show all available extensions"
    )
    add_kard_argument(list_extension_parser)
    list_extension_parser.set_defaults(
        func=lambda args: print(
            *(
                Extensions().list()
                if args.all
                else Kard.load_current(args.kard, args.crypt_password).extensions.list()
            ),
            sep="\n",
        )
    )

    # Ext parser
    configure_ext_parser(sub_p.add_parser("ext", help="Call extension method"))

    # Init
    init_parser = sub_p.add_parser("init", help="Build a base tree structure for pkr.")
    init_parser.add_argument(
        "path", help="The path in which to init the pkr environment.", default=None
    )

    def create_env(args):
        pkr_path = Path(args.path)
        create_pkr_folder(pkr_path)
        write("File structure created in : {}".format(str(pkr_path.absolute())))

    init_parser.set_defaults(func=create_env)

    return pkr_parser


def configure_image_parser(parser):
    parser.set_defaults(func=lambda _: parser.print_help())
    sub_p = parser.add_subparsers(title="Commands", metavar="<command>", help="<action>")

    # Build parser
    build_parser = sub_p.add_parser("build", help="Build docker images")
    build_parser.add_argument("-t", "--tag", default=None, help="The tag for images")
    build_parser.add_argument("-T", "--target", default=None, help="The targeted stage")
    build_parser.add_argument(
        "-r", "--rebuild-context", action="store_true", default=True, help="Rebuild the context"
    )
    build_parser.add_argument(
        "-n", "--nocache", action="store_true", help="Pass nocache to docker for the build"
    )
    build_parser.add_argument(
        "-p", "--parallel", type=int, default=None, help="Number of parallel image build"
    )
    build_parser.add_argument(
        "-b", "--no-rebuild", action="store_true", help="Disable rebuild if image already exists"
    )
    build_parser.add_argument(
        "-c",
        "--clean-builder",
        action="store_true",
        help="Clean builder before build (buildx driver)",
    )
    add_service_argument(build_parser)
    add_kard_argument(build_parser)
    build_parser.set_defaults(
        func=lambda args: Kard.load_current(args.kard, args.crypt_password).driver.build_images(
            **args.__dict__
        )
    )

    # Push parser
    push_parser = sub_p.add_parser("push", help="Push docker images")
    add_service_argument(push_parser)
    push_parser.add_argument("-r", "--registry", default=None, help="The docker registry")
    push_parser.add_argument("-u", "--username", default=None, help="The docker registry username")
    push_parser.add_argument("-p", "--password", default=None, help="The docker registry password")
    push_parser.add_argument("-t", "--tag", default=None, help="The tag for images")
    push_parser.add_argument(
        "-o", "--other-tags", default=[], nargs="+", help="Supplemental tags for images"
    )
    push_parser.add_argument(
        "--parallel", type=int, default=None, help="Number of parallel image push"
    )
    add_kard_argument(push_parser)
    push_parser.set_defaults(
        func=lambda args: Kard.load_current(args.kard, args.crypt_password).driver.push_images(
            **args.__dict__
        )
    )

    # Login parser
    login_parser = sub_p.add_parser("login", help="Login docker registry")
    add_service_argument(login_parser)
    login_parser.add_argument("-r", "--registry", default=None, help="The docker registry")
    login_parser.add_argument(
        "-u", "--username", default=None, help="The docker registry username"
    )
    login_parser.add_argument(
        "-p", "--password", default=None, help="The docker registry password"
    )
    login_parser.set_defaults(
        func=lambda args: Kard.load_current(
            args.kard, args.crypt_password
        ).driver.logon_remote_registry(**args.__dict__)
    )

    # Pull parser
    pull_parser = sub_p.add_parser("pull", help="Pull docker images")
    add_service_argument(pull_parser)
    pull_parser.add_argument("-r", "--registry", default=None, help="The docker registry")
    pull_parser.add_argument("-u", "--username", default=None, help="The docker registry username")
    pull_parser.add_argument("-p", "--password", default=None, help="The docker registry password")
    pull_parser.add_argument("-t", "--tag", default=None, help="The tag for images")
    pull_parser.add_argument(
        "--parallel", type=int, default=None, help="Number of parallel image pull"
    )
    pull_parser.add_argument(
        "--ignore-errors", action="store_true", help="Ignore image pull errors"
    )
    add_kard_argument(pull_parser)
    pull_parser.set_defaults(
        func=lambda args: Kard.load_current(args.kard, args.crypt_password).driver.pull_images(
            **args.__dict__
        )
    )

    # Purge parser
    purge_parser = sub_p.add_parser(
        "purge", help="Delete all images for containers of the current kard"
    )
    purge_parser.add_argument("--tag", default=None, help="Delete images with the given tag")
    purge_parser.add_argument(
        "--except-tag", default=None, help="Do not delete images with the given tag"
    )
    purge_parser.add_argument(
        "--repository", default=None, help="Delete image reference in a specified repository"
    )
    add_kard_argument(purge_parser)
    purge_parser.set_defaults(
        func=lambda args: Kard.load_current(args.kard, args.crypt_password).driver.purge_images(
            **args.__dict__
        )
    )

    # List parser
    list_parser = sub_p.add_parser(
        "list", help="List all images for containers of the current kard"
    )
    list_parser.add_argument("--tag", default=None, help="List images with the given tag")
    add_service_argument(list_parser)
    add_kard_argument(list_parser)
    list_parser.set_defaults(
        func=lambda args: Kard.load_current(args.kard, args.crypt_password).driver.list_images(
            **args.__dict__
        )
    )

    # Download parser
    download_parser = sub_p.add_parser(
        "download", help="Download all images for containers of the current kard"
    )
    download_parser.add_argument("-r", "--registry", default=None, help="The docker registry")
    download_parser.add_argument(
        "-u", "--username", default=None, help="The docker registry username"
    )
    download_parser.add_argument(
        "-p", "--password", default=None, help="The docker registry password"
    )
    download_parser.add_argument("--tag", default=None, help="Download images with the given tag")
    download_parser.add_argument(
        "--nopull", default=False, action="store_true", help="Do not pull before export"
    )
    add_service_argument(download_parser)
    add_kard_argument(download_parser)
    download_parser.set_defaults(
        func=lambda args: Kard.load_current(args.kard, args.crypt_password).driver.download_images(
            **args.__dict__
        )
    )

    # Import parser
    import_parser = sub_p.add_parser("import", help="Import all images from kard to docker")
    import_parser.add_argument("--tag", default=None, help="Import images to the given tag")
    add_service_argument(import_parser)
    add_kard_argument(import_parser)
    import_parser.set_defaults(
        func=lambda args: Kard.load_current(args.kard, args.crypt_password).driver.import_images(
            **args.__dict__
        )
    )


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
    parser.set_defaults(func=lambda _: parser.print_help())
    sub_p = parser.add_subparsers(title="Commands", metavar="<command>", help="<action>")

    make_context = sub_p.add_parser(
        "make", help="Generate or regenerate docker-context using the current pkr " "kard"
    )
    make_context.add_argument(
        "-u",
        "--update",
        action="store_false",
        help="Update the previous docker-context, "
        "the files added in the docker-context "
        "after the previously pkr make will not "
        "be removed",
    )
    add_kard_argument(make_context)
    make_context.set_defaults(
        func=lambda args: Kard.load_current(args.kard, args.crypt_password).make(reset=args.update)
    )

    create_kard_p = sub_p.add_parser("create", help="Create a new kard")

    def _create_kard_handler(args):
        extra = {a[0]: a[1] for a in [a.split("=", 1) for a in args.__dict__.pop("extra")]}
        return Kard.create(extra=extra, **args.__dict__)

    create_kard_p.set_defaults(func=_create_kard_handler)
    create_kard_p.add_argument("name", help="The name of the kard")
    create_kard_p.add_argument("-e", "--env", default="dev", help="The environment (dev/prod)")
    create_kard_p.add_argument(
        "-d", "--driver", default=None, help="The pkr driver to use {}".format(list_drivers())
    )
    create_kard_p.add_argument(
        "-m", "--meta", type=argparse.FileType("r"), help="A file to load meta from"
    )
    create_kard_p.add_argument(
        "-f",
        "--features",
        help="Comma-separated list of features to include in the deployment. "
        "Take one or more of: elk, protractor, salt",
        default=None,
    )
    create_kard_p.add_argument(
        "--do-not-set-current",
        help='Do not change the "current" symbolic link after creating the Kard.',
        action="store_true",
    )
    create_kard_p.add_argument(
        "--extra",
        nargs="*",
        default=[],
        action=ExtendAction,
        help="Extra args",
    )

    list_kard = sub_p.add_parser("list", help="List kards")
    list_kard.add_argument(
        "-k", "--kubernetes", action="store_true", help="Query kube remote kards"
    )

    def _list_kard_handler(args):
        kards = Kard.list(args.kubernetes)
        if kards:
            write("Kards:")
            for kard in kards:
                write(" - {}".format(kard))
        else:
            write("No kard found.")

    list_kard.set_defaults(func=_list_kard_handler)

    get_kard = sub_p.add_parser("get", help="Get current kard")

    def _get_kard_handler(_):
        write("Current Kard: {}".format(Kard.get_current()))

    get_kard.set_defaults(func=_get_kard_handler)

    dump_kard = sub_p.add_parser(
        "dump", help="Dump current kard templating context (including all values)"
    )
    dump_kard.add_argument(
        "-c",
        "--cleaned",
        action="store_true",
        help="Include only kard specific values (effectively dump the content of meta.yml)",
    )
    add_kard_argument(dump_kard)
    dump_kard.set_defaults(
        func=lambda args: write(
            Kard.load_current(args.kard, args.crypt_password).dump(**args.__dict__)
        )
    )

    load_kard = sub_p.add_parser("load", help="Load a kard")
    load_kard.set_defaults(func=lambda args: Kard.set_current(args.name, args.crypt_password))
    load_kard.add_argument("name", help="The name of the kard")

    update_kard_p = sub_p.add_parser("update", help="Update the current kard")
    add_kard_argument(update_kard_p)
    update_kard_p.set_defaults(
        func=lambda args: Kard.load_current(args.kard, args.crypt_password).update()
    )

    encrypt_kard_p = sub_p.add_parser("encrypt", help="Encrypt metadata for the current kard")
    add_kard_argument(encrypt_kard_p)

    def _encrypt_kard_handler(args):
        kard = Kard.load_current(args.kard, args.crypt_password, Cmd.ENCRYPT)
        kard.encrypt(kard.password)
        kard.driver.encrypt(kard.password)

    encrypt_kard_p.set_defaults(func=lambda args: _encrypt_kard_handler(args))

    decrypt_kard_p = sub_p.add_parser("decrypt", help="Decrypt metadata for the current kard")
    add_kard_argument(decrypt_kard_p)

    def _decrypt_kard_handler(args):
        kard = Kard.load_current(args.kard, args.crypt_password, Cmd.DECRYPT)
        kard.decrypt(kard.password)
        kard.driver.decrypt(kard.password)

    decrypt_kard_p.set_defaults(func=lambda args: _decrypt_kard_handler(args))


def configure_ext_parser(parser):
    parser.set_defaults(func=lambda _: parser.print_help())
    sub_p = parser.add_subparsers(title="Extensions", metavar="<extension>", help="Extensions")

    try:
        for name, ext in Extensions.list_all().items():
            if (
                hasattr(ext, "configure_parser")
                and ext.configure_parser is not ExtMixin.configure_parser
            ):
                ext_parser = sub_p.add_parser(
                    name, help="{} extension features".format(name.capitalize())
                )
                ext.configure_parser(ext_parser)
    except PkrException:
        pass


def add_service_argument(parser):
    parser.add_argument(
        "-s", "--services", nargs="+", default=None, help="List of services (default to all)"
    )


def add_kard_argument(parser, add_short_option=True):
    options = {
        "default": None,
        "help": 'Use a different Kard than "current". You may also set PKR_KARD.',
    }
    if add_short_option:
        parser.add_argument("-k", "--kard", **options)
    else:
        parser.add_argument("--kard", **options)


def input_password(pw):
    if pw == "-":
        return getpass()
    else:
        return pw
