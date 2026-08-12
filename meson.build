project(
  'nextsync',
  version: '0.2.5',
  meson_version: '>= 1.0.0',
)

gnome = import('gnome')
i18n = import('i18n')
python = import('python').find_installation('python3')

python_sources = files(
  'src/nextsync/__init__.py',
  'src/nextsync/__main__.py',
  'src/nextsync/application.py',
  'src/nextsync/core/__init__.py',
  'src/nextsync/core/account.py',
  'src/nextsync/core/account_manager.py',
  'src/nextsync/core/autostart.py',
  'src/nextsync/core/conflict_files.py',
  'src/nextsync/core/debounce.py',
  'src/nextsync/core/delete_guard.py',
  'src/nextsync/core/desktop_integration.py',
  'src/nextsync/core/exclusions.py',
  'src/nextsync/core/inotify.py',
  'src/nextsync/core/legacy_cleanup.py',
  'src/nextsync/core/network.py',
  'src/nextsync/core/power.py',
  'src/nextsync/core/runtime.py',
  'src/nextsync/core/scheduler.py',
  'src/nextsync/core/state.py',
  'src/nextsync/core/suspend.py',
  'src/nextsync/core/sync_permit.py',
  'src/nextsync/core/sync_engine.py',
  'src/nextsync/core/timers.py',
  'src/nextsync/core/triggers.py',
  'src/nextsync/core/updates.py',
  'src/nextsync/core/window_presentation.py',
  'src/nextsync/nextcloud/__init__.py',
  'src/nextsync/nextcloud/api.py',
  'src/nextsync/nextcloud/command.py',
  'src/nextsync/nextcloud/credentials.py',
  'src/nextsync/nextcloud/http.py',
  'src/nextsync/nextcloud/login_flow.py',
  'src/nextsync/nextcloud/nextcloudcmd_progress.py',
  'src/nextsync/nextcloud/push.py',
  'src/nextsync/nextcloud/push_protocol.py',
  'src/nextsync/storage/__init__.py',
  'src/nextsync/storage/config.py',
  'src/nextsync/storage/log.py',
  'src/nextsync/ui/__init__.py',
  'src/nextsync/ui/about.py',
  'src/nextsync/ui/about_content.py',
  'src/nextsync/ui/activity.py',
  'src/nextsync/ui/conflict_resolver.py',
  'src/nextsync/ui/log_view.py',
  'src/nextsync/ui/main_window.py',
  'src/nextsync/ui/settings.py',
  'src/nextsync/ui/setup.py',
  'src/nextsync/ui/tray.py',
  'src/nextsync/ui/tray_state.py',
  'src/nextsync/ui/update_window.py',
  'src/nextsync/util/__init__.py',
  'src/nextsync/util/i18n.py',
  'src/nextsync/util/paths.py',
  'src/nextsync/util/redact.py',
)

