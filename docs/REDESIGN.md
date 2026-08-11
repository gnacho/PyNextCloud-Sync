# PyNextCloud Sync: feedback from a fork maintainer

This is a note from someone who has been running PyNextCloud Sync
through real use and then maintaining a fork of it. It is not a bug
report and it is not a complaint. It is my honest opinion on what the
app does well, where it costs more than it should, and a proposal for a
simpler architecture that I think would help everyone.

I am writing it in the open because the fork already exists and the
changes are significant enough that you deserve to see the reasoning
before deciding anything.

## 1. What I think the app gets right

The core decision is the right one. Building on `nextcloudcmd` instead
of writing a sync engine from scratch gives the app a decade of
production experience, an ETag-aware delta sync, a perpetual database,
and conflict resolution that the upstream desktop client keeps paying
for. That choice is what makes the app worth using at all.

The desktop layer around it is genuinely good. The GNOME integration,
the secure credential store, the tray, autostart, filesystem
monitoring, server push notifications, and the clean multi-account
setup all feel native. Nothing else on Linux ties this bundle together
this cleanly.

So the feedback below is not about the foundation. It is about a layer
on top of the foundation that I think grew in the wrong direction.

## 2. What I hit when I actually used it

I tried to point the app at a self-hosted Nextcloud with a few years of
content, multiple local folders that I wanted mapped to different
remote folders, and more than one account. Three things stood out.

### The first sync downloads the whole server, twice, plus a local rewrite

The protected initialization step, `core/bootstrap.py`, creates a
private staging tree and runs `nextcloudcmd` against it. That is a full
mirror of the remote folder into a temporary location before the app
decides anything. It then compares that staging tree against the local
folder with a file-by-file SHA-256 sweep, applies a merge policy, and
for good measure runs `nextcloudcmd` again on the merged staging, then
copies the whole result over the local folder, then runs it a third
time on the final local folder.

With a multi-gigabyte account this is not a first sync. It is hours of
download into a hidden temporary folder, a full local rewrite, and
three times the bandwidth. The official client does the same first sync
in one pass because it compares against the local tree with size and
ETag checks and only transfers what differs.

### No progress, no cancel, and no cleanup

While that multi-gigabyte mirror ran, the window showed an
indeterminate spinner and a single line of text that said "Downloading
a protected copy from Nextcloud". `nextcloudcmd` was printing one line
per file, and the app was reading every line into a capture buffer, but
none of it reached the screen. There was no progress bar, no file
count, no cancel button that was obvious, and no disk estimate.

The staging cleanup only runs from an explicit cancel path. When the
app is killed, the temporary mirror stays on disk. In my session four
aborted attempts left 11 GB of orphaned staging behind, invisible to
the user, before I noticed and removed it by hand.

### One folder per account, mirrored as a whole

The app models an account as a single local folder that mirrors the
whole remote root. I have several local folders that map to different
remote folders, which is how the official client works and how most
people with existing data on disk actually think about it. With the
single-root model I would have had to either move all my local folders
into one place or mirror the entire server repeatedly.

## 3. What I think the deeper problem is

The bootstrap layer reimplements what `nextcloudcmd` already does, and
it does it worse. The engine has its own perpetual database, its own
conflict policy, its own ETag delta logic, and its own way of
preserving both sides of a conflict. The app then adds a second source
of truth, a Python inventory with SHA-256 hashes, and tries to gate the
engine on top of it. Two systems maintaining the same idea is where the
complexity and the disk and bandwidth costs come from. It is also where
the silent failure modes come from, because the gating layer hides what
the engine is doing.

The reason the bootstrap exists, as far as I can tell, is caution
about data loss on the very first sync. That is a reasonable fear. But
the cost of the current design is paid by every user on every first
sync, and the fear is already handled by the engine, which keeps a
trash bin on the server and preserves conflicting versions instead of
destroying them.

## 4. A simpler proposal

Make PyNextCloud Sync a thin desktop companion over `nextcloudcmd` and
let the engine own sync, conflicts, and safety. The app owns what it
is already good at: credentials, accounts, folder mapping, scheduling,
filesystem monitoring, server push, tray, autostart, and a readable UI
for the files the engine produces.

Concretely:

- The first sync is a normal `nextcloudcmd` run. No staging mirror, no
  three-pass merge, no SHA-256 sweep. The engine's delta detection
  handles it in one pass and only transfers what differs.
- Remove the bootstrap module, the Python safety baseline, the run
  marker, the merge policies, and their UI.
- Keep the engine's own conflict handling. When it produces files
  named `name (Nextcloud conflicted copy date).ext`, the app shows a
  small window listing them with keep local, keep remote, keep both,
  and open in Files. That view is optional and never blocks sync.
- Before the first sync, if either side is empty, show a short
  confirmation: connect and start syncing this folder now? Two
  buttons. Nothing else.
- Surface the engine's per-file output as a phase label and file
  counter in the main window and tray. Pulse mode when the engine does
  not report totals.

This keeps everything that makes the app valuable and deletes the layer
that costs the most. It is a smaller app, not a bigger one.

## 5. The conclusions I have adopted

I am not asking you to take my word for the proposal. I want to be
clear about what I have already concluded and why, so the reasoning is
on the table:

- `nextcloudcmd` is the source of truth for sync. Replacing it with a
  Python WebDAV engine is not worth doing. The upstream project
  maintains it and will keep improving it.
- The bootstrap, safety baseline, and staging layers should be deleted,
  not patched. Every fix to them adds surface area to code that exists
  to second-guess an engine that does not need second-guessing.
- The multi-account and folder-mapping work is worth keeping. It is
  the part that makes the app useful for people with existing data.
- An 11 GB orphaned staging leak is not a minor bug. It is the
  visible symptom of the wrong layer owning disk and bandwidth.

## 6. What I am doing with this

The fork already ships multi-account support and remote-path folder
mapping, and this document records the direction for the next step. If
you disagree with any of it, I would genuinely like to hear why. If any
part of it is useful to the main project, I am happy to open it as a
proposal there rather than keep it in the fork. Either way, the
reasoning above is what I used to decide, and you should have it.

Thank you for building the foundation. It is a good one.
