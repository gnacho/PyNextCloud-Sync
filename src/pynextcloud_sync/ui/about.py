from __future__ import annotations

import platform

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

from pynextcloud_sync import APP_ID, APP_NAME, VERSION
from pynextcloud_sync.util.i18n import _

from .about_content import MIT_LICENSE_TEXT, release_notes_markup, terms_text


WEBSITE_URL = "https://eduhcommerce.com.br"
PROJECT_URL = "https://github.com/ehstbr/PyNextCloud-Sync"
ISSUES_URL = f"{PROJECT_URL}/issues"
CHANGELOG_URL = f"{PROJECT_URL}/blob/main/CHANGELOG.md"
TERMS_URL = f"{PROJECT_URL}/blob/main/TERMS.md"
THIRD_PARTY_URL = f"{PROJECT_URL}/blob/main/THIRD-PARTY.md"


def show_about_dialog(parent: Gtk.Window) -> None:
    about = Adw.AboutDialog(
        application_name=APP_NAME,
        application_icon=APP_ID,
        version=VERSION,
        developer_name="EduhCommerce",
        comments=_("A lightweight Nextcloud synchronization client for Linux."),
        website=WEBSITE_URL,
        issue_url=ISSUES_URL,
        copyright="© 2026 EduhCommerce",
    )
    about.set_license_type(Gtk.License.CUSTOM)
    about.set_license(MIT_LICENSE_TEXT)
    about.set_release_notes(release_notes_markup())
    if hasattr(about, "set_release_notes_version"):
        about.set_release_notes_version(VERSION)

    about.add_link(_("Source code on GitHub"), PROJECT_URL)
    about.add_link(_("Report a problem"), ISSUES_URL)
    about.add_link(_("Complete changelog"), CHANGELOG_URL)
    about.add_link(_("Terms of Use"), TERMS_URL)
    about.add_link(_("Third-party projects and licenses"), THIRD_PARTY_URL)
    about.add_acknowledgement_section(
        _("Synchronization Engine"), ["Nextcloud nextcloudcmd"]
    )
    about.add_acknowledgement_section(
        _("Desktop Technologies"), ["GTK 4", "Libadwaita", "Secret Service", "D-Bus"]
    )
    about.add_acknowledgement_section(
        _("Languages"), ["English", "Português (Brasil)", "Español"]
    )
    about.add_legal_section(
        _("Terms of Use"),
        "© 2026 EduhCommerce",
        Gtk.License.CUSTOM,
        terms_text(),
    )

    if hasattr(about, "set_debug_info"):
        gtk_version = ".".join(
            str(value)
            for value in (
                Gtk.get_major_version(),
                Gtk.get_minor_version(),
                Gtk.get_micro_version(),
            )
        )
        adw_version = ".".join(
            str(value)
            for value in (
                Adw.get_major_version(),
                Adw.get_minor_version(),
                Adw.get_micro_version(),
            )
        )
        about.set_debug_info(
            "\n".join(
                (
                    f"PyNextCloud Sync: {VERSION}",
                    f"Python: {platform.python_version()}",
                    f"GTK: {gtk_version}",
                    f"Libadwaita: {adw_version}",
                    f"Platform: {platform.platform()}",
                )
            )
        )
        about.set_debug_info_filename("pynextcloud-sync-debug.txt")
    about.present(parent)
