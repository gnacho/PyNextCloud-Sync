from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).parents[2]

APP_SOURCE = ROOT / "src" / "nextsync" / "application.py"
UI_SOURCES = sorted((ROOT / "src" / "nextsync" / "ui").glob("*.py"))

# These are the widgets the issue reported: primary actions that must follow
# the system accent color instead of a fixed brand blue. Each entry maps the
# source file to one or more code fragments that create the accent-colored
# button. Libadwaita applies the system accent to `suggested-action` and to
# `Adw.ResponseAppearance.SUGGESTED` alert responses by default.
ACCENT_WIDGET_FRAGMENTS: dict[str, list[str]] = {
    "main_window.py": ['css_classes=["suggested-action", "pill"]'],
    "setup.py": [
        'css_classes=["suggested-action"]',
        'css_classes=["suggested-action", "pill"]',
    ],
    "settings.py": ['css_classes=["suggested-action"]'],
    "conflict_resolver.py": ['css_classes=["suggested-action"]'],
    "update_window.py": ['add_css_class("suggested-action")'],
}

DIALOG_SUGGESTED_FRAGMENTS: dict[str, list[str]] = {
    "application.py": ["Adw.ResponseAppearance.SUGGESTED"],
    "main_window.py": ["Adw.ResponseAppearance.SUGGESTED"],
    "setup.py": ["Adw.ResponseAppearance.SUGGESTED"],
    "settings.py": ["Adw.ResponseAppearance.SUGGESTED"],
}

# Brand blue lives only in the application icon, never in widget code. The icon
# is out of scope for the accent fix: it is an image, not a styled button.
BRAND_BLUE = "#0082C8"


class UiAccentContractTests(unittest.TestCase):
    def test_application_is_an_adwaita_application(self) -> None:
        source = APP_SOURCE.read_text(encoding="utf-8")
        self.assertIn("class NextSyncApplication(Adw.Application)", source)
        self.assertIn("Adw.Application.do_startup", source)
        self.assertIn("Adw.Application.do_shutdown", source)

    def test_no_css_provider_overrides_widget_styling(self) -> None:
        forbidden = (
            "CssProvider",
            "load_from_string",
            "load_from_file",
            "add_provider_for_display",
        )
        for path in (APP_SOURCE, *UI_SOURCES):
            source = path.read_text(encoding="utf-8")
            for token in forbidden:
                self.assertNotIn(
                    token,
                    source,
                    f"{path.name} must not inject custom CSS that could "
                    f"override the system accent ({token})",
                )

    def test_no_hardcoded_widget_colors_in_the_ui(self) -> None:
        for path in (APP_SOURCE, *UI_SOURCES):
            source = path.read_text(encoding="utf-8")
            self.assertNotIn(
                BRAND_BLUE,
                source,
                f"{path.name} must not hardcode the brand color in widgets",
            )

    def test_primary_buttons_use_suggested_action(self) -> None:
        for filename, fragments in ACCENT_WIDGET_FRAGMENTS.items():
            source = (ROOT / "src" / "nextsync" / "ui" / filename).read_text(
                encoding="utf-8"
            )
            for fragment in fragments:
                self.assertIn(
                    fragment,
                    source,
                    f"{filename} primary buttons must use suggested-action "
                    f"(missing: {fragment})",
                )

    def test_dialog_primary_responses_are_suggested(self) -> None:
        for filename, fragments in DIALOG_SUGGESTED_FRAGMENTS.items():
            if filename == "application.py":
                path = ROOT / "src" / "nextsync" / filename
            else:
                path = ROOT / "src" / "nextsync" / "ui" / filename
            source = path.read_text(encoding="utf-8")
            for fragment in fragments:
                self.assertIn(
                    fragment,
                    source,
                    f"{filename} primary dialog responses must be SUGGESTED "
                    f"(missing: {fragment})",
                )


if __name__ == "__main__":
    unittest.main()