python.install_sources(
  files(
    'src/nextsync/__init__.py',
    'src/nextsync/__main__.py',
    'src/nextsync/application.py',
  ),
  subdir: 'nextsync',
  pure: true,
)
python.install_sources(
  files(
    'src/nextsync/core/__init__.py',
    'src/nextsync/core/account.py',
    'src/nextsync/core/account_manager.py',
    'src/nextsync/core/autostart.py',
    'src/nextsync/core/conflict_files.py',
    'src/nextsync/core/debounce.py',
    'src/nextsync/core/delete_guard.py',
    'src/nextsync/core/desktop_integration.py',
    'src/nextsync/core/exclusions.py',
    'src/nextsync/core/inotify.py',
    'src/nextsync/core/legacy_cleanup.py',
    'src/nextsync/core/network.py',
    'src/nextsync/core/power.py',
    'src/nextsync/core/runtime.py',
    'src/nextsync/core/scheduler.py',
    'src/nextsync/core/state.py',
    'src/nextsync/core/suspend.py',
    'src/nextsync/core/sync_permit.py',
    'src/nextsync/core/sync_engine.py',
    'src/nextsync/core/timers.py',
    'src/nextsync/core/triggers.py',
    'src/nextsync/core/updates.py',
    'src/nextsync/core/window_presentation.py',
  ),
  subdir: 'nextsync/core',
  pure: true,
)
python.install_sources(
  files(
    'src/nextsync/nextcloud/__init__.py',
    'src/nextsync/nextcloud/api.py',
    'src/nextsync/nextcloud/command.py',
    'src/nextsync/nextcloud/credentials.py',
    'src/nextsync/nextcloud/http.py',
    'src/nextsync/nextcloud/login_flow.py',
    'src/nextsync/nextcloud/nextcloudcmd_progress.py',
    'src/nextsync/nextcloud/push.py',
    'src/nextsync/nextcloud/push_protocol.py',
  ),
  subdir: 'nextsync/nextcloud',
  pure: true,
)
python.install_sources(
  files(
    'src/nextsync/storage/__init__.py',
    'src/nextsync/storage/config.py',
    'src/nextsync/storage/log.py',
  ),
  subdir: 'nextsync/storage',
  pure: true,
)
python.install_sources(
  files(
    'src/nextsync/ui/__init__.py',
    'src/nextsync/ui/about.py',
    'src/nextsync/ui/about_content.py',
    'src/nextsync/ui/activity.py',
    'src/nextsync/ui/conflict_resolver.py',
    'src/nextsync/ui/log_view.py',
    'src/nextsync/ui/main_window.py',
    'src/nextsync/ui/settings.py',
    'src/nextsync/ui/setup.py',
    'src/nextsync/ui/tray.py',
    'src/nextsync/ui/tray_state.py',
    'src/nextsync/ui/update_window.py',
  ),
  subdir: 'nextsync/ui',
  pure: true,
)
python.install_sources(
  files(
    'src/nextsync/util/__init__.py',
    'src/nextsync/util/i18n.py',
    'src/nextsync/util/paths.py',
    'src/nextsync/util/redact.py',
  ),
  subdir: 'nextsync/util',
  pure: true,
)

launcher_configuration = configuration_data()
launcher_configuration.set('PYTHON', python.full_path())
configure_file(
  input: 'data/nextsync.in',
  output: 'nextsync',
  configuration: launcher_configuration,
  install: true,
  install_dir: get_option('bindir'),
  install_mode: ['rwxr-xr-x'],
)

install_data(
  'data/io.github.gnacho.nextsync.desktop',
  install_dir: join_paths(get_option('datadir'), 'applications'),
)
install_data(
  'data/io.github.gnacho.nextsync.metainfo.xml',
  install_dir: join_paths(get_option('datadir'), 'metainfo'),
)
install_data(
  'data/icons/io.github.gnacho.nextsync.svg',
  install_dir: join_paths(get_option('datadir'), 'icons', 'hicolor', 'scalable', 'apps'),
)
install_data(
  'data/icons/io.github.gnacho.nextsync-symbolic.svg',
  install_dir: join_paths(get_option('datadir'), 'icons', 'hicolor', 'symbolic', 'apps'),
)
install_data(
  'data/icons/nextsync-settings-2-symbolic.svg',
  'data/icons/nextsync-info-symbolic.svg',
  install_dir: join_paths(get_option('datadir'), 'icons', 'hicolor', 'symbolic', 'apps'),
)
install_data(
  'data/icons/io.github.gnacho.nextsync-folder.svg',
  install_dir: join_paths(get_option('datadir'), 'icons', 'hicolor', 'scalable', 'places'),
)
install_data(
  'data/icons/status/nextsync-status-battery-symbolic.svg',
  'data/icons/status/nextsync-status-error-symbolic.svg',
  'data/icons/status/nextsync-status-offline-symbolic.svg',
  'data/icons/status/nextsync-status-ok-symbolic.svg',
  'data/icons/status/nextsync-status-paused-symbolic.svg',
  'data/icons/status/nextsync-status-syncing-symbolic.svg',
  'data/icons/status/nextsync-tray-cloud.svg',
  'data/icons/status/nextsync-tray-cloud-off.svg',
  install_dir: join_paths(
    get_option('datadir'), 'icons', 'hicolor', 'symbolic', 'apps'
  ),
)

install_data(
  'CHANGELOG.md',
  'LICENSE',
  'TERMS.md',
  'THIRD-PARTY.md',
  'version.json',
  install_dir: join_paths(get_option('datadir'), 'doc', 'nextsync'),
)

subdir('po')
