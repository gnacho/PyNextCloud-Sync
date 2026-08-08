from __future__ import annotations

from html import escape

from pynextcloud_sync.util.i18n import _


MIT_LICENSE_TEXT = """MIT License

Copyright (c) 2026 EduhCommerce

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE."""


def terms_text() -> str:
    return _(
        "PyNextCloud Sync is an independent, unofficial third-party project. "
        "It is not affiliated with, sponsored by, endorsed by, maintained by, or "
        "otherwise connected to Nextcloud GmbH. Nextcloud is a registered trademark "
        "of Nextcloud GmbH.\n\n"
        "Bidirectional synchronization can upload, download, replace, conflict, or "
        "delete files on both the computer and the configured server. Use this "
        "software entirely at your own risk, test it with non-critical data, and "
        "maintain independent, restorable backups. The authors and contributors are "
        "not responsible for lost, corrupted, deleted, or otherwise damaged data.\n\n"
        "The application delegates file reconciliation and conflict handling to "
        "nextcloudcmd. Availability of notify_push and other server features depends "
        "on the Nextcloud installation. This release was tested with Nextcloud Hub 26 "
        "Spring (34.0.1) on Nextcloud AIO. Compatibility with other or future "
        "Nextcloud versions is not guaranteed.\n\n"
        "No telemetry, advertising, or usage tracking is included. Credentials are "
        "stored through the desktop Secret Service. Use of this software is also "
        "subject to the MIT License and its warranty disclaimer."
    )


def release_notes_markup() -> str:
    sections = [
        (
            _("Version 0.1.10"),
            [
                _("Added the native GNOME Keyring unlock prompt required after biometric desktop login."),
                _("Canceled unlocks now remain separate from invalid Nextcloud credentials without repeated automatic prompts."),
                _("File synchronization and notify_push resume together after the keyring is unlocked."),
                _("Interactive Debian upgrades now gracefully stop and restart a running application."),
            ],
        ),
        (
            _("Version 0.1.9"),
            [
                _("Published the corrected website, source, issue, and changelog links under the canonical repository."),
            ],
        ),
        (
            _("Version 0.1.8"),
            [
                _("Added native Files sidebar and desktop shortcuts for the synchronized folder."),
                _("Added a branded folder icon and settings for all three desktop integrations."),
                _("Removing the Files bookmark outside the application now updates Settings without recreating it."),
            ],
        ),
        (
            _("Version 0.1.7"),
            [
                _("Settings now opens independently from the tray without opening the main window."),
                _("The independent Settings window is released after closing to preserve the low-memory interface lifecycle."),
            ],
        ),
        (
            _("Version 0.1.6"),
            [
                _("Fixed opening Settings from the tray while the main window is closed."),
                _("Reduced background memory by creating the main interface only when needed and releasing it when closed."),
                _("Bounded command output, log display, activity history, and browser login polling."),
                _("Avoided unnecessary filesystem watcher and push connection reconfiguration."),
            ],
        ),
        (
            _("Version 0.1.5"),
            [
                _("Activity messages can now be expanded with one click and copied from a right-click menu."),
                _("Fixed Brazilian Portuguese loading and completed the application translation catalog."),
            ],
        ),
        (
            _("Version 0.1.4"),
            [
                _("Made the tray icon and details follow synchronization state changes live."),
                _("Added compatible StatusNotifierItem and D-Bus property change notifications."),
            ],
        ),
        (
            _("Version 0.1.3"),
            [
                _("Fixed the application icon displayed by GNOME tray hosts."),
                _("Added icon theme, absolute SVG, and pixel fallback support."),
            ],
        ),
        (
            _("Version 0.1.2"),
            [
                _("A more compact, responsive main window with a stable status header."),
                _("Collapsible recent activity with severity icons and single-line messages."),
                _("A working one-click tray menu and more reliable window presentation."),
                _("Optional daily log files with configurable retention."),
                _("Expanded About, legal terms, license, credits, and changelog information."),
                _("Fixed D-Bus menu variants, literal log rendering, and numeric log formatting."),
            ],
        ),
        (
            _("Version 0.1.1"),
            [
                _("Fixed GNOME Keyring compatibility for saving, reading, and removing credentials."),
                _("Moved Keyring operations away from the GTK main thread."),
            ],
        ),
        (
            _("Version 0.1.0"),
            [
                _("Initial development release with browser login, nextcloudcmd synchronization, inotify, timers, notify_push, exclusions, logs, and GNOME integration."),
            ],
        ),
    ]
    parts: list[str] = []
    for heading, entries in sections:
        parts.append(f"<p>{escape(heading)}</p>")
        parts.append("<ul>")
        parts.extend(f"<li>{escape(entry)}</li>" for entry in entries)
        parts.append("</ul>")
    return "".join(parts)
