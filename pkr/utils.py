# -*- coding: utf-8 -*-
# Copyright© 1986-2019 Altair Engineering Inc.

# pylint: disable=C0111,E1101,R0912,R0913

"""Utils functions for pkr"""

import base64
import hashlib
from builtins import input
from builtins import object
from builtins import range
from builtins import str
import collections
import errno
from fnmatch import fnmatch
from glob import glob
import json
import os
import random
import re
import shutil
import time

import jinja2
from pathlib2 import Path

KARD_FOLDER = 'kard'
PATH_ENV_VAR = 'PKR_PATH'


class PkrException(Exception):
    """pkr Exception"""


class KardInitializationException(PkrException):
    """pkr Exception"""


def is_pkr_path(path):
    """Check environments files to deduce if path is a usable pkr path"""
    from pkr.environment import ENV_FOLDER
    return path.is_dir() and \
           len(list(path.glob('{}/*/env.yml'.format(ENV_FOLDER)))) > 0


def get_pkr_path(raise_if_not_found=True):
    """Return the path of the pkr folder

    If the env. var 'PKR_PATH' is specified, it is returned, otherwise a
    KeyError exception is raised.
    """

    full_path = Path(os.environ.get(PATH_ENV_VAR, os.getcwd())).absolute()
    pkr_path = full_path
    while pkr_path.parent != pkr_path:
        if is_pkr_path(pkr_path):
            return pkr_path
        pkr_path = pkr_path.parent

    if raise_if_not_found and not is_pkr_path(pkr_path):
        raise KardInitializationException(
            '{} path {} is not a valid pkr path, no usable env found'.format(
                'Given' if PATH_ENV_VAR in os.environ else 'Current',
                full_path))

    return pkr_path


def get_kard_root_path():
    """Return the root path of Kards"""
    return get_pkr_path() / KARD_FOLDER


def get_timestamp():
    """Return a string timestamp"""
    return time.strftime('%Y%m%d-%H%M%S')


class HashableDict(dict):
    """Extends dict with a __hash__ method to make it unique in a set"""

    def __key(self):
        return json.dumps(self)

    def __hash__(self):
        return hash(self.__key())

    def __eq__(self, other):
        return self.__key() == other.__key()  # pylint: disable=W0212


def merge(source, destination):
    """Deep merge 2 dicts

    Warning: the source dict is merged INTO the destination one. Make a copy
    before using it if you do not want to destroy the destination dict.
    """
    for key, value in list(source.items()):
        if isinstance(value, collections.Mapping):
            # get node or create one
            node = destination.setdefault(key, {})
            merge(value, node)
        elif isinstance(value, list):
            if key in destination:
                try:
                    destination[key] = list(dict.fromkeys(destination[key] + value))
                # Prevent errors when having unhashable dict types
                except TypeError:
                    destination[key].extend(value)
            else:
                destination[key] = value
        else:
            destination[key] = value

    return destination


