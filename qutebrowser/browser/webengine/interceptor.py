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

"""A request interceptor taking care of adblocking and custom headers."""

from qutebrowser.config import websettings, config
from qutebrowser.browser import shared
from qutebrowser.utils import utils, log, debug, qtutils
from qutebrowser.extensions import interceptors
from qutebrowser.misc import objects
from qutebrowser.qt import webenginecore, core


class WebEngineRequest(interceptors.Request):

    """QtWebEngine-specific request interceptor functionality."""

    _WHITELISTED_REQUEST_METHODS = {core.QByteArray(b'GET'), core.QByteArray(b'HEAD')}

    def __init__(self, *args, webengine_info, **kwargs):
        super().__init__(*args, **kwargs)
        self._webengine_info = webengine_info
        self._redirected = False

    def redirect(self, url: core.QUrl, *, ignore_unsupported: bool = False) -> None:
        if self._redirected:
            raise interceptors.RedirectException("Request already redirected.")
        if self._webengine_info is None:
            raise interceptors.RedirectException("Request improperly initialized.")

        # Redirecting a request that contains payload data is not allowed.
        # To be safe, abort on any request not in a whitelist.
        verb = self._webengine_info.requestMethod()
        if verb not in self._WHITELISTED_REQUEST_METHODS:
            msg = (f"Request method {verb} for {self.request_url.toDisplayString()} "
                   "does not support redirection.")
            if ignore_unsupported:
                log.network.debug(msg)
                return
            raise interceptors.RedirectException(msg)

        self._webengine_info.redirect(url)
        self._redirected = True


class RequestInterceptor(webenginecore.QWebEngineUrlRequestInterceptor):
    """Handle ad blocking and custom headers."""

    def __init__(self, parent=None):
        super().__init__(parent)
        req_info = webenginecore.QWebEngineUrlRequestInfo.ResourceType
        resource_type = interceptors.ResourceType
        # This dict should be from QWebEngine Resource Types to qutebrowser
        # extension ResourceTypes. If a ResourceType is added to Qt, this table
        # should be updated too.
        self._resource_types = {
            req_info.ResourceTypeMainFrame: resource_type.main_frame,
            req_info.ResourceTypeSubFrame: resource_type.sub_frame,
            req_info.ResourceTypeStylesheet: resource_type.stylesheet,
            req_info.ResourceTypeScript: resource_type.script,
            req_info.ResourceTypeImage: resource_type.image,
            req_info.ResourceTypeFontResource: resource_type.font_resource,
            req_info.ResourceTypeSubResource: resource_type.sub_resource,
            req_info.ResourceTypeObject: resource_type.object,
            req_info.ResourceTypeMedia: resource_type.media,
            req_info.ResourceTypeWorker: resource_type.worker,
            req_info.ResourceTypeSharedWorker: resource_type.shared_worker,
            req_info.ResourceTypePrefetch: resource_type.prefetch,
            req_info.ResourceTypeFavicon: resource_type.favicon,
            req_info.ResourceTypeXhr: resource_type.xhr,
            req_info.ResourceTypePing: resource_type.ping,
            req_info.ResourceTypeServiceWorker: resource_type.service_worker,
            req_info.ResourceTypeCspReport: resource_type.csp_report,
            req_info.ResourceTypePluginResource: resource_type.plugin_resource,
            req_info.ResourceTypeUnknown: resource_type.unknown,
            req_info.ResourceTypeNavigationPreloadMainFrame: resource_type.preload_main_frame,
            req_info.ResourceTypeNavigationPreloadSubFrame: resource_type.preload_sub_frame,
        }

    def install(self, profile):
        """Install the interceptor on the given QWebEngineProfile."""
        profile.setUrlRequestInterceptor(self)

    def interceptRequest(self, info):
        """Handle the given request.

        Reimplementing this virtual function and setting the interceptor on a
        profile makes it possible to intercept URL requests.

        info contains the information about the URL request and will track
        internally whether its members have been altered.

        Args:
            info: QWebEngineUrlRequestInfo &info
        """
        if 'log-requests' in objects.debug_flags:
            resource_type_str = debug.qenum_key(
                webenginecore.QWebEngineUrlRequestInfo, info.resourceType()
            )
            navigation_type_str = debug.qenum_key(
                webenginecore.QWebEngineUrlRequestInfo, info.navigationType()
            )
            log.network.debug(
                "{} {}, first-party {}, resource {}, "
                "navigation {}".format(
                    bytes(info.requestMethod()).decode('ascii'),
                    info.requestUrl().toDisplayString(),
                    info.firstPartyUrl().toDisplayString(),
                    resource_type_str,
                    navigation_type_str,
                )
            )

        url = info.requestUrl()
        first_party = info.firstPartyUrl()
        if not url.isValid():
            log.network.debug("Ignoring invalid intercepted URL: {}".format(
                url.errorString()))
            return

        # Per QWebEngineUrlRequestInfo::ResourceType documentation, if we fail
        # our lookup, we should fall back to ResourceTypeUnknown
        try:
            resource_type = self._resource_types[info.resourceType()]
        except KeyError:
            log.network.warning(
                "Resource type {} not found in RequestInterceptor dict.".format(
                    debug.qenum_key(
                        webenginecore.QWebEngineUrlRequestInfo, info.resourceType()
                    )
                )
            )
            resource_type = interceptors.ResourceType.unknown

        is_xhr = (
            info.resourceType()
            == webenginecore.QWebEngineUrlRequestInfo.ResourceType.ResourceTypeXhr
        )

        if ((url.scheme(), url.host(), url.path()) ==
                ('qute', 'settings', '/set')):
            if first_party != core.QUrl('qute://settings/') or not is_xhr:
                log.network.warning("Blocking malicious request from {} to {}"
                                    .format(first_party.toDisplayString(),
                                            url.toDisplayString()))
                info.block(True)
                return

        # FIXME:qtwebengine only block ads for NavigationTypeOther?
        request = WebEngineRequest(
            first_party_url=first_party,
            request_url=url,
            resource_type=resource_type,
            webengine_info=info)

        interceptors.run(request)
        if request.is_blocked:
            info.block(True)

        for header, value in shared.custom_headers(url=url):
            if header.lower() == b'accept' and is_xhr:
                # https://developer.mozilla.org/en-US/docs/Web/API/XMLHttpRequest/setRequestHeader
                # says: "If no Accept header has been set using this, an Accept header
                # with the type "*/*" is sent with the request when send() is called."
                #
                # We shouldn't break that if someone sets a custom Accept header for
                # normal requests.
                continue
            info.setHttpHeader(header, value)

        if config.cache['content.headers.referer'] == 'never':
            info.setHttpHeader(b'Referer', b'')

        user_agent = websettings.user_agent(url)
        info.setHttpHeader(b'User-Agent', user_agent.encode('ascii'))
