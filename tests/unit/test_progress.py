from __future__ import annotations

import unittest

from nextsync.nextcloud.nextcloudcmd_progress import (
    describe_progress,
    parse_progress_line,
)


class ParseProgressLineTests(unittest.TestCase):
    def test_parses_download_line(self) -> None:
        progress = parse_progress_line("Downloading: /home/user/NextCloud/a.pdf")
        self.assertIsNotNone(progress)
        assert progress is not None
        self.assertEqual(progress.action, "download")
        self.assertEqual(progress.path, "/home/user/NextCloud/a.pdf")

    def test_parses_upload_line(self) -> None:
        progress = parse_progress_line("Uploading: docs/report.txt")
        self.assertIsNotNone(progress)
        assert progress is not None
        self.assertEqual(progress.action, "upload")
        self.assertEqual(progress.path, "docs/report.txt")

    def test_parses_delete_line(self) -> None:
        progress = parse_progress_line("Deleting: /tmp/NextCloud/old.odt")
        self.assertIsNotNone(progress)
        assert progress is not None
        self.assertEqual(progress.action, "delete")

    def test_parses_synced_line(self) -> None:
        progress = parse_progress_line("Synced  : /home/user/NextCloud/file.txt")
        self.assertIsNotNone(progress)
        assert progress is not None
        self.assertEqual(progress.action, "synced")
        self.assertEqual(progress.path, "/home/user/NextCloud/file.txt")

    def test_ignores_non_operation_lines(self) -> None:
        for line in (
            "",
            "  ",
            "Synchronizing folders",
            "Nextcloud synchronization completed",
            "Created journal: /tmp/foo/.sync.db",
            "exit 0",
            "14:22:03 [INFO] Database is ready",
        ):
            self.assertIsNone(parse_progress_line(line), f"should ignore: {line!r}")

    def test_ignores_unknown_actions(self) -> None:
        self.assertIsNone(parse_progress_line("Flurping: /tmp/file"))

    def test_processed_count_is_not_set_by_parser(self) -> None:
        progress = parse_progress_line("Downloading: /tmp/a")
        assert progress is not None
        self.assertEqual(progress.processed, 0)


class DescribeProgressTests(unittest.TestCase):
    def test_describe_includes_count_when_known(self) -> None:
        text = describe_progress(parse_progress_line("Downloading: /a.pdf"))
        self.assertIn("/a.pdf", text)

    def test_describe_none_is_empty(self) -> None:
        self.assertEqual(describe_progress(None), "")


if __name__ == "__main__":
    unittest.main()
