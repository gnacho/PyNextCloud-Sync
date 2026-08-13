<div align="center">
  <img src="data/icons/io.github.gnacho.nextsync.svg" width="112" alt="NextSync icon">
  <h1>NextSync</h1>
  <p><strong>Your files, local. Your Nextcloud, in sync.</strong></p>
  <p>A lightweight, GNOME-native desktop companion for keeping one complete physical copy of a Nextcloud account on Linux.</p>
  <p>
    <a href="https://github.com/gnacho/nextsync">Website</a>
    ·
    <a href="https://github.com/gnacho/nextsync/releases">Releases</a>
    ·
    <a href="https://github.com/gnacho/nextsync/issues">Report an issue</a>
  </p>
  <p>
    <img src="https://img.shields.io/badge/version-0.2.5-6557e8?style=flat-square" alt="Version 0.2.5">
    <img src="https://img.shields.io/badge/platform-Linux-f0c674?style=flat-square&logo=linux&logoColor=111" alt="Linux">
    <img src="https://img.shields.io/badge/desktop-GNOME-4a86cf?style=flat-square&logo=gnome&logoColor=white" alt="GNOME">
    <img src="https://img.shields.io/badge/GTK-4-4a86cf?style=flat-square&logo=gtk&logoColor=white" alt="GTK 4">
    <img src="https://img.shields.io/badge/license-GPLv3%2B-2da44e?style=flat-square" alt="GNU GPLv3 or later">
  </p>
</div>

<p align="center">
  <img src="docs/screenshots/main-window.png" width="820" alt="NextSync main window while synchronizing">
</p>

## A small app with one clear job

NextSync keeps **one or more Nextcloud accounts** mirrored to **one or more local folders** per account. It deliberately avoids virtual files, selective-sync rule sets beyond a per-folder remote path, dashboards, and unrelated cloud features. You can connect an account and finish the setup without synchronizing any folder, and add or remove folders later from Settings.

