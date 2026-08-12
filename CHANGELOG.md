# Changelog

## 0.2.6 — 2026-08-13

### White tray glyphs, remote folder picker from the server

- **Tray icon renders in white**: the Lucide `cloud`/`cloud-off` glyphs now use a fixed white stroke, so the tray host draws the exact design in white on the panel instead of black or a wrong color. Transparent background preserved.
- **Remote folder picker**: the Add Folder dialog lists the remote folders that already exist on the server (via WebDAV PROPFIND), so you can pick one instead of typing a path.
- **Blank remote folder auto-names**: leaving the remote folder field empty now creates a remote folder with the same name as the local folder (e.g. `/home/user/NextCloud` → `/NextCloud`); an explicit `/` still maps to the account root.

## 0.2.5 — 2026-08-13

### Settings finally opens (two crashes fixed), Lucide icons, monochrome tray

- **Settings now opens.** Two bugs kept it closed: `SettingsWindow` received an `AccountRuntime` that did not expose the attributes it reads (`push_message`, `push_state`, `watched_directories`, `reconfigure`, `logger`), and the legacy config view never copied `delete_guard` into `config.data`, so building the window raised `AttributeError`/`KeyError`. Both fixed. You can now open Settings, add sync folders, and actually synchronize.
- **Settings and About buttons** use the Lucide `settings-2` and `info` icons, matching the unified Lucide icon set.
- **Monochrome transparent tray icon**: the Lucide `cloud` glyph on a transparent background, published as an ARGB pixmap so the tray host renders it identically and never black (`cloud-off` when no account is configured).

## 0.2.4 — 2026-08-12

### Settings for zero-folder accounts, tray polish, Lucide icons

- **Settings opens for accounts with no sync folders** (fixes the silent no-op): desktop-integration switches are hidden when there is no folder, and the Synchronization Folders group (with Add Folder) is always shown.
- **Themed tray icon**: the tray publishes a bare symbolic icon name resolved through the icon theme, so it follows the theme instead of rendering black.
- **Trimmed tray menu**: now only Open NextSync, Settings, and Quit; the per-account submenu and redundant actions were removed.
- **Lucide-unified icons**: the folder and symbolic SVGs now derive from the Lucide icon set like the rest.

## 0.2.3 — 2026-08-12

### Fix: main window on libadwaita 1.6+

- Fixed a silent crash that prevented the main window from opening on
  libadwaita 1.6+: `Adw.NavigationSplitView` now receives `NavigationPage`
  objects for the sidebar and content instead of the removed
  `sidebar=`/`content=` keyword form.

## 0.2.2 — 2026-08-12

### Fix: zero-folder accounts, Add Folder row, Spanish

- Fixed a crash when an account has no sync folders: the tray and account controls now use a neutral scheduler instead of dereferencing `None`.
- Fixed the **Add Folder** row in the setup wizard: it is now inside a `ListBox` so the action actually opens the folder dialog.
- Aggregated account state now exposes sync progress to the tray.
- Spanish translations added for the folder UI and account states.

## 0.2.1 — 2026-08-12

### Fix: folder picker default location

- The folder picker no longer forces a hardcoded initial path (`~/NextCloud`). It opens at the file chooser's default location unless the pre-filled path is an existing directory, matching the file chooser behavior of the official client.

## 0.2.0 — 2026-08-12

### Multiple sync folders per account

- Accounts now hold a **list of sync folders** instead of a single pair. Each folder maps a local root to an optional remote path and runs its own synchronization, inotify watch, deletion guard, exclusions, and `nextcloudcmd` invocation, sharing the account's sync settings.
- The setup wizard lets you **finish the login without choosing any folder**, matching the official Nextcloud client; folders can be added later from Settings.
- The account view lists every sync folder, and Settings gains **Add Folder / Remove Folder** actions.
- Config schema bumps to **v6**: the single `local_root`/`remote_path` pair migrates automatically into the `folders` list, and the account identity no longer depends on the folder.
- **Note:** desktop integrations (Files bookmark, Desktop shortcut, folder icon) and the conflict resolver currently apply to the first folder of the active account; per-folder integration for every folder is a future refinement.

## 0.1.0 — 2026-08-12

### Fork of PyNextCloud-Sync, renamed to NextSync

