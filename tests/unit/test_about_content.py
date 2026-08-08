from __future__ import annotations

import unittest
import xml.etree.ElementTree as ET

from pynextcloud_sync.ui.about_content import MIT_LICENSE_TEXT, release_notes_markup, terms_text


class AboutContentTests(unittest.TestCase):
    def test_release_notes_are_valid_appstream_xml(self) -> None:
        root = ET.fromstring(f"<description>{release_notes_markup()}</description>")
        self.assertGreater(len(root.findall("p")), 0)
        self.assertGreater(len(root.findall("ul")), 0)

    def test_legal_texts_are_complete(self) -> None:
        self.assertIn("MIT License", MIT_LICENSE_TEXT)
        self.assertIn("No telemetry", terms_text())
        self.assertIn("lost, corrupted, deleted", terms_text())
        self.assertIn("future Nextcloud versions is not guaranteed", terms_text())


if __name__ == "__main__":
    unittest.main()
