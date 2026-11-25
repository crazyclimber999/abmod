#!/usr/bin/env bash
#
# ABMod - put a receiver back the way it was before the upgrade.

set -euo pipefail
QUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$QUI/lib.sh"

richiedi_root
BACKUP="${1:-}"
[ -n "$BACKUP" ] || muori "Usage: $0 /root/abmod-backup-YYYYmmdd-HHMMSS"
[ -d "$BACKUP" ] || muori "No such backup: $BACKUP"
ARCHIVIO="$BACKUP/openwebrx-files.tgz"
[ -f "$ARCHIVIO" ] || muori "The backup has no openwebrx-files.tgz"

INSTALLAZIONE="$(trova_openwebrx)" || muori "Cannot find the OpenWebRX installation"

dire ""
dire "This will replace $INSTALLAZIONE/owrx and $INSTALLAZIONE/htdocs"
dire "with the contents of $ARCHIVIO."
printf 'Continue? [y/N] '
read -r risposta
case "$risposta" in [yY]*) ;; *) muori "Stopped. Nothing changed." ;; esac

passo "Restoring the files"
tar xzf "$ARCHIVIO" -C "$(dirname "$INSTALLAZIONE")"
dire "    restored"

# The configuration is deliberately NOT restored: the upgrade never changes
# it, so whatever is there now is the operator's own and more recent.
dire ""
dire "    settings.json, bookmarks and users were left as they are -"
dire "    the upgrade never touches them. Copies are in $BACKUP if you want them."

riavvia_e_verifica "${ABMOD_PORT:-8073}" || true
svuota_varnish
dire ""
dire "Rollback finished."
