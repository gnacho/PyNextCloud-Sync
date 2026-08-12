from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Callable
from urllib.parse import urlsplit

from .http import HttpClient, basic_authorization, parse_json


class NextcloudApi:
    def __init__(self, http: HttpClient | None = None) -> None:
        self.http = http or HttpClient()

    def validate_credentials(
        self,
        server: str,
        username: str,
        password: str,
        callback: Callable[[bool, str | None, Exception | None], None],
    ) -> None:
        url = f"{server.rstrip('/')}/ocs/v2.php/cloud/user?format=json"
        headers = {
            "Accept": "application/json",
            "OCS-APIREQUEST": "true",
            "Authorization": basic_authorization(username, password),
        }

        def done(status: int, body: bytes, error: Exception | None) -> None:
            if error:
                callback(False, None, error)
                return
            if status in {401, 403}:
                callback(False, None, PermissionError("The server rejected these credentials."))
                return
            if status < 200 or status >= 300:
                callback(False, None, RuntimeError(f"Nextcloud returned HTTP {status}."))
                return
            try:
                payload = parse_json(body)
                display_name = payload.get("ocs", {}).get("data", {}).get("display-name")
                callback(True, display_name, None)
            except Exception as exc:
                callback(False, None, RuntimeError(f"Invalid Nextcloud response: {exc}"))

        self.http.request("GET", url, done, headers=headers)

    def probe_remote(
        self,
        server: str,
        username: str,
        password: str,
        remote_path: str,
        callback: Callable[[bool, Exception | None], None],
    ) -> None:
        """Return whether the remote folder holds any entries, using a shallow
        WebDAV PROPFIND that downloads no file bodies.

        ``remote_path`` uses the normalized form from config (``""`` for the
        account root, otherwise ``/Documents``). A ``True`` result means the
        folder exists and has at least one child entry.
        """
        base = f"{server.rstrip('/')}/remote.php/dav/files/{username}"
        folder = f"{base}{remote_path.rstrip('/')}/"
        body = (
            b'<?xml version="1.0"?>'
            b'<d:propfind xmlns:d="DAV:"><d:prop><d:resourcetype/></d:prop></d:propfind>'
        )
        headers = {
            "Depth": "1",
            "Content-Type": "application/xml; charset=utf-8",
            "Authorization": basic_authorization(username, password),
        }

        def done(status: int, response: bytes, error: Exception | None) -> None:
            if error:
                callback(False, error)
                return
            if status in {401, 403}:
                callback(False, PermissionError("The server rejected these credentials."))
                return
            if status < 200 or status >= 300:
                callback(False, RuntimeError(f"Nextcloud returned HTTP {status}."))
                return
            try:
                tree = ET.fromstring(response)
            except ET.ParseError as exc:
                callback(False, RuntimeError(f"Invalid WebDAV response: {exc}"))
                return
            dav = "{DAV:}"
            folder_path = urlsplit(folder).path.rstrip("/")
            children = 0
            for element in tree.findall(f"{dav}response"):
                href = element.findtext(f"{dav}href", "")
                href_path = urlsplit(href).path.rstrip("/")
                if href_path == folder_path:
                    continue
                children += 1
            callback(children > 0, None)

        self.http.request(
            "PROPFIND",
            folder,
            done,
            headers=headers,
            body=body,
            content_type="application/xml; charset=utf-8",
        )

    def revoke_app_password(
        self,
        server: str,
        username: str,
        password: str,
        callback: Callable[[bool], None],
    ) -> None:
        url = f"{server.rstrip('/')}/ocs/v2.php/core/apppassword"
        headers = {
            "Accept": "application/json",
            "OCS-APIREQUEST": "true",
            "Authorization": basic_authorization(username, password),
        }

        def done(status: int, _body: bytes, _error: Exception | None) -> None:
            callback(200 <= status < 300)

        self.http.request("DELETE", url, done, headers=headers)
