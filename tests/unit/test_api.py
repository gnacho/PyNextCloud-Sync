from __future__ import annotations

import unittest
from typing import Any

from nextsync.nextcloud.api import NextcloudApi


class _FakeHttp:
    def __init__(self, status: int = 207, body: bytes = b"", error: Exception | None = None) -> None:
        self.status = status
        self.body = body
        self.error = error
        self.requests: list[dict[str, Any]] = []

    def request(self, method: str, url: str, callback: Any, **kwargs: Any) -> Any:
        self.requests.append({"method": method, "url": url, **kwargs})
        callback(self.status, self.body, self.error)
        return None


EMPTY_PROPFIND = b"""<?xml version="1.0"?>
<d:multistatus xmlns:d="DAV:" xmlns:s="http://sabredav.org/ns">
  <d:response>
    <d:href>/remote.php/dav/files/alice/</d:href>
    <d:propstat>
      <d:prop><d:resourcetype><d:collection/></d:resourcetype></d:prop>
      <d:status>HTTP/1.1 200 OK</d:status>
    </d:propstat>
  </d:response>
</d:multistatus>"""

POPULATED_PROPFIND = b"""<?xml version="1.0"?>
<d:multistatus xmlns:d="DAV:" xmlns:s="http://sabredav.org/ns">
  <d:response>
    <d:href>/remote.php/dav/files/alice/</d:href>
    <d:propstat><d:status>HTTP/1.1 200 OK</d:status></d:propstat>
  </d:response>
  <d:response>
    <d:href>/remote.php/dav/files/alice/Documents/</d:href>
    <d:propstat><d:status>HTTP/1.1 200 OK</d:status></d:propstat>
  </d:response>
  <d:response>
    <d:href>/remote.php/dav/files/alice/report.pdf</d:href>
    <d:propstat><d:status>HTTP/1.1 200 OK</d:status></d:propstat>
  </d:response>
</d:multistatus>"""

COLLECTIONS_PROPFIND = b"""<?xml version="1.0"?>
<d:multistatus xmlns:d="DAV:" xmlns:s="http://sabredav.org/ns">
  <d:response>
    <d:href>/remote.php/dav/files/alice/</d:href>
    <d:propstat>
      <d:prop><d:resourcetype><d:collection/></d:resourcetype></d:prop>
      <d:status>HTTP/1.1 200 OK</d:status>
    </d:propstat>
  </d:response>
  <d:response>
    <d:href>/remote.php/dav/files/alice/Documents/</d:href>
    <d:propstat>
      <d:prop><d:resourcetype><d:collection/></d:resourcetype></d:prop>
      <d:status>HTTP/1.1 200 OK</d:status>
    </d:propstat>
  </d:response>
  <d:response>
    <d:href>/remote.php/dav/files/alice/Photos/</d:href>
    <d:propstat>
      <d:prop><d:resourcetype><d:collection/></d:resourcetype></d:prop>
      <d:status>HTTP/1.1 200 OK</d:status>
    </d:propstat>
  </d:response>
  <d:response>
    <d:href>/remote.php/dav/files/alice/report.pdf</d:href>
    <d:propstat>
      <d:prop><d:resourcetype></d:resourcetype></d:prop>
      <d:status>HTTP/1.1 200 OK</d:status>
    </d:propstat>
  </d:response>
</d:multistatus>"""

SPECIAL_COLLECTIONS_PROPFIND = b"""<?xml version="1.0"?>
<d:multistatus xmlns:d="DAV:" xmlns:s="http://sabredav.org/ns">
  <d:response>
    <d:href>/remote.php/dav/files/alice/</d:href>
    <d:propstat>
      <d:prop><d:resourcetype><d:collection/></d:resourcetype></d:prop>
      <d:status>HTTP/1.1 200 OK</d:status>
    </d:propstat>
  </d:response>
  <d:response>
    <d:href>/remote.php/dav/files/alice/.hidden/</d:href>
    <d:propstat>
      <d:prop><d:resourcetype><d:collection/></d:resourcetype></d:prop>
      <d:status>HTTP/1.1 200 OK</d:status>
    </d:propstat>
  </d:response>
  <d:response>
    <d:href>/remote.php/dav/files/alice/files_trashbin/</d:href>
    <d:propstat>
      <d:prop><d:resourcetype><d:collection/></d:resourcetype></d:prop>
      <d:status>HTTP/1.1 200 OK</d:status>
    </d:propstat>
  </d:response>
  <d:response>
    <d:href>/remote.php/dav/files/alice/Documents/</d:href>
    <d:propstat>
      <d:prop><d:resourcetype><d:collection/></d:resourcetype></d:prop>
      <d:status>HTTP/1.1 200 OK</d:status>
    </d:propstat>
  </d:response>
</d:multistatus>"""


