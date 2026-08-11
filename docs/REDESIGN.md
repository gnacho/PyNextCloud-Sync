# Redesign: thin GNOME wrapper over nextcloudcmd

Status: proposal for discussion. Not implemented yet.
Supersedes issues #4 and #5 once accepted.
Scope: architectural simplification. Removes the bootstrap, safety, and
staging subsystems without touching the multi-account and remote-path
mapping work shipped in #2 and #3.

## 1. Why we are doing this

`nextcloudcmd` ships with the Nextcloud Desktop Client. It has been the
canonical Linux sync engine for years, with conflict resolution, an
internal perpetual database, ETag-aware delta sync, and its own
protocol-level safety. The upstream project maintains it and will keep
improving it without us doing anything.

PyNextCloud Sync wraps that engine today, but adds a parallel
"protected initialization" subsystem on top of it: `BootstrapRunner`,
`safety.py`, `SafetyManifest`, four merge policies, a staging tree,
three full `nextcloudcmd` runs per first sync, and a file-by-file
SHA-256 comparison in Python. Verified against the code shipped in
v2.1.0:

- `core/bootstrap.py:242-294` creates a private staging tree under
  `~/.local/state/pynextcloud-sync/bootstrap/protected-*` and runs
  `nextcloudcmd <staging> <server>` against it. That is a full
  root-to-staging mirror of the entire account, or of the remote-path
  mapping configured via #3, regardless of what is already on the local
  side.
- `core/bootstrap.py:316-370` performs up to three `nextcloudcmd` runs
  per first sync: download to staging, upload merged staging back to the
  server, and re-sync staging into the user's local folder after
  `_apply_staging` overwrites it (`bootstrap.py:522-548`).
- `core/bootstrap.py:107-118` hashes every file on both sides with
  SHA-256, even when size and mtime already match, to, in the code's
  words, "avoid silently treating a same-size conflict as identical".
- `ui/bootstrap.py:84-102` shows an indeterminate `Gtk.Spinner` and a
  single phase label for the entire duration. No progress bar, no
  fraction, no bytes counter, no reachable Cancel button. The per-line
  `nextcloudcmd` progress output is captured only into the daily log
  file (`bootstrap.py:414`), never into the UI.

For small accounts the cost is wasted bandwidth, disk, and CPU. For
large accounts the bootstrap is unworkable. Observed during testing: an
account against `self-hosted-nextcloud.example` consumed 11 GB of staging across
aborted attempts before being killed, with no progress feedback and no
clean shutdown path. `_cleanup_staging` is only invoked from explicit
`cancel()` / `cleanup()`, so on SIGTERM or SIGKILL the staging tree
survives on disk.

The design parallels and reimplements what the engine already does, and
does it worse. That is the scope creep this redesign removes.

## 2. What we learned the hard way

This redesign is not hypothetical. It comes out of a concrete session
trying to use the app against a real Nextcloud, and the way the app
behaved pushed us from "let's polish the UX" to "let's delete a
subsystem".

Three observations drove it.

### The server bug the app masked and the engine exposed

`self-hosted-nextcloud.example` runs openresty and sends the header `Upgrade: h2,h2c`
on HTTP/2 responses. That header is illegal under RFC 7540 section
8.1.1. libsoup3, which the app uses for its HTTP, refuses the response
and surfaces `g-io-error-quark` in the UI. The official Nextcloud
desktop client, built on libcurl, tolerates the same header and works.
The first user report read "I just clicked sign in with the browser, I
hadn't typed anything yet, and it broke". Chasing that down led us to
read the code around `nextcloud/http.py:59-60`, where any `GLib.Error`
from libsoup3 gets relit as `RuntimeError(str(exc))`. The string of a
`GLib.Error` begins with the quark name, so the UI shows that quark
verbatim. The user was not told anything they could act on.

The point here is not the quark. It is that the app stood up an entire
subprocess-based sync architecture on top of libsoup3, and the moment
the transport layer complained the app had no vocabulary for explaining
it. "Thin wrapper" means, in part, surfacing transport errors with
words.

### Eleven gigabytes on disk, silently, while the UI spun

