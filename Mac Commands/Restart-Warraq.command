#!/bin/zsh
set -u
cd "${0:A:h}/.." || exit 1

if ! command -v python3 >/dev/null 2>&1; then
  echo "Warraq requires Python 3.11 or newer. Install Python, then try again."
  read "REPLY?Press Return to close this window..."
  exit 1
fi

if ! python3 scripts/manage_warraq.py restart; then
  echo
  echo "Warraq did not restart. The error and log path are shown above."
  read "REPLY?Press Return to close this window..."
  exit 1
fi
