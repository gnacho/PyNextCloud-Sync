#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

# Tests assume English UI strings; pin the locale so results do not depend on
# the developer's environment.
export LANG=C
export LC_ALL=C

export PYTHONPATH="$project_root/src${PYTHONPATH:+:$PYTHONPATH}"
python3 -m compileall -q src tests
python3 -m unittest discover -s tests -v
msgfmt --check --output-file=/tmp/pynextcloud-sync-es.mo po/es.po