When the bootstrap did kick off against `self-hosted-nextcloud.example`, it ran for
fifty minutes with an indeterminate spinner and the text "Downloading a
protected copy from Nextcloud". Behind that spinner, 11 GB of staging
landed under `~/.local/state/pynextcloud-sync/bootstrap/protected-*`.
`BoundedOutputCapture` in `bootstrap.py:393` was reading every line
`nextcloudcmd` printed, but the UI never saw them. They went to the log
file via `self.logger.info("CMD %s", line)` and disappeared from the
session.

Killing the app left the staging trees on disk. `_cleanup_staging` only
fires from `cancel()` and `cleanup()`, not from a SIGTERM handler. Four
aborted attempts produced four `protected-*` directories totalling
11 GB. None of this was visible to the user. The redesign's section 3,
which removes the staging tree entirely, removes the leak with it.

### A working engine, sitting right there

The official Nextcloud client, against the same server, was syncing
files during the same session. It uses libcurl and is permissive about
illegal HTTP/2 headers. It uses the same WebDAV PROPFIND the redesign
proposes leaning on, the same `.sync.db` perpetual database, the same
conflict file policy that produces `* (Nextcloud conflicted copy
<date>).*` names. None of that is inscrutable magic; it is the engine the
app already invokes. The app was not adding value on top of it. It was
getting in the way.

## 3. New direction

PyNextCloud Sync becomes a thin GNOME desktop companion over
`nextcloudcmd`. The engine owns synchronization, conflict resolution,
and safety. The app owns everything around it: GNOME integration,
secure credentials, account configuration, folder mapping, scheduling,
filesystem monitoring, server push notifications, tray, autostart,
activity log, and an accessible UI for the conflict files the engine
produces.

The first synchronization is a normal `nextcloudcmd` run. No staging,
no three-step merge wash, no SHA-256 sweep. If the user has existing
files locally that match the remote by size and ETag, the engine skips
them. If both sides have files, the engine applies its conflict policy
and produces `* (Nextcloud conflicted copy YYYY-MM-DD).*` names visible
in the file manager.

## 4. What we remove

| Path | What it does | Why it goes |
|---|---|---|
| `src/pynextcloud_sync/core/bootstrap.py` | `BootstrapRunner`, `BootstrapAnalysis`, `BootstrapPolicy`, `BootstrapConflict`, `BootstrapResult`; staging tree plus the three-run `nextcloudcmd` flow | Reimplements engine responsibilities badly. |
| `src/pynextcloud_sync/ui/bootstrap.py` | `BootstrapWindow` (analysis, review, conflict decisions, apply) | Backs the removal above. |
| `src/pynextcloud_sync/core/safety.py` safety machinery | `SafetyManifest`, `InventorySnapshot`, deletion guards, baseline persistence | The engine has its own perpetual database and safety. The Python baseline adds a second source of truth that drifts. |
| `src/pynextcloud_sync/core/safety.py` deletion guard and shrunk-folder check | Picks a fight with the engine on every sync | Replace with trust in the engine's own shadowing and trash bin on the server. |
| `src/pynextcloud_sync/core/sync_run_marker.py` | Durable breadcrumb around `nextcloudcmd` runs; only meaningful if we distrust the engine | Goes with the safety removal. |
| Config fields `bootstrap_complete`, `bootstrap_completed_at`, `guard_enabled`, `deletion_count_threshold`, `deletion_percent_threshold` | Backed by the safety machinery | Removed from the schema; migration drops legacy values. |
| `ui/bootstrap.py` review and merge UI (policies, conflict rows) | UI wrapper over the removed runner | Goes with the bootstrap removal. |

`notify_push`, `inotify`, `triggers`, `timers`, `debounce`, `scheduler`,
`sync_permit`, `sync_engine`, `runtime`, `account`, `account_manager`,
the credential store, GNOME integration (tray, autostart, bookmarks),
the updates check, multi-account, and remote-path mapping all stay. They
are the actual product value.

## 5. What we add, small and mostly UI

- A conflict file resolver view. A small window lists files the engine
  has produced as `* (conflicted copy) *` in the user's folder, with
  side-by-side size and mtime, and buttons: keep local, keep remote,
  keep both, open in Files. The engine writes those copies. The UI just
  surfaces them. This is an opt-in view launched from the tray and the
  main window, not a blocking gate.
