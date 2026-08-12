from __future__ import annotations

from html import escape

from pynextcloud_sync.util.i18n import _


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
        "subject to the GNU General Public License version 3 or later and its "
        "warranty disclaimer."
    )


def release_notes_markup() -> str:
    sections = [
        (
            _("Version 3.0.0"),
            [
                _("Thin-wrapper redesign: the bootstrap staging, safety baseline, run markers, and deletion guard are removed. nextcloudcmd now owns synchronization, conflict resolution, and safety."),
                _("The config schema bumps from v4 to v5 and drops the safety fields automatically; leftover staging trees are removed and legacy safety manifests are archived on first run after upgrade."),
                _("A first-sync confirmation dialog appears before the initial run when the local folder, the remote folder, or both are empty, probing the remote side with a shallow WebDAV PROPFIND."),
                _("A new view with Recent activity and conflicted copies lists the files nextcloudcmd preserves as '* (Nextcloud conflicted copy <date>).*' with Keep Local, Keep Remote, and Open in Files actions."),
                _("A lightweight deletion guard blocks synchronization before nextcloudcmd starts when a large share of previously known local files disappears, with Keep Paused, Restore from Nextcloud, or Approve These Deletions Once."),
                _("The account view and tray tooltip now show the current file and processed count during a sync, falling back to the state label when the engine emits no per-file output."),
            ],
        ),
        (
            _("Version 2.1.0"),
            [
                _("Added an optional Remote Folder field to the setup wizard so an account can mirror a specific Nextcloud folder instead of the entire account root."),
                _("When a remote folder is configured, the --path argument is passed to nextcloudcmd; leaving the field as / keeps the previous root-to-root behaviour."),
                _("Existing configurations migrate transparently to schema version 4 with the remote path defaulting to the account root."),
                _("Two accounts against the same server, user, and local folder but different remote folders are now treated as distinct accounts."),
            ],
        ),
        (
            _("Version 2.0.0"),
            [
                _("Added support for multiple Nextcloud accounts, each with its own synchronization, safety, and runtime settings."),
                _("Existing single-account configurations are migrated automatically on first launch."),
                _("The main window now has an accounts sidebar and a per-account status and activity panel."),
                _("The tray shows an aggregated state and per-account actions for syncing, opening, and pausing."),
                _("Synchronizations are serialized across accounts so concurrent reconciliations do not saturate the network."),
            ],
        ),
        (
            _("Version 0.1.19"),
            [
                _("Relicensed PyNextCloud Sync under the GNU General Public License version 3 or later."),
                _("About now identifies and displays the GPLv3 license using GTK's native license presentation."),
                _("Updated project, Debian, AppStream, documentation, terms, and translation metadata to consistently identify the new license."),
            ],
        ),
        (
            _("Version 0.1.18"),
            [
                _("Recovered explicitly from Linux inotify queue overflow by rebuilding filesystem monitoring and requesting a protected nextcloudcmd reconciliation."),
                _("Added a durable marker around nextcloudcmd that is cleared only after a successful safety baseline commit."),
                _("Retained the previous last-known-good safety baseline after interrupted runs."),
            ],
        ),
        (
            _("Version 0.1.17"),
            [
                _("Automatic update notices now wait until the main window is fully mapped before they are created."),
                _("Update windows are no longer reassociated after becoming visible, preventing placement on another monitor at the desktop origin."),
                _("Mandatory updates now show only Download New Version and Close Application."),
            ],
        ),
        (
            _("Version 0.1.16"),
            [
                _("The update notice now remains above the main window when the application is opened from its launcher."),
                _("Download and dismissal actions remain visible above the scrollable release details."),
                _("Download New Version now opens the latest GitHub release directly."),
                _("Mandatory updates use an urgent warning presentation and keep Not Now disabled."),
            ],
        ),
        (
            _("Version 0.1.15"),
            [
                _("Added automatic startup update checks through a validated GitHub version manifest."),
                _("Optional updates remain non-blocking, while mandatory updates prevent the synchronization runtime from starting."),
                _("Added a manual update check in About, semantic version comparison, safe failure handling, and UTC release dates."),
                _("The update window now shows a short summary and an expandable full changelog."),
            ],
        ),
        (
            _("Version 0.1.14"),
            [
                _("Added a protected first synchronization with a fresh isolated server snapshot and an explicit merge review."),
                _("Existing synchronization databases are archived and never silently reused during initialization."),
                _("Added a persistent safety baseline that blocks missing, replaced, empty, unreadable, or abnormally reduced local folders before nextcloudcmd starts."),
                _("Added safe recovery, one-time deletion approval, preserved conflict copies, and configurable review thresholds."),
            ],
        ),
        (
            _("Version 0.1.13"),
            [
                _("The default GNOME password collection is now unlocked before searching for the Nextcloud credential after biometric login."),
                _("A locked Login collection is no longer misreported as a missing stored credential during desktop autostart."),
                _("Added diagnostic logging and a regression test for credentials hidden while the keyring is locked."),
            ],
        ),
        (
            _("Version 0.1.12"),
            [
                _("Fixed Debian upgrade detection by querying the live D-Bus owner instead of treating list-apps as a process list."),
                _("The package now confirms that the old instance has exited before replacing application files."),
                _("Replaced the inaccurate package-upgrade fixture with a regression test that matches the real GLib behavior."),
            ],
        ),
        (
            _("Version 0.1.11"),
            [
                _("Fixed detection of running application instances during Debian upgrades when APT/dpkg does not preserve SUDO_UID."),
                _("Upgrades now stop and restart the application through its real per-user D-Bus session."),
                _("Added an executable regression test for graceful package-upgrade shutdown and restart."),
            ],
        ),
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