def generate_password(pw_len=15):
    """Generate a password"""
    alphabet = 'abcdefghijklmnopqrstuvwxyz'
    upperalphabet = alphabet.upper()
    pwlist = []

    for _ in range(pw_len // 3):
        pwlist.append(alphabet[random.randrange(len(alphabet))])
        pwlist.append(upperalphabet[random.randrange(len(upperalphabet))])
        pwlist.append(str(random.randrange(10)))
    for _ in range(pw_len - len(pwlist)):
        pwlist.append(alphabet[random.randrange(len(alphabet))])

    random.shuffle(pwlist)
    return ''.join(pwlist)


def ensure_dir_absent(path):
    """Ensure a folder and its content are deleted"""
    try:
        shutil.rmtree(str(path))
    except OSError as err:
        if err.errno == errno.ENOENT:
            pass
        else:
            raise


def ask_input(name):
    return input('Missing meta({}):'.format(name))


class TemplateEngine(object):

    def __init__(self, tpl_context):
        self.tpl_context = tpl_context.copy()

        self.pkr_path = get_pkr_path()
        self.tpl_env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(self.pkr_path)))

        def b64encode(string):
            return base64.b64encode(string.encode("utf-8")).decode("utf-8")

        self.tpl_env.filters['b64encode'] = b64encode

        def sha256(string):
            return hashlib.sha256(string.encode("utf-8")).hexdigest()

        self.tpl_env.filters['sha256'] = sha256

    def process_template(self, template_file):
        """Process a template and render it in the context

        Args:
          - template_file: the template to load

        Return the result of the processed template.
        """

        rel_template_file = str(template_file.relative_to(self.pkr_path))

        template = self.tpl_env.get_template(rel_template_file)
        out = template.render(self.tpl_context)  # .encode('utf-8')
        return out

    def copy(self, path, origin, local_dst, excluded_paths,
             gen_template=False):
        """Copy a tree recursively, while excluding specified files

        Args:
          - path: the file or folder to copy
          - origin: the base folder of all paths
          - local_dst: the destination folder / file
          - excluded_paths: the list of unwanted excluded files
        """
        path_str = str(path)
        if '*' in path_str:
            file_list = [Path(p) for p in glob(path_str)]
            if '*' in origin.name:
                origin = origin.parent

            for path_it in file_list:
                rel_local_dst = path_it.relative_to(origin)
                full_local_dst = local_dst / rel_local_dst

                self.copy(path_it, path_it, full_local_dst,
                          excluded_paths, gen_template)
        elif path.is_file():
            # Direct match for excluded paths
            if path in excluded_paths:
                return
            if path != origin:
                # path = /pkr/src/backend/api/__init__.py
                abs_path = path.relative_to(origin)
                # path = api/__init__.py
                dst_path = local_dst / abs_path
                # path = docker-context/backend/api/__init__.py
            else:
                # Here we avoid having a '.' as our abs_path
                dst_path = local_dst
            # We ensure that the containing folder exists

            dst_path.parent.mkdir(parents=True, exist_ok=True)
            if gen_template and path.name.endswith('.template'):
                # If the dst_local contains the filename with template
                if not dst_path.is_dir():
                    if dst_path.name.endswith('.template'):
                        dst_path = self.remove_ext(dst_path)
                else:  # We create the destination path
                    dst_path = dst_path / self.remove_ext(path.name)
                out = self.process_template(path)
                dst_path.write_text(out)
                shutil.copystat(path_str, str(dst_path))
            else:
                shutil.copy2(path_str, str(dst_path))
        else:
            for path_it in path.iterdir():
                path_it = path / path_it
                if not any([fnmatch(str(path_it), str(exc_path))
                            for exc_path in excluded_paths]):
                    self.copy(path_it, origin, local_dst,
                              excluded_paths, gen_template)

    @staticmethod
    def remove_ext(path):
        """Remove the portion of a string after the last dot."""
        return path.parent / path.stem


FLAGS = re.VERBOSE | re.MULTILINE | re.DOTALL
WHITESPACE = re.compile(r'[ \t\n\r]*', FLAGS)


class ConcatJSONDecoder(json.JSONDecoder):

    def decode(self, s, _w=WHITESPACE.match):
        s_len = len(s)

        objs = []
        end = 0
        while end != s_len:
            obj, end = self.raw_decode(s, idx=_w(s, end).end())
            end = _w(s, end).end()
            objs.append(obj)
        return objs


def is_running_in_docker():
    """Return True if running in a docker container, False otherwise"""
    return os.path.exists('/.dockerenv')


def ensure_key_present(key, default, data, path=None):
    """Ensure that a key is present, set the default is present, or ask
    the user to input it."""

    if key in data:
        return data.pop(key)
    if key in default:
        return default.pop(key)

    return ask_input((path or '') + key)


def ensure_definition_matches(definition, defaults, data, path=None):
    """Recursive function that ensures data is provided.

    Ask for it if not.
    """
    path = path or ''
    if isinstance(definition, dict):
        values = {k: ensure_definition_matches(
            definition=v,
            defaults=defaults.get(k, []),
            data=data.get(k, {}),
            path=path + k + '/') for k, v in definition.items()}
        return values

    elif isinstance(definition, list):
        values = {}
        for element in definition:
            values.update(ensure_definition_matches(
                definition=element,
                defaults=defaults,
                data=data,
                path=path))
        return values

    else:
        value = ensure_key_present(definition, defaults, data, path)
        return {definition: value}


def create_pkr_folder(pkr_path=None):
    """Creates a folder structure for pkr.

    This looks like:
    PKR_PATH/
    ├── env/
    │   └── dev/
    │       └── env.yaml
    └── kard/
    """
    pkr_path = pkr_path or get_pkr_path(False)

    (pkr_path / 'env' / 'dev').mkdir(parents=True)
    (pkr_path / 'env' / 'dev' / 'env.yml').touch()
    (pkr_path / 'kard').mkdir(parents=True)
