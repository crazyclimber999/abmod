#!/bin/bash
#
# Regenerates diverted-files.txt: the files ABMod replaces that the openwebrx
# package owns. Run it against a receiver with a PRISTINE openwebrx - over a
# hand-installed ABMod the answer is the same, but verify first with
# "dpkg -V openwebrx" and expect it to list exactly these files.
#
# Usage: packaging/list-diverted.sh [user@host]
#        with no argument, reads the openwebrx installed on this machine.
#
set -euo pipefail

qui="$(cd "$(dirname "$0")" && pwd)"
sorgente="$(cd "$qui/.." && pwd)/src"
remoto="${1:-}"

if [ -n "$remoto" ]; then
    posseduti="$(ssh "$remoto" 'dpkg -L openwebrx')"
else
    posseduti="$(dpkg -L openwebrx)"
fi

intestazione="$(sed -n '1,/^[^#]/p' "$qui/diverted-files.txt" | grep -E '^\s*(#|$)')"

{
    printf '%s\n' "$intestazione"
    (cd "$sorgente" && find . -type f | sed 's|^\./||' | sort) | while IFS= read -r rel; do
        if printf '%s\n' "$posseduti" | grep -qxF "/usr/lib/python3/dist-packages/$rel"; then
            printf '%s\n' "$rel"
        fi
    done
} > "$qui/diverted-files.txt.nuovo"

if cmp -s "$qui/diverted-files.txt" "$qui/diverted-files.txt.nuovo"; then
    rm "$qui/diverted-files.txt.nuovo"
    echo "  unchanged"
else
    mv "$qui/diverted-files.txt.nuovo" "$qui/diverted-files.txt"
    echo "  diverted-files.txt updated - review the diff and commit it"
fi
