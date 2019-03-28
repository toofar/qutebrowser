# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Generic settings status displayed in the statusbar."""

import functools

from PyQt5.QtCore import pyqtSlot, QUrl

from qutebrowser.config import config, configtypes
from qutebrowser.mainwindow.statusbar import textbase
from qutebrowser.utils import objreg, usertypes
from qutebrowser.browser.browsertab import WebTabError, shared


class BooleanSettings(textbase.TextBase):

    """Boolean settings state displayed in the statusbar."""

    config_option = 'statusbar.settings'

    def __init__(self, parent, win_id, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self._win_id = win_id
        # A dict of setting_name -> indicator mappings.
        self._config = {}
        self._parse_config()

    def _test_feature(self, setting_name):
        tab = self._current_tab()
        if not tab:
            raise WebTabError
        state = tab.permissions.test_feature(setting_name)
        return state == shared.FeatureState.granted

    def _to_bool(self, setting_name, url):
        """Return a bool for Bool and BoolAsk settings."""
        opt = config.instance.get_opt(setting_name)
        if not opt.supports_pattern:
            url = None
        obj = config.instance.get_obj(setting_name, url=url)
        if isinstance(opt.typ, configtypes.BoolAsk):
            try:
                return self._test_feature(setting_name)
            except WebTabError:
                return obj is True
        return obj

    def _parse_config(self):
        """Parse and apply settings from the config option."""
        self._config = config.instance.get(self.config_option)

        tab = self._current_tab()
        if tab:
            self.on_url_changed(tab.url())

    @functools.lru_cache(maxsize=256)
    def _text_for(self, url):
        parts = [
            indicator for setting, indicator in self._config.items()
            if self._to_bool(setting, url)
        ]
        return "[{}]".format(''.join(parts))

    @pyqtSlot(QUrl)
    def on_url_changed(self, url):
        """Update the widget to reflect settings for url."""
        if not self.isVisible():
            return
        if not url.isValid():
            url = None
        self.setText(self._text_for(url))

    def on_tab_changed(self, tab):
        """Update tab settings text when tab changed."""
        if not tab:
            # Probably some timing issue with tabs/windows closing down.
            return
        self.on_url_changed(tab.url())

    @pyqtSlot(usertypes.LoadStatus)
    def on_load_status_changed(self, _status):
        """Update widget when load status changed."""
        self.on_tab_changed(self._current_tab())

    def _current_tab(self):
        """Get the currently displayed tab."""
        window = objreg.get('tabbed-browser', scope='window',
                            window=self._win_id)
        return window.widget.currentWidget()

    def on_config_changed(self, option):
        """Update the widget when the config changes."""
        self._text_for.cache_clear()
        if option == self.config_option:
            self._parse_config()
        elif option in self._config:
            self.on_tab_changed(self._current_tab())

    @pyqtSlot(str, shared.FeatureState)
    def on_feature_permission_changed(self, option, _state):
        """Update the widget when a pages feature permissions change."""
        if option in self._config:
            self._text_for.cache_clear()
            self.on_tab_changed(self._current_tab())
