# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2018-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# This file is part of qutebrowser.
#
# qutebrowser is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# qutebrowser is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with qutebrowser.  If not, see <https://www.gnu.org/licenses/>.

"""Wrappers around Qt/PyQt code."""

# pylint: disable=unused-import

import sys
import importlib
from importlib.abc import Loader, MetaPathFinder
from importlib.machinery import ModuleSpec

try:
    import PyQt5 as pyqt
except ImportError:
    import PyQt6 as pyqt

# While upstream recommends using PyQt5.sip ever since PyQt5 5.11, some distributions
# still package later versions of PyQt5 with a top-level "sip" rather than "PyQt5.sip".
try:
    sip = importlib.import_module(f"{pyqt.__name__}.sip")
except ImportError:
    import sip  # type: ignore[import, no-redef]


class QuteProxyLoader(Loader):
    """Proxy loader that loads modules with an alternate prefix."""

    def __init__(self, our_prefix, their_prefix):
        self.our_prefix = our_prefix
        self.their_prefix = their_prefix

    def create_module(self, spec):
        submodule = spec.name[len(self.our_prefix):]
        return importlib.import_module(f"{self.their_prefix}{submodule}")

    def exec_module(self, module):
        pass


class QuteProxyFinder(MetaPathFinder):
    """
    Proxy finder to access modules via an alternate prefix.

    For example:
        >>> sys.meta_path.insert(0, QuteProxyFinder('qutesys', 'sys'))
        >>> import qutesys
        >>> qutesys
        <module 'sys' (built-in)>
        >>> qutesys.__spec__
        ModuleSpec(name='qutesys', loader=<__main__.QuteProxyLoader object at 0x7f8367ce1370>, origin='built-in')
        >>> id(sys) == id(qutesys)
        True

    Note that since we are returning an existing module with a new name this
    will overwrite the `__spec__` object of the module from the initial (real)
    load. (Implementation detail: we could swap it back in
    loader.exec_module().)
    This may break importlib.reload(), otherwise the module is still accessible
    at the old name just fine.
    """

    def __init__(self, our_prefix, their_prefix):
        assert our_prefix != their_prefix
        self.our_prefix = our_prefix
        self.their_prefix = their_prefix
        self._loader = QuteProxyLoader(self.our_prefix, self.their_prefix)

    def find_spec(self, fullname, path, target=None):
        if not fullname.startswith(self.our_prefix):
            return None

        submodule = fullname[len(self.our_prefix):]
        # Copy the spec of the module we will be proxying, also serves to
        # detect if the module we are going to be proxying exists.
        their_spec = importlib.util.find_spec(f"{self.their_prefix}{submodule}")
        if not their_spec:
            return None

        return ModuleSpec(
            name=f"{self.our_prefix}{submodule}",
            loader=self._loader,
            origin=their_spec.origin,
            is_package=their_spec.submodule_search_locations is not None,
            loader_state={"original_spec": their_spec},
        )


# Register our finder. For our case there probably shouldn't be contention
# over the package path so we don't strictly have to put our finer at the
# start of the list. But that seems to be the convention and we exit out fast
# for modules we don't know how to handle.
sys.meta_path.insert(0, QuteProxyFinder(__name__, pyqt.__name__))


#from pyqt import QtCore
#from pyqt import QtDBus
#from pyqt import QtGui
#from pyqt import QtNetwork
#from pyqt import QtPrintSupport
#from pyqt import QtQml
#from pyqt import QtSql
#from pyqt import QtWebEngine
#from pyqt import QtWebEngineCore
#from pyqt import QtWebEngineWidgets
#from pyqt import QtWebKit
#from pyqt import QtWebKitWidgets
#from pyqt import QtWidgets

#QtCore = importlib.import_module("PyQt5.QtCore", package="qutebrowser.qt")
#QtDBus = importlib.import_module("PyQt5.QtDBus")
#QtGui = importlib.import_module("PyQt5.QtGui")
#QtNetwork = importlib.import_module("PyQt5.QtNetwork")
#QtPrintSupport = importlib.import_module("PyQt5.QtPrintSupport")
#QtQml = importlib.import_module("PyQt5.QtQml")
#QtSql = importlib.import_module("PyQt5.QtSql")
#QtWidgets = importlib.import_module("PyQt5.QtWidgets")

#try:
#    QtWebEngine = importlib.import_module("PyQt5.QtWebEngine")
#    QtWebEngineCore = importlib.import_module("PyQt5.QtWebEngineCore")
#    QtWebEngineWidgets = importlib.import_module("PyQt5.QtWebEngineWidgets")
#except ImportError:
#    QtWebEngine = None
#    QtWebEngineCore = None
#    QtWebEngineWidgets = None
#
#try:
#    QtWebKit = importlib.import_module("PyQt5.QtWebKit")
#    QtWebKitWidgets = importlib.import_module("PyQt5.QtWebKitWidgets")
#except ImportError:
#    QtWebKit = None
#    QtWebKitWidgets = None

#common_submodules = [
#    'QtCore',
#    'QtDBus',
#    'QtGui',
#    'QtNetwork',
#    'QtPrintSupport',
#    'QtQml',
#    'QtSql',
#    'QtWidgets',
#]
#webengine_submodules = [
#    'QtWebEngine',
#    'QtWebEngineCore',
#    'QtWebEngineWidgets',
#]
#webkit_submodules = [
#    'QtWebKit',
#    'QtWebKitWidgets',
#]

#def fake_import(submodule):
#    spec = importlib.util.find_spec(f"PyQt5.{submodule}")
#    spec.name = f"{__name__}.{submodule}"
#    spec.loader.name = f"{__name__}.{submodule}"
#    print(f"Trying {spec.name}")
#    return importlib.util.module_from_spec(spec)
#
#for submodule in common_submodules:
#    globals()[submodule] = fake_import(submodule)
#
