#!/bin/bash
# Swarmbly AI — double-click installer for macOS (opens Terminal).
cd "$(dirname "$0")"
./install.sh "$@"
status=$?
echo
read -r -p "Pulsa Enter para cerrar / Press Enter to close… " _
exit $status
