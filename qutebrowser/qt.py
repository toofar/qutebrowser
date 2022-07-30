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
import os
from dataclasses import dataclass


@dataclass
class _Machinery:
    IS_QT6: bool
    IS_QT5: bool
    PACKAGE: str


PyQt5 = PyQt6 = False
try:
    import PyQt5 as pyqt  # type ignore # noqa: N813

    PyQt5 = True
    machinery = _Machinery(
        IS_QT6=False,
        IS_QT5=True,
        PACKAGE="PyQt5",
    )
except ImportError:
    import PyQt6 as pyqt  # type: ignore[no-redef] # noqa: N813

    PyQt6 = True
    machinery = _Machinery(
        IS_QT6=True,
        IS_QT5=False,
        PACKAGE="PyQt6",
    )

# While upstream recommends using PyQt5.sip ever since PyQt5 5.11, some distributions
# still package later versions of PyQt5 with a top-level "sip" rather than "PyQt5.sip".
try:
    if PyQt5:
        from PyQt5 import sip
    elif PyQt6:
        from PyQt6 import sip
except ImportError:
    import sip  # type: ignore[import]

# pylint: disable=ungrouped-imports
if PyQt5:
    from PyQt5 import QtCore as core
    from PyQt5 import QtDBus as dbus
    from PyQt5 import QtGui as gui
    from PyQt5 import QtNetwork as network
    from PyQt5 import QtPrintSupport as printsupport
    from PyQt5 import QtQml as qml
    from PyQt5 import QtSql as sql
    from PyQt5 import QtTest as test
    from PyQt5 import QtWidgets as widgets
    opengl = gui  # for QOpenGLVersionProfile
    gui.QFileSystemModel = widgets.QFileSystemModel
    del widgets.QFileSystemModel
elif PyQt6:
    from PyQt6 import QtCore as core
    from PyQt6 import QtDBus as dbus
    from PyQt6 import QtGui as gui
    from PyQt6 import QtNetwork as network
    from PyQt6 import QtPrintSupport as printsupport
    from PyQt6 import QtQml as qml
    from PyQt6 import QtSql as sql
    from PyQt6 import QtTest as test
    from PyQt6 import QtWidgets as widgets
    from PyQt6 import QtOpenGL as opengl

try:
    if os.environ.get("SKIP_WEBENGINE_IMPORT"):
        raise ImportError
    if PyQt5:
        from PyQt5 import QtWebEngineCore as webenginecore
        from PyQt5 import QtWebEngineWidgets as webenginewidgets
        # Some stuff moved from widgets to core in Qt6
        # fixme:mypy cannot follow these renamings and I can't seem to get it
        # to ignore the PyQt5 codepaths.
        for attr in [
            "QWebEngineSettings",
            "QWebEngineProfile",
            "QWebEngineDownloadItem",
            "QWebEnginePage",
            "QWebEngineCertificateError",
            "QWebEngineScript",
            "QWebEngineHistory",
            "QWebEngineHistoryItem",
            "QWebEngineScriptCollection",
            "QWebEngineClientCertificateSelection",
            "QWebEngineFullScreenRequest",
            "QWebEngineContextMenuData",
        ]:
            setattr(webenginecore, attr, getattr(webenginewidgets, attr))
            delattr(webenginewidgets, attr)
        webenginecore.QWebEngineDownloadRequest = getattr(  # noqa: B009
            webenginecore,
            "QWebEngineDownloadItem",
        )
        from PyQt5 import QtWebEngine
        for attr in [
            "PYQT_WEBENGINE_VERSION",
            "PYQT_WEBENGINE_VERSION_STR",
        ]:
            setattr(webenginecore, attr, getattr(QtWebEngine, attr))
            delattr(QtWebEngine, attr)
    elif PyQt6:
        from PyQt6 import QtWebEngineCore as webenginecore
        from PyQt6 import QtWebEngineWidgets as webenginewidgets
except ImportError:
    webenginecore = None
    webenginewidgets = None

try:
    if os.environ.get("SKIP_WEBKIT_IMPORT"):
        raise ImportError
    if PyQt5:
        from PyQt5 import QtWebKit as webkit
        from PyQt5 import QtWebKitWidgets as webkitwidgets
    elif PyQt6:
        webkit = None
        webkitwidgets = None
except ImportError:
    webkit = None
    webkitwidgets = None