class ProbeRemoteTests(unittest.TestCase):
    def _probe(self, http: _FakeHttp, remote_path: str = "") -> tuple[bool, Exception | None]:
        api = NextcloudApi(http=http)
        result: list[tuple[bool, Exception | None]] = []

        def done(has_children: bool, error: Exception | None) -> None:
            result.append((has_children, error))

        api.probe_remote(
            "https://cloud.example.com",
            "alice",
            "secret",
            remote_path,
            done,
        )
        self.assertEqual(len(result), 1)
        return result[0]

    def test_empty_folder_returns_false(self) -> None:
        has_children, error = self._probe(_FakeHttp(207, EMPTY_PROPFIND))
        self.assertIsNone(error)
        self.assertFalse(has_children)

    def test_populated_folder_returns_true(self) -> None:
        has_children, error = self._probe(_FakeHttp(207, POPULATED_PROPFIND))
        self.assertIsNone(error)
        self.assertTrue(has_children)

    def test_uses_depth_one_and_no_bodies(self) -> None:
        http = _FakeHttp(207, EMPTY_PROPFIND)
        self._probe(http)
        self.assertEqual(len(http.requests), 1)
        request = http.requests[0]
        self.assertEqual(request["method"], "PROPFIND")
        self.assertIn("Depth", request["headers"])
        self.assertEqual(request["headers"]["Depth"], "1")
        self.assertIn("Authorization", request["headers"])
        self.assertTrue(request["url"].endswith("/remote.php/dav/files/alice/"))

    def test_remote_path_is_appended_to_the_folder(self) -> None:
        http = _FakeHttp(207, EMPTY_PROPFIND)
        self._probe(http, "/Documents")
        self.assertEqual(len(http.requests), 1)
        self.assertTrue(http.requests[0]["url"].endswith("/Documents/"))

    def test_http_error_surfaces(self) -> None:
        has_children, error = self._probe(_FakeHttp(500, b""))
        self.assertFalse(has_children)
        self.assertIsNotNone(error)

    def test_auth_rejection_surfaces_as_permission_error(self) -> None:
        has_children, error = self._probe(_FakeHttp(401, b""))
        self.assertIsInstance(error, PermissionError)

    def test_malformed_xml_surfaces(self) -> None:
        has_children, error = self._probe(_FakeHttp(207, b"not xml"))
        self.assertIsNotNone(error)
        self.assertFalse(has_children)


class ListRemoteFoldersTests(unittest.TestCase):
    def _list(self, http: _FakeHttp) -> tuple[list[str], Exception | None]:
        api = NextcloudApi(http=http)
        result: list[tuple[list[str], Exception | None]] = []

        def done(folders: list[str], error: Exception | None) -> None:
            result.append((folders, error))

        api.list_remote_folders(
            "https://cloud.example.com",
            "alice",
            "secret",
            done,
        )
        self.assertEqual(len(result), 1)
        return result[0]

    def test_returns_existing_top_level_folders_only(self) -> None:
        folders, error = self._list(_FakeHttp(207, COLLECTIONS_PROPFIND))
        self.assertIsNone(error)
        self.assertEqual(folders, ["/Documents", "/Photos"])

    def test_ignores_hidden_and_trash_collections(self) -> None:
        folders, error = self._list(_FakeHttp(207, SPECIAL_COLLECTIONS_PROPFIND))
        self.assertIsNone(error)
        self.assertEqual(folders, ["/Documents"])

    def test_empty_root_returns_no_folders(self) -> None:
        folders, error = self._list(_FakeHttp(207, EMPTY_PROPFIND))
        self.assertIsNone(error)
        self.assertEqual(folders, [])

    def test_auth_rejection_surfaces_as_permission_error(self) -> None:
        folders, error = self._list(_FakeHttp(401, b""))
        self.assertEqual(folders, [])
        self.assertIsInstance(error, PermissionError)

    def test_malformed_xml_surfaces_as_runtime_error(self) -> None:
        folders, error = self._list(_FakeHttp(207, b"not xml"))
        self.assertEqual(folders, [])
        self.assertIsInstance(error, RuntimeError)

    def test_probes_the_account_root_with_depth_one(self) -> None:
        http = _FakeHttp(207, COLLECTIONS_PROPFIND)
        self._list(http)
        self.assertEqual(len(http.requests), 1)
        request = http.requests[0]
        self.assertEqual(request["method"], "PROPFIND")
        self.assertEqual(request["headers"]["Depth"], "1")
        self.assertIn("Authorization", request["headers"])
        self.assertTrue(request["url"].endswith("/remote.php/dav/files/alice/"))


if __name__ == "__main__":
    unittest.main()
