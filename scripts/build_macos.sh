#!/bin/zsh
set -e
cd "${0:A:h}/.."
PROJECT_ROOT="$PWD"
if [[ "$(uname -s)" != "Darwin" ]]; then
  print -u2 "The macOS bundle must be built on macOS."
  exit 1
fi
if [[ ! -x .venv-desktop/bin/python ]]; then
  python3 -m venv .venv-desktop
fi
.venv-desktop/bin/python -m pip install -r requirements-desktop.txt nuitka ordered-set zstandard
.venv-desktop/bin/python scripts/make_macos_icon.py
export PATH="$PWD/.venv-desktop/bin:$PATH"
export NUITKA_CACHE_DIR="$PWD/.nuitka-cache"
BUILD_STAGE="$(mktemp -d /tmp/waraq-macos-build.XXXXXX)"
PYSIDE_ROOT="$("$PROJECT_ROOT/.venv-desktop/bin/python" -c 'from pathlib import Path; import PySide6; print(Path(PySide6.__file__).parent)')"
ASSET_ARCHIVE="$PYSIDE_ROOT/Qt/qml/Qt/labs/assetdownloader/libqmlassetdownloaderprivateplugin.a"
# PySide's deployment scanner mistakes this static Qt archive for a shared
# library. Keep the backup outside the disposable staging directory so a
# cancelled build can restore it on the next invocation.
ASSET_BACKUP="$PROJECT_ROOT/.nuitka-cache/libqmlassetdownloaderprivateplugin.a"
restore_build_state() {
  if [[ -f "$ASSET_BACKUP" ]]; then
    mv "$ASSET_BACKUP" "$ASSET_ARCHIVE"
  fi
  rm -rf "$BUILD_STAGE"
}
trap restore_build_state EXIT
if [[ -f "$ASSET_BACKUP" && ! -f "$ASSET_ARCHIVE" ]]; then
  mv "$ASSET_BACKUP" "$ASSET_ARCHIVE"
fi
if [[ -f "$ASSET_ARCHIVE" ]]; then
  mv "$ASSET_ARCHIVE" "$ASSET_BACKUP"
fi
cp run_desktop.py Warraq.pyproject pysidedeploy.spec "$BUILD_STAGE/"
cp -R waraq "$BUILD_STAGE/"
cd "$BUILD_STAGE"
"$PROJECT_ROOT/.venv-desktop/bin/pyside6-deploy" -c pysidedeploy.spec --force
if [[ ! -d Warraq.app/Contents/MacOS ]]; then
  print -u2 "The application bundle was not created. Review the pyside6-deploy output above."
  exit 1
fi
cd "$PROJECT_ROOT"
if [[ -d Warraq.app ]]; then
  mv Warraq.app "/tmp/Warraq-previous-$EPOCHSECONDS.app"
fi
cp -R "$BUILD_STAGE/Warraq.app" Warraq.app
print "Built macOS application bundle. Check the deployment output above for Warraq.app."
