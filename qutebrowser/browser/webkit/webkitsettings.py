# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Bridge from QWebSettings to our own settings.

Module attributes:
    ATTRIBUTES: A mapping from internal setting names to QWebSetting enum
                constants.
"""

from typing import cast
import os.path

from qutebrowser.qt import webkitwidgets, webkit, gui, core

from qutebrowser.config import config, websettings
from qutebrowser.config.websettings import AttributeInfo as Attr
from qutebrowser.utils import standarddir, urlutils
from qutebrowser.browser import shared


# The global WebKitSettings object
global_settings = cast('WebKitSettings', None)

parsed_user_agent = None


class WebKitSettings(websettings.AbstractSettings):

    """A wrapper for the config for QWebSettings."""

    _ATTRIBUTES = {
        'content.images':
            Attr(webkit.QWebSettings.WebAttribute.AutoLoadImages),
        'content.javascript.enabled':
            Attr(webkit.QWebSettings.WebAttribute.JavascriptEnabled),
        'content.javascript.can_open_tabs_automatically':
            Attr(webkit.QWebSettings.WebAttribute.JavascriptCanOpenWindows),
        'content.javascript.can_close_tabs':
            Attr(webkit.QWebSettings.WebAttribute.JavascriptCanCloseWindows),
        'content.javascript.clipboard':
            Attr(webkit.QWebSettings.WebAttribute.JavascriptCanAccessClipboard,
                 converter=lambda val: val != "none"),
        'content.plugins':
            Attr(webkit.QWebSettings.WebAttribute.PluginsEnabled),
        'content.webgl':
            Attr(webkit.QWebSettings.WebAttribute.WebGLEnabled),
        'content.hyperlink_auditing':
            Attr(webkit.QWebSettings.WebAttribute.HyperlinkAuditingEnabled),
        'content.local_content_can_access_remote_urls':
            Attr(webkit.QWebSettings.WebAttribute.LocalContentCanAccessRemoteUrls),
        'content.local_content_can_access_file_urls':
            Attr(webkit.QWebSettings.WebAttribute.LocalContentCanAccessFileUrls),
        'content.dns_prefetch':
            Attr(webkit.QWebSettings.WebAttribute.DnsPrefetchEnabled),
        'content.frame_flattening':
            Attr(webkit.QWebSettings.WebAttribute.FrameFlatteningEnabled),
        'content.cache.appcache':
            Attr(webkit.QWebSettings.WebAttribute.OfflineWebApplicationCacheEnabled),
        'content.local_storage':
            Attr(webkit.QWebSettings.WebAttribute.LocalStorageEnabled,
                 webkit.QWebSettings.WebAttribute.OfflineStorageDatabaseEnabled),
        'content.print_element_backgrounds':
            Attr(webkit.QWebSettings.WebAttribute.PrintElementBackgrounds),
        'content.xss_auditing':
            Attr(webkit.QWebSettings.WebAttribute.XSSAuditingEnabled),
        'content.site_specific_quirks.enabled':
            Attr(webkit.QWebSettings.WebAttribute.SiteSpecificQuirksEnabled),

        'input.spatial_navigation':
            Attr(webkit.QWebSettings.WebAttribute.SpatialNavigationEnabled),
        'input.links_included_in_focus_chain':
            Attr(webkit.QWebSettings.WebAttribute.LinksIncludedInFocusChain),

        'zoom.text_only':
            Attr(webkit.QWebSettings.WebAttribute.ZoomTextOnly),
        'scrolling.smooth':
            Attr(webkit.QWebSettings.WebAttribute.ScrollAnimatorEnabled),
    }

    _FONT_SIZES = {
        'fonts.web.size.minimum':
            webkit.QWebSettings.FontSize.MinimumFontSize,
        'fonts.web.size.minimum_logical':
            webkit.QWebSettings.FontSize.MinimumLogicalFontSize,
        'fonts.web.size.default':
            webkit.QWebSettings.FontSize.DefaultFontSize,
        'fonts.web.size.default_fixed':
            webkit.QWebSettings.FontSize.DefaultFixedFontSize,
    }

    _FONT_FAMILIES = {
        'fonts.web.family.standard': webkit.QWebSettings.FontFamily.StandardFont,
        'fonts.web.family.fixed': webkit.QWebSettings.FontFamily.FixedFont,
        'fonts.web.family.serif': webkit.QWebSettings.FontFamily.SerifFont,
        'fonts.web.family.sans_serif': webkit.QWebSettings.FontFamily.SansSerifFont,
        'fonts.web.family.cursive': webkit.QWebSettings.FontFamily.CursiveFont,
        'fonts.web.family.fantasy': webkit.QWebSettings.FontFamily.FantasyFont,
    }

    # Mapping from QWebSettings::QWebSettings() in
    # qtwebkit/Source/WebKit/qt/Api/qwebsettings.cpp
    _FONT_TO_QFONT = {
        webkit.QWebSettings.FontFamily.StandardFont: gui.QFont.StyleHint.Serif,
        webkit.QWebSettings.FontFamily.FixedFont: gui.QFont.StyleHint.Monospace,
        webkit.QWebSettings.FontFamily.SerifFont: gui.QFont.StyleHint.Serif,
        webkit.QWebSettings.FontFamily.SansSerifFont: gui.QFont.StyleHint.SansSerif,
        webkit.QWebSettings.FontFamily.CursiveFont: gui.QFont.StyleHint.Cursive,
        webkit.QWebSettings.FontFamily.FantasyFont: gui.QFont.StyleHint.Fantasy,
    }


def _set_user_stylesheet(settings):
    """Set the generated user-stylesheet."""
    stylesheet = shared.get_user_stylesheet().encode('utf-8')
    url = urlutils.data_url('text/css;charset=utf-8', stylesheet)
    settings.setUserStyleSheetUrl(url)


def _set_cookie_accept_policy(settings):
    """Update the content.cookies.accept setting."""
    mapping = {
        'all': webkit.QWebSettings.ThirdPartyCookiePolicy.AlwaysAllowThirdPartyCookies,
        'no-3rdparty': webkit.QWebSettings.ThirdPartyCookiePolicy.AlwaysBlockThirdPartyCookies,
        'never': webkit.QWebSettings.ThirdPartyCookiePolicy.AlwaysBlockThirdPartyCookies,
        'no-unknown-3rdparty': webkit.QWebSettings.ThirdPartyCookiePolicy.AllowThirdPartyWithExistingCookies,
    }
    value = config.val.content.cookies.accept
    settings.setThirdPartyCookiePolicy(mapping[value])


def _set_cache_maximum_pages(settings):
    """Update the content.cache.maximum_pages setting."""
    value = config.val.content.cache.maximum_pages
    settings.setMaximumPagesInCache(value)


def _update_settings(option):
    """Update global settings when qwebsettings changed."""
    global_settings.update_setting(option)

    settings = webkit.QWebSettings.globalSettings()
    if option in ['scrollbar.hide', 'content.user_stylesheets']:
        _set_user_stylesheet(settings)
    elif option == 'content.cookies.accept':
        _set_cookie_accept_policy(settings)
    elif option == 'content.cache.maximum_pages':
        _set_cache_maximum_pages(settings)


def _init_user_agent():
    global parsed_user_agent
    ua = webkitwidgets.QWebPage().userAgentForUrl(core.QUrl())
    parsed_user_agent = websettings.UserAgent.parse(ua)


def init():
    """Initialize the global QWebSettings."""
    cache_path = standarddir.cache()
    data_path = standarddir.data()

    webkit.QWebSettings.setIconDatabasePath(standarddir.cache())
    webkit.QWebSettings.setOfflineWebApplicationCachePath(
        os.path.join(cache_path, 'application-cache'))
    webkit.QWebSettings.globalSettings().setLocalStoragePath(
        os.path.join(data_path, 'local-storage'))
    webkit.QWebSettings.setOfflineStoragePath(
        os.path.join(data_path, 'offline-storage'))

    settings = webkit.QWebSettings.globalSettings()
    _set_user_stylesheet(settings)
    _set_cookie_accept_policy(settings)
    _set_cache_maximum_pages(settings)

    _init_user_agent()

    config.instance.changed.connect(_update_settings)

    global global_settings
    global_settings = WebKitSettings(webkit.QWebSettings.globalSettings())
    global_settings.init_settings()


def shutdown():
    """Disable storage so removing tmpdir will work."""
    webkit.QWebSettings.setIconDatabasePath('')
    webkit.QWebSettings.setOfflineWebApplicationCachePath('')
    webkit.QWebSettings.globalSettings().setLocalStoragePath('')
