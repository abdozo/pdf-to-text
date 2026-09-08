#!/bin/zsh
set -u
cd "${0:A:h}/.." || exit 1

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 is required to stop a source checkout of Warraq."
  read "REPLY?Press Return to close this window..."
  exit 1
fi

if ! python3 scripts/manage_warraq.py stop; then
  read "REPLY?Press Return to close this window..."
  exit 1
fi
