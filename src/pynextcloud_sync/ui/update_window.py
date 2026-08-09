from __future__ import annotations

from typing import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, Gtk

from pynextcloud_sync import APP_NAME, VERSION
from pynextcloud_sync.core.updates import RELEASES_URL, UpdateManifest
from pynextcloud_sync.util.i18n import _


class UpdateWindow(Adw.ApplicationWindow):
    def __init__(
        self,
        application: Gtk.Application,
        manifest: UpdateManifest,
        *,
        on_close: Callable[[UpdateWindow], None],
        on_quit: Callable[[], None],
    ) -> None:
        mandatory = manifest.mandatory
        super().__init__(
            application=application,
            title=_("Required Update") if mandatory else _("Update Available"),
        )
        self.manifest = manifest
        self.mandatory = mandatory
        self._on_close = on_close
        self._on_quit = on_quit
        self.set_default_size(560, 570)
        self.set_resizable(True)
        self.set_modal(mandatory)
        self.set_deletable(not mandatory)
        self.connect("close-request", self._close_requested)

        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        header.set_show_end_title_buttons(not mandatory)
        toolbar.add_top_bar(header)

        scroller = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
        clamp = Adw.Clamp(maximum_size=520, tightening_threshold=400)
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        content.set_margin_top(24)
        content.set_margin_bottom(24)
        content.set_margin_start(18)
        content.set_margin_end(18)
        clamp.set_child(content)
        scroller.set_child(clamp)
        toolbar.set_content(scroller)

        icon = Gtk.Image(
            icon_name=(
                "software-update-urgent-symbolic"
                if mandatory
                else "software-update-available-symbolic"
            ),
            pixel_size=64,
        )
        content.append(icon)

        heading = Gtk.Label(
            label=_("This version must be updated")
            if mandatory
            else _("A new version is available"),
            css_classes=["title-1"],
            justify=Gtk.Justification.CENTER,
            wrap=True,
        )
        content.append(heading)

        explanation = Gtk.Label(
            label=(
                _(
                    "This update is mandatory. PyNextCloud Sync will not start "
                    "synchronization or allow use of the current version."
                )
                if mandatory
                else _(
                    "This update is optional. PyNextCloud Sync can continue running "
                    "while you decide when to install it."
                )
            ),
            justify=Gtk.Justification.CENTER,
            wrap=True,
            xalign=0.5,
        )
        explanation.add_css_class("dim-label")
        content.append(explanation)

        version_group = Adw.PreferencesGroup(title=_("Version Information"))
        version_group.add(
            Adw.ActionRow(title=_("Installed version"), subtitle=VERSION)
        )
        version_group.add(
            Adw.ActionRow(
                title=_("Available version"), subtitle=manifest.version_text
            )
        )
        version_group.add(
            Adw.ActionRow(
                title=_("Released at"), subtitle=manifest.released_at_utc_text
            )
        )
        content.append(version_group)

        changes_group = Adw.PreferencesGroup(title=_("What's New"))
        summary_row = Adw.ActionRow(title=manifest.summary)
        if hasattr(summary_row, "set_title_lines"):
            summary_row.set_title_lines(0)
        changes_group.add(summary_row)
        content.append(changes_group)

        changelog_group = Adw.PreferencesGroup()
        changelog = Adw.ExpanderRow(
            title=_("Full Changelog"),
            subtitle=_("{count} changes in this release").format(
                count=len(manifest.changelog)
            ),
        )
        changelog.set_expanded(False)
        for index, item in enumerate(manifest.changelog, start=1):
            row = Adw.ActionRow(title=item)
            row.add_prefix(Gtk.Label(label=str(index), css_classes=["dim-label"]))
            if hasattr(row, "set_title_lines"):
                row.set_title_lines(0)
            changelog.add_row(row)
        changelog_group.add(changelog)
        content.append(changelog_group)

        actions = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=12,
            halign=Gtk.Align.CENTER,
        )
        releases = Gtk.Button(label=_("Open Releases Page"))
        releases.add_css_class("suggested-action")
        releases.connect("clicked", self._open_releases)
        actions.append(releases)
        finish = Gtk.Button(
            label=_("Close Application") if mandatory else _("Not Now")
        )
        if mandatory:
            finish.add_css_class("destructive-action")
            finish.connect("clicked", lambda *_args: self._on_quit())
        else:
            finish.connect("clicked", lambda *_args: self.close())
        actions.append(finish)
        content.append(actions)

        footer = Gtk.Label(
            label=APP_NAME,
            css_classes=["dim-label", "caption"],
            halign=Gtk.Align.CENTER,
        )
        content.append(footer)
        self.set_content(toolbar)

    def _open_releases(self, _button: Gtk.Button) -> None:
        Gio.AppInfo.launch_default_for_uri(RELEASES_URL, None)

    def _close_requested(self, _window: Gtk.Window) -> bool:
        if self.mandatory:
            return True
        self._on_close(self)
        return False
