#!/usr/bin/env bash
#
# ABMod - upgrade a receiver that already runs OpenWebRX.
#
# Changes nothing until it has a backup it has verified it can read, and
# checks afterwards that the receiver actually came back.

set -euo pipefail
QUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$QUI/lib.sh"

PORTA="${ABMOD_PORT:-8073}"
MARCA="$(date +%Y%m%d-%H%M%S)"

dire ""
dire "ABMod - upgrading an existing OpenWebRX"
dire "======================================="

richiedi_root

passo "Looking for OpenWebRX"
INSTALLAZIONE="$(trova_openwebrx)" || muori "OpenWebRX is not installed here. Use install.sh instead."
DATI="$(trova_dati)"
VERSIONE="$(versione_openwebrx)"
dire "    found in $INSTALLAZIONE"
dire "    version $VERSIONE"
dire "    data in $DATI"

# ABMod was built against 1.2.2. It may well work on a near neighbour, but
# saying so is better than finding out after the files are in place.
case "$VERSIONE" in
    v1.2.2|1.2.2) : ;;
    *)
        avviso "ABMod was built and tested against OpenWebRX v1.2.2."
        avviso "This receiver reports $VERSIONE. It may still work, but it is untested."
        printf '    Continue anyway? [y/N] '
        read -r risposta
        case "$risposta" in [yY]*) ;; *) muori "Stopped. Nothing has been changed." ;; esac
        ;;
esac

BACKUP="/root/abmod-backup-$MARCA"
fai_backup "$BACKUP" "$INSTALLAZIONE" "$DATI"

applica_file "$QUI/../src" "$INSTALLAZIONE"
installa_dipendenze

if riavvia_e_verifica "$PORTA"; then
    svuota_varnish
    dire ""
    dire "${VERDE}Done.${NORMALE} The receiver is running ABMod."
    dire ""
    dire "  Backup:        $BACKUP"
    dire "  To roll back:  $QUI/rollback.sh $BACKUP"
    dire ""
    dire "What to do next:"
    dire "  - Settings -> General: set the antenna height and, if you want them,"
    dire "    the aprs.fi key and the APRS-IS passcode"
    dire "  - the bookmarks and the settings now need a login; create the first"
    dire "    administrator with:  sudo openwebrx admin adduser <name>"
    dire ""
    dire "  Your own settings.json, bookmarks and users were not touched."
else
    errore ""
    errore "The receiver did not come back. Roll back with:"
    errore "  $QUI/rollback.sh $BACKUP"
    exit 1
fi
