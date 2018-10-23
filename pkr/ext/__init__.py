# -*- coding: utf-8 -*-
# Copyright© 1986-2018 Altair Engineering Inc.

"""Module containing extensions for pkr"""
import abc
import signal

from builtins import object
from builtins import str
from future.utils import with_metaclass
from stevedore.named import ExtensionManager, NamedExtensionManager

from pkr.cli.log import write
from pkr.utils import ask_input


class ExtMixin(with_metaclass(abc.ABCMeta, object)):
    """Mixin for an extension implementation"""

    @staticmethod
    def setup(args, kard):
        """Populate build_data with extension specific values.

        This hook is called when a new kard is created. It might also be used
        for kard updating.

        A practical implementation is provided in the function `check_args`
        below.

        Args:
          - args: the args passed in the env
          - kard: the kard object (which might not be available through
          load_current when a new kard is created)
        """

    @staticmethod
    def get_context_template_data():
        """"""

    @staticmethod
    def post_up(effective_modules):
        """Run specific post up jobs"""

    @staticmethod
    def populate_kard():
        """Populate kard folder"""

    @staticmethod
    def configure_parser(parser):
        """configure option parser"""


class Extensions(object):
    """This class allow the recursive call of a specific method on all
    extensions
    """

    def __init__(self, features):
        super(Extensions, self).__init__()
        self.features = set(features)
        self._extensions = None

    @property
    def extensions(self):
        """Lazy loading of extensions"""
        if self._extensions is None:
            self._extensions = NamedExtensionManager(
                namespace='extensions', names=self.features, name_order=True)
        return self._extensions

    def __getattr__(self, attribute):
        if hasattr(ExtMixin, attribute):
            if not self.features:
                return lambda *args, **kw: ()
            return lambda *args, **kw: self.extensions.map(
                self._wrap_call, attribute, *args, **kw)
        return super(Extensions, self).__getattribute__(attribute)

    @staticmethod
    def _wrap_call(extension, method_name, *args, **kwargs):
        method = getattr(extension.plugin(), method_name, None)

        if method is None:
            # it is OK if an extension does not implement all methods
            return

        try:
            return method(*args, **kwargs)
        except TimeoutError:
            write('Extension "{}" raise timeout error, step "{}"'.format(
                extension.name, method_name))
            raise
        except Exception as exc:
            write('Extension "{}" raise exception, step "{}": {}'.format(
                extension.name, method_name, str(exc)))
            raise

    def list(self):
        """Return the list of the extensions"""
        return iter(((e.name, e.plugin()) for e in self.extensions))

    @staticmethod
    def list_all():
        """Return the list of all available extensions"""
        extensions = ExtensionManager(namespace='extensions')
        return iter(((e.name, e.plugin()) for e in extensions.extensions))

    def __contains__(self, ext_name):
        return ext_name in self.features


class TimeoutError(Exception):
    """Exception for timeout"""


def timeout_handler(*_):
    """Simple function for raising a timeout Exception"""
    raise TimeoutError()


def timeout(timeout_duration):  # pylint: disable=C0111
    def wrap(func):  # pylint: disable=C0111
        def decorated_function(*args, **kwargs):  # pylint: disable=C0111
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(timeout_duration)
            ret = func(*args, **kwargs)
            signal.alarm(0)
            return ret

        return decorated_function

    return wrap


def check_args(args, kard, expected_metas, defaults=None):
    """Check if required metas are provided in the args.

    If not, it tries to look for a default in the environment, and if absent,
    prompt the user for it.
    """

    defaults = defaults or {}

    for meta in expected_metas:
        if meta in args:
            kard.meta[meta] = args.pop(meta)
        elif meta not in kard.meta:
            if defaults and meta in defaults:  # Already defined in the env
                kard.meta[meta] = defaults[meta]
            else:  # Already defined in the env default
                kard.meta[meta] = ask_input(meta)
