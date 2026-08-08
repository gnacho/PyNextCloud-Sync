from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[2]


class PackagingTests(unittest.TestCase):
    def test_release_version_is_consistent_across_package_metadata(self) -> None:
        expected = "0.1.10"
        for relative_path in (
            "src/pynextcloud_sync/__init__.py",
            "pyproject.toml",
            "meson.build",
            "data/com.eduhcommerce.PyNextCloudSync.metainfo.xml",
            "packaging/debian/changelog",
            "CHANGELOG.md",
            "README.md",
            "README.pt-BR.md",
        ):
            contents = (ROOT / relative_path).read_text(encoding="utf-8")
            self.assertIn(expected, contents, relative_path)

    def test_maintainer_scripts_have_valid_shell_syntax(self) -> None:
        for name in ("preinst", "postinst", "postrm"):
            path = ROOT / "packaging" / "debian" / name
            subprocess.run(["sh", "-n", str(path)], check=True)

    def test_upgrade_requests_graceful_quit_and_restarts_in_user_session(self) -> None:
        preinst = (ROOT / "packaging/debian/preinst").read_text(encoding="utf-8")
        postinst = (ROOT / "packaging/debian/postinst").read_text(encoding="utf-8")
        build = (ROOT / "packaging/build-deb.sh").read_text(encoding="utf-8")
        source_build = (ROOT / "packaging/build-source-zip.sh").read_text(
            encoding="utf-8"
        )

        self.assertIn('gapplication action "$app_id" quit', preinst)
        self.assertIn("while app_is_running", preinst)
        self.assertNotIn("pkill", preinst)
        self.assertNotIn("kill -", preinst)
        self.assertIn("systemd-run --user", postinst)
        self.assertIn("pynextcloud-sync --background", postinst)
        self.assertIn('packaging/debian/preinst', build)
        self.assertIn('output_dir="$(cd "$output_dir" && pwd)"', source_build)


if __name__ == "__main__":
    unittest.main()
