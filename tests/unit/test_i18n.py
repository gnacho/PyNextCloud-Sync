from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).parents[2]


def _locale_env() -> dict[str, str]:
    environment = os.environ.copy()
    environment.update(
        {
            "LANGUAGE": "es",
            "NEXTSYNC_LOCALE_DIR": str(PROJECT_ROOT / "locale"),
            "PYTHONPATH": str(PROJECT_ROOT / "src"),
        }
    )
    return environment


class I18nTests(unittest.TestCase):
    def test_bundled_es_catalog_loads_with_locale(self) -> None:
        catalog = (
            PROJECT_ROOT
            / "locale"
            / "es"
            / "LC_MESSAGES"
            / "nextsync.mo"
        )
        self.assertTrue(catalog.is_file(), catalog)
        environment = os.environ.copy()
        environment.update(
            {
                "LANG": "es_ES.UTF-8",
                "LC_ALL": "",
                "LC_MESSAGES": "",
                "LANGUAGE": "",
                "NEXTSYNC_LOCALE_DIR": str(PROJECT_ROOT / "locale"),
                "PYTHONPATH": str(PROJECT_ROOT / "src"),
            }
        )
        translated = subprocess.check_output(
            [
                sys.executable,
                "-c",
                "from nextsync.util.i18n import _; print(_('Recent Activity'))",
            ],
            env=environment,
            text=True,
        ).strip()
        self.assertEqual(translated, "Actividad reciente")

    def test_hyphenated_language_name_is_normalized(self) -> None:
        environment = _locale_env()
        environment["LANGUAGE"] = "es-ES"
        translated = subprocess.check_output(
            [
                sys.executable,
                "-c",
                "from nextsync.util.i18n import _; print(_('Sync Now'))",
            ],
            env=environment,
            text=True,
        ).strip()
        self.assertEqual(translated, "Sincronizar ahora")

    def test_desktop_integration_labels_are_translated(self) -> None:
        environment = _locale_env()
        translated = subprocess.check_output(
            [
                sys.executable,
                "-c",
                "from nextsync.util.i18n import _; "
                "print(_('Show in Files sidebar')); "
                "print(_('Show on Desktop')); "
                "print(_('Use special folder icon'))",
            ],
            env=environment,
            text=True,
        ).splitlines()
        self.assertEqual(
            translated,
            [
                "Mostrar en la barra lateral de Archivos",
                "Mostrar en el escritorio",
                "Usar un icono especial para la carpeta",
            ],
        )

    def test_update_window_and_manual_check_are_translated(self) -> None:
        environment = _locale_env()
        translated = subprocess.check_output(
            [
                sys.executable,
                "-c",
                "from nextsync.util.i18n import _; "
                "print(_('Check for Updates')); "
                "print(_('Update Available')); "
                "print(_('Required Update')); "
                "print(_('Full Changelog')); "
                "print(_('Download New Version')); "
                "print(_('Mandatory update available'))",
            ],
            env=environment,
            text=True,
        ).splitlines()
        self.assertEqual(
            translated,
            [
                "Buscar actualización",
                "Actualización disponible",
                "Actualización obligatoria",
                "Historial completo de cambios",
                "Descargar nueva versión",
                "Actualización obligatoria disponible",
            ],
        )


if __name__ == "__main__":
    unittest.main()
