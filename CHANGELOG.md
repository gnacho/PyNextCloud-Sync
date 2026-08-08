# Changelog

## 0.1.9 — 2026-08-07

- Published the corrected website, source, issue, and changelog links in a new
  package version so systems with `0.1.8` installed apply the update normally.
- Added artifact-level validation for the canonical
  `https://github.com/ehstbr/PyNextCloud-Sync` repository and against the former
  repository URL.

## 0.1.8 — 2026-08-07

- Set the public project website to `eduhcommerce.com.br` across application,
  AppStream, Python, and Debian metadata.
- Updated source, issue, and documentation links to the canonical
  `ehstbr/PyNextCloud-Sync` repository.
- Added complete English and Brazilian Portuguese GitHub documentation with a
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
  robust for `pt_BR`, `pt-BR`, encoding suffixes, and installed packages.
- Completed the Brazilian Portuguese catalog so application-owned status,
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
- English source UI plus Brazilian Portuguese and Spanish translations.
