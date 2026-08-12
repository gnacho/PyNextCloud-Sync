# Refactor conclusions

This document records why the two major refactors of NextSync happened, what
each changed, and the conclusions we drew from doing them. It is written after
the fact, for future maintainers (including ourselves six months from now) who
might wonder why the code looks the way it does.

Two refactors are covered:

1. **The thin-wrapper redesign** (v0.1.0, fork release). Removed the protected
   initialization subsystem so `nextcloudcmd` owns synchronization, conflict
   resolution, and safety.
2. **The multi-folder model** (v0.2.0). Accounts stopped holding a single sync
   folder and started holding a list of folder pairs (possibly empty).

## 1. The thin-wrapper redesign (v0.1.0)

### Why it happened

The original upstream code wrapped `nextcloudcmd` in a "protected
initialization" layer. Before the first real sync it mirrored the entire
remote tree into a staging folder, ran `nextcloudcmd` three times to merge
both sides, and kept its own SHA-256 baseline of the local tree. On a real
account that design broke down:

- **The first sync downloaded everything twice.** A full root-to-staging
  mirror ran before the real sync, consuming the same bandwidth twice and
  tens of gigabytes of disk.
- **No feedback, no cancel.** The bootstrap window showed an indeterminate
  spinner for the whole phase while `nextcloudcmd` printed one line per file
  that never reached the UI.
- **A second source of truth that drifted.** The app kept its own manifest
  of the local tree and compared it before every sync. That is a parallel
  bookkeeping system on top of the engine's own journal. It reimplemented
  the engine's safety poorly and could disagree with reality.
- **Leaked staging.** Killing the app left `protected-*` staging trees on
  disk. Observed in real use: four aborted attempts, 11 GB of orphaned
  staging.

### What changed

- The bootstrap, staging, and three-run merge are gone. The first sync is a
  single `nextcloudcmd` run with delta detection.
- The safety baseline, run markers, and SHA-256 sweep are gone. The engine's
  journal is the single source of truth.
- A first-sync confirmation asks before the initial run when a side is empty.
- A small, opt-in deletion guard restores the protection the CLI engine
  does not provide (its confirmation dialog is GUI-only).
- A conflict view surfaces the conflicted copies the engine preserves.

### Conclusions

- **Do not reimplement what the engine already does.** `nextcloudcmd` has a
  perpetual SQLite journal, ETag-aware delta sync, a conflict policy, and it
  only rewrites files that actually changed. Reimplementing any of that in
  Python on top of it was scope creep that did the job worse.
- **One source of truth is worth more than defensive bookkeeping.** Two
  tracking systems (engine journal + app manifest) will drift. When they
  disagree, the user sees a scary error and nobody can say which one is
  right.
- **Feedback and cancel beat cleverness.** A 50-minute silent spinner is
  worse than a slower but observable operation. The redesign surfaces real
  per-file progress and never blocks without explanation.
- **The engine's honest gaps are the app's job.** The CLI does not ask
  before propagating a mass local deletion, so the app ships a small
  deletion guard. The right scope for a companion app is exactly the gaps
  of the thing it wraps.

## 2. The multi-folder model (v0.2.0)

### Why it happened

The thin-wrapper redesign originally declared multi-folder mappings out of
scope: one account, one `local_root` + `remote_path` pair. Real use pushed
back. Users want to mirror several unrelated directories of the same
account without creating a separate account entry for each, and the
official client lets you connect an account without synchronizing any
folder at all.

### What changed

- The config schema moved from v5 to v6. Each account now holds a `folders`
  list, where each entry maps a local root to an optional remote path.
- The account identity no longer includes the folder pair. It is a hash of
  server + login. A folder pair has its own fingerprint.
- Each folder runs its own runtime, inotify watcher, deletion guard,
  exclusions, and `nextcloudcmd` invocation, sharing the account's sync
  settings.
- The setup wizard lets you finish the login without choosing any folder.
  Folders are added and removed later from Settings.
- Migrating from v5 to v6 moves the single pair into the list
  automatically.

### Conclusions

- **A model with an empty list is a different feature than a model with an
  optional field.** Allowing zero folders (finish the login, add folders
  later) changes the setup flow from "required step" to "optional step".
  The official client behaves this way, and it is the behavior users expect.
- **Identity must not depend on the most volatile part.** The old account id
  hashed the folder pair, so "same account, different folder" produced a
  different id and an ugly duplicate-account error. Moving identity to
  server + login made folders a mutable list under a stable account.
- **Per-item runtime is the natural unit.** The engine already treats each
  local root as an independent sync with its own journal. Giving each folder
  its own runtime, watcher, and guard matched the engine's model instead of
  fighting it. The per-account settings stay shared because they are
  account-level concerns (push, intervals).
- **Migrating configs automatically is cheaper than asking.** Schema bumps
  with automatic migration let existing users keep working. The migration
  from v5 to v6 is small because the old single pair maps trivially into a
  one-element list.

## 3. Cross-cutting lessons

- **Scope creep arrives as "a small layer on top".** Both refactors removed
  code that had grown as a convenience layer and ended up duplicating the
  engine or the model. Question every layer that tracks state the underlying
  system already tracks.
- **Real usage is the spec.** Both refactors were driven by concrete pain
  observed on real accounts (staging copies, silent spinners, folder limits).
  The documents that declared things "out of scope" were wrong; usage
  corrected them.
- **Keep the wrongness visible.** The "what was wrong" sections above are
  the most useful part of this file. When a future design feels elegant,
  re-read them to remember what the previous elegant idea actually cost.

See [REDESIGN.md](REDESIGN.md) for the original redesign proposal and
[CHANGELOG.md](../CHANGELOG.md) for the version history.