The actual bidirectional reconciliation is performed by the official [`nextcloudcmd`](https://github.com/nextcloud/desktop) engine. NextSync adds the desktop experience around it: secure login, automatic triggers, a compact status window, GNOME integration, logs, and a tray menu.

### A fork, with thanks

NextSync is a full fork of [**PyNextCloud-Sync**](https://github.com/ehstbr/PyNextCloud-Sync) by **ehstbr**. The project was renamed, the codebase was refactored into a thin wrapper around `nextcloudcmd` (see below), and versioning restarts at **0.1.0** — each release adds `+0.1`.

A big thank you to ehstbr for the original project and for releasing it under the GPL-3.0-or-later license, which makes this fork possible.

### Highlights

- **Complete physical mirror:** every eligible file in the account is kept locally.
- **Multiple accounts:** each account keeps its own synchronization and runtime settings, shown in a dedicated sidebar and per-account tray menu.
- **Official synchronization engine:** `nextcloudcmd` owns sync, conflict resolution, and safety. NextSync is a thin GNOME companion around it.
- **GNOME-native interface:** GTK 4 and Libadwaita, with a compact and familiar layout.
- **Secure sign-in:** Nextcloud Login Flow v2 or manual credentials, stored through Secret Service / GNOME Keyring.
- **Fast local detection:** recursive Linux `inotify` monitoring with event coalescing.
- **Remote change awareness:** optional `notify_push`, backed by a configurable remote interval.
- **Low-noise background operation:** one coalescing queue and at most one `nextcloudcmd` process.
- **First-sync confirmation:** before the initial run you confirm when the local folder, the remote folder, or both are empty.
- **Recent activity and conflicts:** a window with the live synchronization log and the `* (Nextcloud conflicted copy <date>).*` files the engine preserves, with keep/restore and open actions.
- **Deletion guard:** a mass local deletion blocks sync before the engine can propagate it, with keep paused, restore from Nextcloud, or approve once.
- **Live progress:** the current file and processed count appear in the main window and tray during a sync.
- **Useful desktop integration:** Files sidebar bookmark, Desktop shortcut, custom folder icon, autostart, notifications, and tray controls.
- **Private by design:** no telemetry, analytics, advertisements, or remote crash reporting.
- **Multilingual:** English source interface with Spanish translation.

## Screenshots

<table>
  <tr>
    <td width="50%" align="center"><strong>GNOME-oriented settings</strong><br><img src="docs/screenshots/settings-general.png" alt="General settings"></td>
    <td width="50%" align="center"><strong>Independent sync triggers</strong><br><img src="docs/screenshots/settings-sync.png" alt="Synchronization settings"></td>
  </tr>
  <tr>
    <td width="50%" align="center"><strong>Network and account controls</strong><br><img src="docs/screenshots/settings-network.png" alt="Network settings"></td>
    <td width="50%" align="center"><strong>Local logs and diagnostics</strong><br><img src="docs/screenshots/settings-advanced.png" alt="Advanced settings"></td>
  </tr>
  <tr>
    <td width="50%" align="center"><strong>Optional update</strong><br><img src="docs/screenshots/update-optional.png" alt="Optional update available"></td>
    <td width="50%" align="center"><strong>Mandatory update</strong><br><img src="docs/screenshots/update-mandatory.png" alt="Mandatory update required"></td>
  </tr>
</table>

<p align="center">
  <strong>Everything important is also available from the tray</strong><br><br>
  <img src="docs/screenshots/tray-menu.png" width="368" alt="NextSync tray menu">
</p>

<details>
<summary><strong>View the first-run setup</strong></summary>
<br>
<table>
  <tr>
    <td width="50%"><img src="docs/screenshots/welcome.png" alt="Welcome screen"></td>
    <td width="50%"><img src="docs/screenshots/connect.png" alt="Nextcloud server address"></td>
  </tr>
  <tr>
    <td width="50%"><img src="docs/screenshots/sign-in.png" alt="Sign-in choices"></td>
    <td width="50%"><img src="docs/screenshots/browser-sign-in.png" alt="Waiting for browser authorization"></td>
  </tr>
  <tr>
    <td width="50%"><img src="docs/screenshots/local-folder.png" alt="Local folder selection"></td>
    <td width="50%"><img src="docs/screenshots/review.png" alt="Configuration review"></td>
  </tr>
</table>
</details>

## How synchronization works

Every trigger asks the same scheduler for a bidirectional reconciliation. Requests that arrive together are coalesced, and the app never intentionally starts two `nextcloudcmd` processes for the same account.

```mermaid
flowchart LR
    A["Local changes<br>inotify / interval"] --> Q["Single<br>sync queue"]
    B["Remote hints<br>notify_push / interval"] --> Q
    C["Manual sync<br>network / resume"] --> Q
    Q --> N["nextcloudcmd"]
    N <--> F["Local mirror"]
    N <--> S["Nextcloud server"]
```

`notify_push` sends only a hint that something may have changed. File discovery, transfer, conflict handling, and deletion propagation remain the responsibility of `nextcloudcmd`.

> [!IMPORTANT]
> Synchronization is bidirectional. Local and remote changes—including deletions—can be propagated to the other side. Keep an independent backup of important data and do not run another synchronization engine against the same local folder.

## Why the thin-wrapper redesign

Version 0.2.0 keeps the thin-wrapper architecture; Version 0.1.0 (the fork release) changed it on purpose. Earlier releases wrapped `nextcloudcmd` in a "protected initialization" layer: a staging folder mirrored the entire remote tree, three separate `nextcloudcmd` runs merged both sides, and the app kept its own safety baseline with SHA-256 hashes and a deletion guard. On a real account that design broke down.

### What was wrong

- **The first sync downloaded everything, twice.** The staging step ran `nextcloudcmd <staging> <server>`, a full root-to-staging mirror of the whole account, before the real sync ever started. On large accounts that meant tens of gigabytes of extra disk in `~/.local/state/.../bootstrap/protected-*`, the same bandwidth used twice, and a re-upload of every local-only file.
- **No feedback, no cancel.** The bootstrap window showed an indeterminate spinner for the whole phase. `nextcloudcmd` prints one line per file, and the app captured every line into the log, but none of it reached the UI. A 50-minute download with zero progress and no Cancel button is what pushed this redesign over the edge.
- **A second source of truth that drifted.** The app kept its own manifest of the local tree and compared it before every sync. That is a parallel bookkeeping system on top of the engine's own perpetual database; it reimplemented the engine's safety poorly and could disagree with the real state.
- **Leaked staging.** Killing the app left `protected-*` staging trees on disk. Observed in real use: four aborted attempts, 11 GB of orphaned staging.

### What the engine already provides

`nextcloudcmd` is the same engine the official Nextcloud desktop client ships. It has a perpetual SQLite journal (`.sync_*.db`), ETag-aware delta sync, an internal conflict policy that preserves both sides as `* (Nextcloud conflicted copy <date>).*`, and it only rewrites files that actually changed. Reimplementing any of that in Python on top of it was scope creep that did the job worse.

One honest caveat drove part of this release: the CLI runs `--non-interactive`, and the mass-deletion confirmation that the GUI client shows is disabled for it. So **the CLI does not ask before propagating a large local deletion to the server.** That is why the fork ships a small, opt-in deletion guard of its own (see below) instead of relying on the engine for it.

### What changed

- **The bootstrap, staging, and three-run merge are gone.** The first sync is now a single `nextcloudcmd` run. Delta detection downloads only what differs, and files that already match by size and ETag stay untouched on disk.
- **The safety baseline, run markers, and SHA-256 sweep are gone.** The engine's journal is the single source of truth for synchronization state.
- **Config schema v4 → v5.** The safety fields are dropped automatically; leftover staging trees are removed and legacy safety manifests are archived on the first run after upgrade.
- **A first-sync confirmation** asks before the initial run when the local folder, the remote folder, or both are empty — probed with a shallow WebDAV PROPFIND that downloads no file bodies.
- **A deletion guard** (new, opt-in, per account) compares the local folder against a baseline of file paths before every sync. If a large share of previously known files disappears, the sync is blocked and you choose **Keep Paused**, **Restore from Nextcloud** (redownloads after dropping the local journal), or **Approve These Deletions Once**.
- **Live progress.** `nextcloudcmd` per-file lines are parsed defensively and shown as the current file plus a processed count in the account view and tray tooltip, falling back to the state label when the engine prints no per-file output.
- **A recent-activity and conflict view.** One window with two tabs: the live synchronization log, and every conflicted copy the engine left behind, with Keep Local, Keep Remote, and Open in Files.

### What this gains you

- **First sync of a large account runs once**, not three times, and does not mirror the remote tree into a staging copy first.
- **No more 50-minute silent spinner** and no more orphaned staging trees after a kill.
- **One source of truth** for synchronization state, maintained by the engine that actually does the work.
- **Accidental mass deletion is caught before it reaches the server** — the gap the CLI leaves open.
- **Conflicts stay visible and resolvable** in the app instead of hiding in the file manager.

## Installation

### Debian package — recommended

Download the `.deb` from the [latest release](https://github.com/gnacho/nextsync/releases/latest), then install it with APT so the required system packages are resolved automatically:

```bash
cd ~/Downloads
sudo apt update
sudo apt install ./nextsync_0.2.5_all.deb
```

During an interactive upgrade started with `sudo apt install`, the package asks a running NextSync instance to quit normally, waits for any current synchronization to finish, and restarts the updated application in the same desktop session. It never force-kills the synchronization process. Non-interactive upgrades or installations without an identifiable desktop session leave process control to the user or system administrator.

The package depends on `nextcloud-desktop-cmd`, Python 3, GTK 4, Libadwaita, PyGObject, libsoup, libsecret, GdkPixbuf, and GNOME Keyring. On GNOME, tray icons normally require an AppIndicator/StatusNotifier extension; synchronization continues even when no tray host is available.

### Source ZIP

Install the runtime dependencies first:

```bash
sudo apt update
sudo apt install \
  python3 python3-gi \
  gir1.2-gtk-4.0 gir1.2-adw-1 gir1.2-gdkpixbuf-2.0 \
  gir1.2-soup-3.0 gir1.2-secret-1 \
  nextcloud-desktop-cmd
```

Then extract and run:

```bash
unzip NextSync-0.3.0.zip
cd NextSync-0.2.5
./run.sh
```

`run.sh` uses the distribution Python and GI packages. It does not create a virtual environment or download packages from the internet.

### Arch / CachyOS package

The fork ships a buildable `PKGBUILD` (not published to the AUR). To build the
package locally, copy the `NextSync-0.3.0.zip` and the `PKGBUILD` into a
directory without spaces (makepkg cannot run in paths containing spaces) and run:

```bash
makepkg -cf
sudo pacman -U nextsync-0.3.0-1-any.pkg.tar.zst
```

The package installs the application, `.desktop` entry, metainfo, icons, and the
`es` translation, and depends on `nextcloud-client` for the
`nextcloudcmd` engine.

## First setup

1. Enter the base URL normally used to open your Nextcloud server.
2. Prefer **Sign in with browser** for Login Flow v2 and two-factor authentication support. Manual username plus password/app-password is also available.
3. Choose the local mirror folder. The default is `$HOME/NextCloud`. Optionally set a remote folder to mirror only that subtree instead of the account root.
4. Review the configuration and start synchronizing.
5. If the local folder, the remote folder, or both are empty, confirm the first run in a small dialog before any file is transferred.

The first synchronization is a normal `nextcloudcmd` run. No staging copy, no three-step merge, no pre-transfer analysis: the engine's delta detection downloads only what differs, and both sides are reconciled in one pass.

New account setup then enables local filesystem monitoring, a 10-minute remote interval, compatible server push, disposable-file exclusions, and autostart. It also adds the synchronized folder to the Files sidebar, creates a safe symbolic link on the XDG Desktop, and applies the NextSync folder icon. These integrations can be changed independently in **Settings → General → Local Folder**.

## Update checks

At every application startup, NextSync reads `version.json` from the
root of the GitHub repository before enabling the synchronization runtime. An
unreachable GitHub service, HTTP failure, or invalid manifest is logged and
does not prevent normal startup.

| Field | Purpose |
| --- | --- |
| `schema_version` | Version of the manifest contract |
| `version` | Latest release using SemVer |
| `mandatory` | Prevents older versions from running when `true` |
| `released_at` | ISO 8601 release date and time in UTC |
| `summary` | Short plain-text release summary |
| `changelog` | Complete ordered list of plain-text changes |

Optional updates use a non-modal Libadwaita window, so normal initialization
continues. Mandatory updates keep the runtime, filesystem monitoring, timers,
and push connection disabled and offer only the official Releases page or
application exit. The same validation can be started manually from **About →
Check for Updates**. The detailed changelog remains collapsed until requested.

## Configuration model

| Area | What it controls |
| --- | --- |
| Accounts | One entry per Nextcloud account: server, login, local folder, remote path, and its own synchronization and runtime settings |
| General | Autostart, battery behavior, local folder, Files bookmark, Desktop shortcut, and branded folder icon |
| Synchronization | `inotify`, local interval, `notify_push`, remote interval, and disposable-file exclusions |
| Network | Account removal, optional HTTP proxy, and explicit opt-in for invalid/self-signed certificates |
| Advanced | Daily logs, retention, detailed output, and runtime diagnostics |

Each account can be paused, synchronized, or removed independently. The tray shows the state that needs attention and offers per-account actions.

All four automatic triggers can be combined or disabled per account. With local monitoring, local interval, server push, and remote interval all disabled, the application operates in manual-only mode.

## Compatibility

Currently tested with [**Nextcloud Hub 26 Spring**](https://nextcloud.com/) **(34.0.1)** deployed with **Nextcloud AIO**.

Compatibility with other installations may depend on the installed `nextcloudcmd`, server configuration, reverse proxy, authentication method, and optional apps. Future versions of Nextcloud are not guaranteed to remain compatible.

## Exclusions

The default rules cover conservative disposable files such as `.DS_Store`, `Thumbs.db`, office lock files, Vim swap files, backup suffixes, and the `nextcloudcmd` journal noise file. Hidden user files remain eligible for synchronization because the client is always invoked with hidden-file support.

Patterns containing `/`, `\`, or `..` are rejected. Version 1 does not support folder, path, or remote-subtree exclusions.

## Files, credentials, and privacy

- Configuration: `$XDG_CONFIG_HOME/nextsync/settings.json`
- Generated exclusions: `$XDG_CONFIG_HOME/nextsync/excludes-<account>.lst` (one per account)
- Daily logs: `$XDG_STATE_HOME/nextsync/nextsync-YYYY-MM-DD.log`
- Account secret: GNOME Keyring or another compatible Secret Service provider

The `<account>` suffix is a short hash of the server URL, login name, local folder, and remote path, so two accounts never share an exclusion file.

Logs remain local, use one file per day, and are retained for 30 days by default. Sensitive values are redacted from application-owned log messages. If biometric desktop login leaves the Login keyring locked, GNOME shows its native unlock prompt before synchronization. The desktop password is handled only by GNOME; NextSync does not receive or store it. Canceling the prompt leaves the app waiting for an explicit **Unlock Password Keyring** request instead of repeatedly prompting or reporting invalid Nextcloud credentials.

## Development and tests

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 -m compileall -q src tests
```

The pure-Python suite includes a fake `nextcloudcmd` for success, failure, authentication failure, output, and slow-run scenarios. Real account, GNOME tray host, UPower, suspend/resume, and long-running memory tests still require an actual desktop session.

Contributions are welcome when they preserve the project's narrow scope, low idle resource use, secure credential handling, and GNOME-oriented design. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Documentation

- [Changelog](CHANGELOG.md)
- [Terms of Use](TERMS.md)
- [GNU General Public License v3 or later](LICENSE)
- [Third-party projects and licenses](THIRD-PARTY.md)
- [Contributing](CONTRIBUTING.md)

## Project status

Version `0.3.0` is the current release intended for evaluation. Test it with non-critical data before relying on it for regular synchronization, and always keep independent backups of important files.

---

<p align="center"><sub>
Nextcloud® is a registered trademark of Nextcloud GmbH. NextSync is an independent, unofficial project and is not affiliated with, sponsored by, endorsed by, or otherwise connected to Nextcloud GmbH. Use is subject to the <a href="TERMS.md">Terms of Use</a> and the GNU General Public License version 3 or later.
</sub></p>
