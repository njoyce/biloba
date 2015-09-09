"""
Extension support for biloba.

Define your module as biloba_foobar and import as ``biloba.ext.foobar``
"""

import sys


class ExtImporter(object):
    """
    This importer redirects imports from one module to another.
    """

    def __init__(self, module, wrapper):
        self.module = module
        self.wrapper = wrapper

        self.prefix = wrapper + '.'

    def __eq__(self, other):
        if self.__class__.__module__ != other.__class__.__module__:
            return False

        if self.__class__.__name__ != other.__class__.__name__:
            return False

        if self.module != other.module:
            return False

        if self.wrapper != other.wrapper:
            return False

        return True

    def __ne__(self, other):
        return not self.__eq__(other)

    def install(self):
        sys.meta_path[:] = [x for x in sys.meta_path if self != x] + [self]

    def find_module(self, full_name, path=None):
        """
        Called by the Python import subsystem to determine if this importer
        should handle the import of the module :ref:`full_name`.

        :param full_name: The full name of the module that is being imported.
        :param path: Unknown. Not used.
        :returns: The importer object that should handle the import or `None`
            if this importer should not handle the import.
        """
        if full_name.startswith(self.prefix):
            return self

    def load_module(self, full_name):
        """
        Called by the Python import subsystem when :ref:`find_module` returns
        True for `full_name`.

        :param full_name: The full name of the module that is being imported.
        :returns: The module that has been loaded to reference the module name
            supplied (full_name).
        """
        # guard against import weirdness
        if full_name in sys.modules:
            return sys.modules[full_name]

        # convert biloba.ext.* -> biloba_*

        mod_name = full_name[len(self.prefix):]

        real_mod_name = self.module.format(mod_name)

        try:
            __import__(real_mod_name)
        except ImportError:
            sys.modules.pop(real_mod_name, None)

            raise

        module = sys.modules[full_name] = sys.modules[real_mod_name]

        if '.' not in mod_name:
            setattr(sys.modules[self.wrapper], mod_name, module)

        return module


def setup():
    importer = ExtImporter('biloba_{}', __name__)  # noqa

    importer.install()


setup()

# remove these as they could be overridden by imported extensions
del setup, ExtImporter
