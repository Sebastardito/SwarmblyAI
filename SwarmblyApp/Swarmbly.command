#!/usr/bin/env bash
# macOS: double-click this file in Finder to start Swarmbly App.
# A Terminal window shows the checks; closing it stops the app.
cd "$(dirname "$0")"
./launch.sh "$@"
status=$?
if [[ $status -ne 0 ]]; then
  echo
  read -r -p "Press Return to close this window." _
fi
exit $status
