#!/usr/bin/env bash
#
# ABMod - install on a machine that has no OpenWebRX yet.
#
# ABMod is a set of changes to OpenWebRX, not a replacement for it, so this
# installs OpenWebRX first and then applies ABMod on top. OpenWebRX itself is
# installed from its own packages: this script deliberately does NOT carry a
# copy of upstream's repository addresses, because a stale URL baked in here
# would fail confusingly a year from now. If the package is not reachable it
# says so and points at upstream's own instructions.

set -euo pipefail
QUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$QUI/lib.sh"

PORTA="${ABMOD_PORT:-8073}"
MARCA="$(date +%Y%m%d-%H%M%S)"

dire ""
dire "ABMod - installing from scratch"
dire "==============================="

richiedi_root

command -v apt-get >/dev/null 2>&1 || muori \
    "This script expects a Debian-like system (Raspberry Pi OS, Debian, Ubuntu).
     On anything else, install OpenWebRX the way its own documentation says,
     then run upgrade.sh from this folder."

passo "Is OpenWebRX already here?"
if INSTALLAZIONE="$(trova_openwebrx)"; then
    dire "    yes, in $INSTALLAZIONE (version $(versione_openwebrx))"
    avviso "Nothing to install. To put ABMod on top of it, run:"
    avviso "  sudo $QUI/upgrade.sh"
    exit 0
fi
dire "    no - installing it"

passo "Installing OpenWebRX"
apt-get update >/dev/null 2>&1 || avviso "apt-get update reported problems; carrying on"
if ! apt-get install -y openwebrx >/dev/null 2>&1; then
    errore "The 'openwebrx' package is not available from the repositories on this machine."
    errore ""
    errore "Add OpenWebRX's own package repository first - the current instructions are at"
    errore "    https://github.com/jketterl/openwebrx/wiki"
    errore "then run this script again. It will pick up from here."
    exit 1
fi

INSTALLAZIONE="$(trova_openwebrx)" || muori "OpenWebRX was installed but cannot be found - stopping"
DATI="$(trova_dati)"
dire "    installed in $INSTALLAZIONE (version $(versione_openwebrx))"

# Even on a fresh machine: the package has just written its defaults and they
# are worth keeping, if only to compare against later.
BACKUP="/root/abmod-backup-$MARCA"
fai_backup "$BACKUP" "$INSTALLAZIONE" "$DATI"

applica_file "$QUI/../src" "$INSTALLAZIONE"
installa_dipendenze

systemctl enable openwebrx >/dev/null 2>&1 || true

if riavvia_e_verifica "$PORTA"; then
    svuota_varnish
    dire ""
    dire "${VERDE}Done.${NORMALE} OpenWebRX with ABMod is running on port $PORTA."
    dire ""
    dire "  Backup of the untouched install: $BACKUP"
    dire ""
    dire "Now, in this order:"
    dire ""
    dire "  1. Create the first administrator - the settings and the bookmarks"
    dire "     need a login, and without this nobody can get in:"
    dire ""
    dire "       sudo openwebrx admin adduser <name>"
    dire ""
    dire "  2. Open http://<this machine>:$PORTA/settings and set, at least:"
    dire "       - Receiver details: name, location and coordinates."
    dire "         The coordinates matter: they decide what the map centres on"
    dire "         and what the listenability filter measures from."
    dire "       - SDR devices and profiles: your receiver and the bands"
    dire "       - Receiving antenna: height above ground"
    dire ""
    dire "  3. Optional, under General settings:"
    dire "       - an aprs.fi API key, to show stations you cannot hear yourself"
    dire "       - an APRS-IS passcode, to forward what you do hear"
    dire ""
    dire "  Full documentation: docs/en/  (English)  docs/it/  (Italiano)"
else
    errore ""
    errore "OpenWebRX is installed but did not answer. Look at:"
    errore "  journalctl -u openwebrx -n 50"
    errore "To undo the ABMod part:  $QUI/rollback.sh $BACKUP"
    exit 1
fi