- A first-sync confirmation dialog when the local folder is empty or
  the remote is empty or both. "Connect `alice@server` and start syncing
  `<folder>` now? Existing conflicts will be preserved as `<name>
  (Nextcloud conflicted copy <date>).<ext>`." Two buttons: Start, Back
  to setup. No multi-hour staging phase behind it.
- Real `nextcloudcmd` progress. The engine emits one-file-per-line
  progress on stdout. Surface it as a phase label, current file, and
  processed counter. Fall back to pulse mode when the engine does not
  report totals. It usually does not. This is the part of #5 that
  survives the redesign. The indeterminate spinner disappears because
  the silent spinner was specifically about the bootstrap phase.

## 6. What we keep configurable

- `trust_invalid_certificates`, passed as `--trust`.
- `custom_proxy`, passed as `--httpproxy`.
- `max_sync_retries`, passed as `--max-sync-retries`.
- `exclude_patterns`, passed as `--exclude`. Unchanged.
- The four sync triggers: `local_inotify_enabled`,
  `local_interval_enabled`, `remote_push_enabled`,
  `remote_interval_enabled`. All engine-adjacent scheduling, kept.
- Per-account offline pause and resume, desktop integration, autostart.
  Kept.

## 7. Migration

Config schema bumps from v4 to v5. Migration:

1. Drop the removed safety fields from every account dict. The state
   file no longer needs stale `bootstrap_complete = false` blocking
   resync.
2. Leftover `protected-*` staging trees in
   `~/.local/state/pynextcloud-sync/bootstrap/` are removed on first
   run after upgrade, freeing disk. The staging directory itself goes
   too. This is the cleanup the current app never runs on its own.
3. Existing `SafetyManifest` files are archived under
   `~/.local/state/pynextcloud-sync/safety-archives/legacy-<ISO>/` and
   then ignored. No user-visible behaviour change beyond "the next
   scheduled sync runs immediately because the guard is gone".

Users who already had `bootstrap_complete = true` keep working. The
engine continues where it was, no staging, no review step. Users who
were stuck mid-bootstrap, like the one observed in this session,
finally get a working first sync: a single `nextcloudcmd` run, normal
conflict files if any, full UI progress.

## 8. Issues this resolves

- Closes #4 (bootstrap downloads the entire remote tree). There is no
  bootstrap download anymore. `nextcloudcmd` runs once, with delta
  detection on size and ETag, downloading only what differs.
- Closes #5 (Bootstrap UI has no progress or cancel). The indeterminate
  spinner disappears together with the bootstrap phase that produced
  it. Real `nextcloudcmd` progress is surfaced. The surviving UX work
  from #5 ships as part of the redesign.
- Removes the staging-clean-up-on-SIGKILL side bug noted in #5. There
  is no staging tree to leak.

## 9. Issues this opens

- A conflict file resolver view, the UI surface in section 5.
- A first-sync confirmation dialog, small, two-button, no staging.
- Real `nextcloudcmd` progress in the main window and tray, the
  surviving UX work from #5 applied to the ongoing sync UI rather than
  to a bootstrap window.

The three will be filed once this redesign is accepted and merged.

## 10. Why now

The remote-path mapping shipped in #3 already makes the bootstrap cost
less than before, because each account targets a single folder. That
would have let us ship the redesign in stages. But the design problems
documented in #4 and #5 are not about account size. They are about the
architecture doing the wrong thing regardless of size. Keeping the
staging subsystem around even for small accounts continues to pay
maintenance, complexity, and disk and bandwidth cost without giving
users anything the engine does not already provide.

The path that adds the least risk and the most long-term value is to
delete the parallel subsystem. It does not require new sync code. It
does require accepting that `nextcloudcmd` is the source of truth for
sync, and that PyNextCloud Sync's job is to make that engine live nicely
on the desktop, not to second-guess it.

## 11. What is not in scope

- Replacing `nextcloudcmd` with a pure-Python WebDAV sync engine. That
  is a multi-week rewrite of an entire client and is not what this app
  is for. If the upstream desktop client ever stops shipping
  `nextcloudcmd`, this decision is revisited.
- Multi-folder mappings inside a single account. Several
  `local_root` to `remote_path` pairs under one login. #1 already
  noted this as out of scope. The redesign keeps the
  one-folder-per-account model and the remote-path mapping shipped in
  #3.
- The custom `--unsyncedfolders` selective sync enhancement. Still
  future work, unrelated to the redesign.