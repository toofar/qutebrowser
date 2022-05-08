# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Customized QWebInspector for QtWebEngine."""

from qutebrowser.qt import widgets, webenginewidgets
from qutebrowser.qt import webenginecore

from qutebrowser.browser import inspector
from qutebrowser.browser.webengine import webenginesettings, webview
from qutebrowser.misc import miscwidgets
from qutebrowser.utils import version, usertypes, qtutils
from qutebrowser.keyinput import modeman


class WebEngineInspectorView(webenginewidgets.QWebEngineView):

    """The QWebEngineView used for the inspector.

    We don't use a qutebrowser WebEngineView because that has various
    customization which doesn't apply to the inspector.
    """

    def createWindow(self,
                     wintype: webenginecore.QWebEnginePage.WebWindowType) -> webenginewidgets.QWebEngineView:
        """Called by Qt when a page wants to create a new tab or window.

        In case the user wants to open a resource in a new tab, we use the
        createWindow handling of the main page to achieve that.

        See WebEngineView.createWindow for details.
        """
        inspected_page = self.page().inspectedPage()
        try:
            # Qt 5
            return inspected_page.view().createWindow(wintype)
        except AttributeError:
            # Qt 6
            newpage = inspected_page.createWindow(wintype)
            return webview.WebEngineView.forPage(newpage)


class WebEngineInspector(inspector.AbstractWebInspector):

    """A web inspector for QtWebEngine with Qt API support."""

    def __init__(self, splitter: miscwidgets.InspectorSplitter,
                 win_id: int,
                 parent: widgets.QWidget = None) -> None:
        super().__init__(splitter, win_id, parent)
        self._check_devtools_resources()
        self._settings = None

    def _on_window_close_requested(self) -> None:
        """Called when the 'x' was clicked in the devtools."""
        modeman.leave(
            self._win_id,
            usertypes.KeyMode.insert,
            'devtools close requested',
            maybe=True,
        )
        self.hide()

    def _check_devtools_resources(self) -> None:
        """Make sure that the devtools resources are available on Fedora.

        Fedora packages devtools resources into its own package. If it's not
        installed, we show a nice error instead of a blank inspector.
        """
        dist = version.distribution()
        if dist is None or dist.parsed != version.Distribution.fedora:
            return

        data_path = qtutils.library_path(qtutils.LibraryPath.data)
        pak = data_path / 'resources' / 'qtwebengine_devtools_resources.pak'
        if not pak.exists():
            raise inspector.Error("QtWebEngine devtools resources not found, "
                                  "please install the qt5-qtwebengine-devtools "
                                  "Fedora package.")

    def inspect(self, page: webenginecore.QWebEnginePage) -> None:  # type: ignore[override]
        if not self._widget:
            view = WebEngineInspectorView()
            inspector_page = webenginecore.QWebEnginePage(
                page.profile(),
                self
            )
            inspector_page.windowCloseRequested.connect(  # type: ignore[attr-defined]
                self._on_window_close_requested)
            view.setPage(inspector_page)
            self._settings = webenginesettings.WebEngineSettings(view.settings())
            self._set_widget(view)

        inspector_page = self._widget.page()
        assert inspector_page.profile() == page.profile()

        inspector_page.setInspectedPage(page)
        self._settings.update_for_url(inspector_page.requestedUrl())

    def _needs_recreate(self) -> bool:
        """Recreate the inspector when detaching to a window.

        WORKAROUND for what's likely an unknown Qt bug.
        """
        return True