- This release is a full fork of [`PyNextCloud-Sync`](https://github.com/ehstbr/PyNextCloud-Sync) by ehstbr, renamed to **NextSync**. The application, the Python module, the binary, the app ID, the icons, and the packaging were renamed accordingly (`pynextcloud_sync` → `nextsync`, app ID `com.eduhcommerce.PyNextCloudSync` → `io.github.gnacho.nextsync`).
- Thanks to ehstbr for the original project and the permissive GPL-3.0-or-later licensing that makes this fork possible.
- Versioning restarts at 0.1.0 for the fork; each release adds +0.1.

### Thin-wrapper redesign

- Remove the protected-initialization subsystem (`core/bootstrap.py`,
  `ui/bootstrap.py`, `core/safety.py`, `core/sync_run_marker.py`): no staging
  tree, no three-run merge, no SHA-256 sweep, no deletion guard. `nextcloudcmd`
  now owns synchronization, conflict resolution, and safety.
- Bump the config schema from v4 to v5. The safety fields
  (`bootstrap_complete`, `bootstrap_completed_at`, `guard_enabled`,
  `deletion_count_threshold`, `deletion_percent_threshold`) are dropped from
  every account automatically. Accounts that were stuck mid-bootstrap sync
  immediately on upgrade.
- On first run after upgrade, leftover `protected-*` staging trees under
  `~/.local/state/nextsync/bootstrap/` are removed and legacy safety
  manifests are archived under `safety-archives/legacy-<ISO>/`.
- Remove the `SAFETY_REVIEW` state, the safety review dialog, and the
  "Deletion Safety Guard" settings group.

### New features

- **First-sync confirmation:** before the first `nextcloudcmd` run for a newly
  configured account, the app probes the local folder and the remote folder
  (shallow WebDAV PROPFIND, Depth 1, no bodies) and asks the user to confirm
  when the local side, the remote side, or both are empty, with wording adapted
  to download/upload/merge.
- **Conflicted-copy resolver:** a window with two tabs — Recent (the live
  synchronization log) and Conflicts — lists the files the engine preserves as
  `* (Nextcloud conflicted copy <date>).*`, with Keep Local, Keep Remote, and
  Open in Files actions. It only scans the local folder and never runs
  `nextcloudcmd`.
- **Deletion guard:** before each sync the app compares the local folder against
  a per-account baseline of file paths and blocks synchronization when a large
  share of previously known files disappears, with Keep Paused / Restore from
  Nextcloud / Approve These Deletions Once. This restores the protection that
  the CLI engine does not provide (its confirmation dialog is GUI-only).
- **Live progress:** a defensive parser surfaces `nextcloudcmd` per-file lines
  (download/upload/delete/conflict) as the current file plus a processed count
  in the account view and the tray tooltip during a sync, falling back to the
  existing state label when the engine emits no per-file output.

### Removed behaviour

- The review/merge window with merge policies no longer exists; the engine
  applies its own conflict policy and leaves `* (Nextcloud conflicted copy
  <date>).*` files in the user's folder.

## 2.1.0 — 2026-08-11

- Add an optional Remote Folder field to the setup wizard so an account mirrors
  a specific Nextcloud folder instead of the entire account root.
- Pass `--path` to `nextcloudcmd` when a remote folder is configured; the account
  root (`/`) is used when the field is left blank.
- Bump the config schema to version 4. Existing single-account and multi-account
  configurations migrate transparently, defaulting the remote path to the
  account root (no behaviour change).
- Account identities now include the remote path, so two accounts against the
  same server, user, and local folder but different remote folders are treated
  as distinct.
- Surface the chosen remote folder in the setup summary and the in-memory
  account metadata so users can review the mapping before the safety baseline
  runs.

## 2.0.0 — 2026-08-11

- Add support for multiple Nextcloud accounts, each with its own
  synchronization, safety, and runtime settings.
- Migrate existing single-account configurations to the multi-account schema
  automatically on first launch.
- Add an accounts sidebar and a per-account status, activity, and
  synchronization panel to the main window.
- Serialize reconciliations across accounts through a global gate so concurrent
  `nextcloudcmd` runs do not saturate the network.
- Name synchronization failure and safety notifications per account.
- Extend the tray with a per-account submenu for Sync Now, Open Folder, and
  Pause actions.
- Extract the local-change debounce and post-sync cooldown into a small,
  independently tested component.

## 0.1.19 — 2026-08-11

- Relicensed NextSync under the GNU General Public License version 3
  or later.
- Replaced the custom MIT text in About with GTK's native GPLv3 license
  presentation.
- Updated Python, Debian, AppStream, documentation, terms, third-party notices,
  and translation metadata to identify the new license consistently.
- No synchronization, safety, authentication, update-checking, or desktop
  integration behavior was changed.

## 0.1.18 — 2026-08-10

- Detect Linux `IN_Q_OVERFLOW` explicitly. When the inotify queue loses events,
  discard trust in that event stream, rebuild the watcher, and request one
  protected normal reconciliation through `nextcloudcmd`.
- Add a minimal durable run marker before starting `nextcloudcmd`; clear it only
  after a successful run has produced and persisted a new safety baseline.
- If the wrapper is killed or otherwise interrupted, keep using the previous
  last-known-good baseline on restart. Existing folder identity, empty-tree,
  missing-database, and abnormal-deletion checks still run before `nextcloudcmd`.
- Keep the marker when the post-sync baseline cannot be committed instead of
  silently treating the wrapper state as fully recorded.
- Persist the safety manifest with a directory `fsync` after the atomic replace.
- Do not add a custom rescan, WebDAV diff, conflict resolver, transaction
  journal, or synchronization algorithm. File discovery, transfer, conflict
  handling, and deletion propagation remain the responsibility of `nextcloudcmd`.

## 0.1.17 — 2026-08-09

- Fixed automatic update notices opening on another monitor at the desktop
  origin when the application was launched normally.
- Startup notices now wait for the main window to be fully mapped and one UI
  cycle to complete before being created with that window as their transient
  parent, matching the correctly centered manual-check behavior.
- Removed the unsafe fallback that changed a visible update window's transient
  parent. A notice created during tray-only startup is recreated after the main
  window maps instead.
- Mandatory updates now show only **Download New Version** and
  **Close Application**. **Not Now** remains available only for optional
  updates.
- Added executable lifecycle tests for unmapped, already mapped, replaced, and
  temporarily unmapped parent windows.

## 0.1.16 — 2026-08-09

- Kept the update window above the main application window by assigning the
  visible application window as its transient parent and presenting the notice
  again after GTK completes a launcher activation.
- Moved the primary actions into a fixed hero area above the scrollable version
  details and changelog, so downloading or dismissing an optional update never
  requires scrolling.
- Renamed the main action to **Download New Version** and changed its fixed,
  trusted destination to the latest release page.
- Made mandatory notices visibly urgent with a warning icon and the explicit
  **Mandatory update available** heading.
- Mandatory notices keep **Not Now** visible but disabled, while preserving the
  required **Download New Version** and **Close Application** actions.

## 0.1.15 — 2026-08-09

- Added `version.json` at the repository root with a schema version, latest
  application version, mandatory-update flag, plain-text summary, and an ISO
  8601 release timestamp in UTC. A separate plain-text changelog list feeds an
  expandable release-details section in the update window.
- Added an automatic check at every process startup. The synchronization
  runtime, `inotify`, timers, and `notify_push` remain inactive until the check
  confirms that the installed version is not blocked.
- Optional updates open a detailed, non-modal window while normal application
  initialization continues. Mandatory updates prevent the application runtime
  from starting and offer only the official Releases page or application exit.
- The custom Libadwaita window presents the short summary immediately and keeps
  the complete per-release changelog in a native collapsed expander row.
- Added the same manual check to About, with clear results for available,
  current, unreachable, and invalid-manifest states.
- Added strict SemVer comparison, including prerelease precedence, without
  string-based version ordering.
- Added bounded downloads, strict JSON and UTC date validation, an eight-second
  network timeout, no-cache requests, and fail-open startup behavior when
  GitHub is unavailable.

## 0.1.14 — 2026-08-08

- Replaced automatic first synchronization with a protected initialization
  review. A completely new private staging folder obtains the server snapshot,
  so a stale `.sync_*.db` in the selected local folder is never reused.
- Added an explicit analysis of local-only, Nextcloud-only, identical, content
  conflict, and file-versus-folder paths before normal synchronization starts.
- Added four user-controlled conflict policies: preserve both with the newest at
  the original path, give Nextcloud priority, give the computer priority, or
  review every conflict individually. The non-preferred version is always kept
  under a clear dated name.
- Existing synchronization databases are archived outside the synchronized tree
  before a clean final baseline is created. They are never silently deleted or
  reused during initialization.
- Upgrades from schema 1, including version 0.1.13, start paused and require the
  same protected review before automatic triggers or `nextcloudcmd` are enabled.
- Added a persistent safety manifest for the last verified synchronization.
  Missing, replaced, emptied, unreadable, or abnormally reduced local folders
  block synchronization before the bidirectional engine starts.
- Added recovery from Nextcloud, explicit one-time approval for intentional
  deletions, tray and main-window warning states, desktop notifications, and
  configurable file-count and percentage thresholds.
- Kept all credential, GNOME integration, low-memory UI, translation, and Debian
  upgrade fixes from version 0.1.13.

## 0.1.13 — 2026-08-07

- Fixed the remaining GNOME biometric-login credential bug. During desktop
  autostart, GNOME Keyring could return an empty Secret Service search while
  the default Login collection was still locked, causing version 0.1.12 to
  report that no stored credential existed without displaying an unlock prompt.
- The credential flow now resolves the default password collection explicitly,
  requests its native GNOME unlock prompt when locked, confirms the collection
  was unlocked, and only then searches for the stored Nextcloud app password.
- Canceling the native prompt still preserves the dedicated **Password keyring
  locked** state and does not create repeated automatic prompts or mislabel the
  Nextcloud account as invalid.
- Added diagnostic log messages for collection unlocking and truly empty
  credential searches, plus a regression test reproducing the real startup
  sequence in which locked items are initially hidden from attribute search.

## 0.1.12 — 2026-08-07

- Fixed the remaining Debian upgrade lifecycle bug. `gapplication list-apps`
  enumerates desktop entries that advertise D-Bus activation; it does not
  report which applications are currently running, so version 0.1.11 could
  still leave the old process in memory.
- The new package now queries `org.freedesktop.DBus.NameHasOwner` on every live
  user session, invokes the application's real `quit` action, and confirms that
  the D-Bus name has been released before allowing package files to be replaced.
- A previously running session is recorded before shutdown and reopened with
  the updated application after configuration. If the application does not
  exit within the safety timeout, the upgrade stops instead of silently
  continuing over a running process.
- Replaced the inaccurate `list-apps` test double with an executable regression
  test in which `list-apps` is empty while the live D-Bus name is owned,
  matching the actual GLib behavior.

## 0.1.11 — 2026-08-07

- Fixed Debian upgrade session discovery. Maintainer scripts no longer depend
  on `SUDO_UID`, which is not reliably propagated by APT/dpkg and caused the
  running old version to remain in memory during the 0.1.10 upgrade.
- Upgrades now inspect the real per-user D-Bus sessions under `/run/user`, ask
  every running NextSync instance to quit normally, wait for any active
  synchronization to finish, and reopen only the sessions that were running.
- Added an executable maintainer-script regression test that reproduces an
  upgrade without `SUDO_UID` and verifies both graceful shutdown and restart.

## 0.1.10 — 2026-08-07

- Fixed startup after biometric GNOME login by searching Secret Service with
  native unlock and secret-loading flags. The GNOME Keyring prompt can now
  unlock the Login collection without exposing the desktop password to the
  application.
- A canceled unlock prompt now leaves the application in the dedicated
  **Password keyring locked** state instead of reporting that the Nextcloud
  account needs attention.
- Automatic filesystem, timer, push, resume, and network triggers are queued
  while the keyring remains locked, preventing repeated unlock prompts. The
  **Unlock Password Keyring** action retries explicitly and resumes both file
  synchronization and `notify_push` after success.
- Debian upgrades started with `sudo apt install` now request a graceful quit
  from a running instance, wait for an active synchronization to finish, and
  restart version 0.1.10 in the same desktop session. No process is force-killed.
- Added credential, locked-state, prompt-coalescing, and Debian maintainer-script
  regression tests.

## 0.1.9 — 2026-08-07

- Published the corrected website, source, issue, and changelog links in a new
  package version so systems with `0.1.8` installed apply the update normally.
- Added artifact-level validation for the canonical
  `https://github.com/gnacho/nextsync` repository and against the former
  repository URL.

## 0.1.8 — 2026-08-07

- Set the public project website to `gnacho.com.br` across application,
  AppStream, Python, and Debian metadata.
- Updated source, issue, and documentation links to the canonical
  `gnacho/nextsync` repository.
- Added complete English GitHub documentation with a
  screenshot gallery, compatibility statement, expanded terms, and third-party
  project/license references.
- Added a native GTK bookmark for the synchronized folder in the Files sidebar.
- Added an optional symbolic link to the synchronized folder in the XDG Desktop
  directory, with collision-safe naming and no replacement of existing files.
- Added a branded GNOME-style folder icon to the synchronized folder and its
  shortcuts through GIO metadata.
- Added independent switches for the Files bookmark, desktop shortcut, and
  special icon under Settings → General → Local Folder.
- The switches read the actual desktop state instead of duplicating it in the
  application configuration. Removing the bookmark in Files is reflected while
  Settings is open and whenever it is opened again.
- New account setup enables the three integrations. Removing the account cleans
  them up without deleting the local synchronized folder or any file inside it.

## 0.1.7 — 2026-08-07

- Replaced the parent-dependent preferences dialog with a standalone
  preferences window.
- Settings now opens directly from the tray without creating, presenting, or
  retaining the main window.
- The same settings window is reused while open and released after closing to
  preserve the lazy, low-memory UI lifecycle.

## 0.1.6 — 2026-08-07

- Fixed the tray Settings action so it maps the main window before presenting
  its adaptive preferences dialog.
- The main window is now created only when needed and releases its widgets,
  subscriptions, and child windows when closed, while synchronization and the
  tray continue running.
- Replaced unbounded `nextcloudcmd` output accumulation with incremental
  classification and a fixed 200-line diagnostic tail.
- Made log opening read only the requested tail from daily files and limited
  the live log text buffer to 2,000 lines.
- Coalesced bursts of activity updates and retained a bounded 500-line live
  history for sessions with persistent logs disabled.
- Reduced per-directory inotify memory and stopped logging every filesystem
  event at the normal information level.
- Avoided rebuilding inotify watches, timers, and push connections for
  unrelated setting changes.
- Prevented overlapping credential-preparation runs, duplicate setup startup
  synchronization, and overlapping Login Flow polling requests.
- Removed unused constants, helpers, imports, and support for the obsolete
  single-file log name. Existing files are not deleted.

## 0.1.5 — 2026-08-07

- Recent Activity rows now expand to show their complete message when clicked
  and collapse back to one ellipsized line when clicked again.
- Added a right-click context menu that copies the complete activity message.
- Bundled compiled translation catalogs with the ZIP and made locale discovery
  robust for language codes, encoding suffixes, and installed packages.
- Completed the Spanish catalog so application-owned status,
  setup, settings, notification, and tray text no longer falls back to English.
- Treats a terminal `Ctrl+C` as a clean interruption without printing a Python
  traceback.

## 0.1.4 — 2026-08-07

- Fixed live tray icon updates by mapping every application state to its own
  symbolic status asset instead of always returning the main application icon.
- State changes now notify tray hosts through both StatusNotifierItem signals
  and the standard D-Bus `PropertiesChanged` signal.
- Tray title, tooltip, attention state, and Pause/Resume menu action now update
  together with the icon.

## 0.1.3 — 2026-08-07

- Fixed the tray icon on GNOME AppIndicator hosts by exporting
  `IconThemePath` from the StatusNotifierItem itself.
- The indicator now publishes the application's absolute SVG path as its
  primary icon and retains ARGB pixmaps as an independent fallback.
- Aligned the StatusNotifierItem `WindowId` property with the signed integer
  type expected by current GNOME/KDE hosts.

## 0.1.2 — 2026-08-07

- Redesigned the main window as a more compact horizontal layout for smaller
  monitors, with a fixed-size status icon and responsive action buttons.
- Replaced the always-open activity list with a collapsed activity section,
  severity icons, one-line ellipsized messages, and literal text rendering.
- Fixed the StatusNotifier D-Bus menu structure and made one click open the
  menu. Added a branded pixel fallback when the tray host cannot find icons.
- Added optional daily log files, configurable 1–365 day retention, log folder
  details, and live activity when persistent logging is disabled.
- Expanded About with GitHub links, issue reporting, valid AppStream release
  notes, full MIT license, terms, credits, changelog history, and debug info.
- Fixed numeric logging arguments being converted to strings by redaction.
- Made local and remote interval controls appear only while enabled.
- Avoided duplicate presentation calls when opening the window from the tray.

## 0.1.1 — 2026-08-07

- Fixed saving, reading, and removing credentials with GNOME Keyring on
  PyGObject versions that do not expose the low-level asynchronous libsecret
  entry points.
- Keyring operations now run outside the GTK main thread, so an unlock prompt
  cannot freeze the application.
- Credential-storage failures are no longer mislabeled as an invalid Nextcloud
  Login Flow response.

## 0.1.0 — 2026-08-07

- Initial executable development release.
- Single-account setup with Nextcloud Login Flow v2 and manual sign-in.
- Secure credentials through Secret Service / GNOME Keyring.
- Bidirectional synchronization through `nextcloudcmd`.
- Recursive Linux inotify monitoring with debounce and watch-limit fallback.
- Independent local interval, notify_push, and remote safety interval triggers.
- Single coalescing synchronization queue and manual-only mode.
- GTK4/Libadwaita setup, main, settings, log, and About interfaces.
- StatusNotifierItem tray integration without a GTK3 helper process.
- Network, battery, suspend, notifications, autostart, logs, and exclusions.
- English source UI plus Spanish translation.
