from __future__ import annotations

from typing import Callable

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
