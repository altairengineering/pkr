# -*- coding: utf-8 -*-
# Copyright© 1986-2018 Altair Engineering Inc.

"""Module containing extensions for pkr"""
import abc
from builtins import object
from builtins import str
import signal
import pkgutil

try:
    from importlib.metadata import entry_points
except ModuleNotFoundError:
    from importlib_metadata import entry_points

from pkr.cli.log import write
from pkr.utils import PkrException, get_pkr_path


class ExtMixin(metaclass=abc.ABCMeta):
    """Mixin for an extension implementation"""

    @staticmethod
    def setup(args, kard):
        """Populate build_data with extension specific values.

        This hook is called when a new kard is created. It might also be used
        for kard updating.

        A practical implementation is provided in the function
        `ensure_definition_matches` in utils.

        Args:
          - args: the args passed in the env
          - kard: the kard object (which might not be available through
          load_current when a new kard is created)
        """

    @staticmethod
    def get_context_template_data():
        """ """

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

    def __init__(self, features=None):
        super(Extensions, self).__init__()
        self.features = features
        self._extensions = None

    @property
    def extensions(self):
        """Lazy loading of extensions"""
        if self._extensions is None:
            self._extensions = self.list_all()
        if self.features is not None:
            return {
                name: self._extensions[name] for name in self.features if name in self._extensions
            }
        return self._extensions

    def __getattr__(self, attribute):
        """Return all matching extensions methods wrapped into a lambda"""
        # Unknown extension method
        if not hasattr(ExtMixin, attribute):
            return super(Extensions, self).__getattribute__(attribute)

        # Called outside a kard, doing nothing
        if not self.features:
            return lambda *args, **kw: ()

        def wrapper(*args, **kwargs):
            return [
                output[1]
                for output in map(
                    lambda ext: self._wrap_call(ext[0], ext[1], attribute, *args, *kwargs),
                    self.extensions.items(),
                )
                if output is not None
            ]

        return wrapper

    @staticmethod
    def _wrap_call(name, extension, method_name, *args, **kwargs):
        method = getattr(extension, method_name, None)
        base_method = getattr(ExtMixin, method_name, None)

        if method is None or method is base_method:
            # it is OK if an extension does not implement all methods
            return

        try:
            return (name, method(*args, **kwargs))
        except TimeoutError:
            write(
                'Extension "{}" raise timeout error, step "{}"'.format(extension.name, method_name)
            )
            raise
        except PkrException:
            # If this is a PkrException, we simply propagate it, and delegate its handling to the caller
            raise
        except Exception as exc:
            write(
                'Extension "{}" raise an unknown exception, step "{}": {}'.format(
                    extension.name, method_name, str(exc)
                )
            )
            raise

    def list(self):
        """Return the list of the extensions"""
        return self.extensions.keys()  # pylint: disable=dict-keys-not-iterating

    @classmethod
    def _get_extension_class(cls, module):
        for attr in dir(module):
            ext_cls = getattr(module, attr)
            try:
                if issubclass(ext_cls, ExtMixin) and ext_cls != ExtMixin:
                    return ext_cls
            except TypeError:
                pass

    @classmethod
    def list_all(cls):
        """Return the list of all available extensions"""
        # Load from pkr path
        extensions = {}
        for importer, package_name, _ in pkgutil.iter_modules(
            [str(get_pkr_path() / "extensions")]
        ):
            module = importer.find_module(package_name).load_module(package_name)
            extensions[package_name] = cls._get_extension_class(module)
        # Load from pkr_extensions entrypoints (and TO BE DEPRECATED extensions group)
        for entry in entry_points().get("pkr_extensions", ()) + entry_points().get(
            "extensions", ()
        ):
            if entry.name not in extensions:
                extensions[entry.name] = entry.load()
        return extensions

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
