#!/usr/bin/env bash
#
# Shared helpers for the ABMod install and upgrade scripts.
#
# Nothing here is specific to either path: finding the OpenWebRX installation,
# taking a backup that can actually be restored, copying the files in and
# checking afterwards that the receiver really came back.

set -u

ROSSO=$'\033[31m'; VERDE=$'\033[32m'; GIALLO=$'\033[33m'; NORMALE=$'\033[0m'

dire()      { printf '%s\n' "$*"; }
passo()     { printf '\n%s==>%s %s\n' "$VERDE" "$NORMALE" "$*"; }
avviso()    { printf '%s!!%s  %s\n' "$GIALLO" "$NORMALE" "$*"; }
errore()    { printf '%s!!%s  %s\n' "$ROSSO" "$NORMALE" "$*" >&2; }
muori()     { errore "$*"; exit 1; }

# --------------------------------------------------------------------------

richiedi_root() {
    if [ "$(id -u)" -ne 0 ]; then
        muori "Run this with sudo: sudo $0"
    fi
}

# Where OpenWebRX actually lives. Debian puts it in dist-packages, a pip
# install puts it in site-packages, and the path carries the python version,
# so it is found rather than assumed.
trova_openwebrx() {
    local trovato
    trovato=$(python3 - <<'PY' 2>/dev/null
import os
try:
    import owrx
    print(os.path.dirname(os.path.dirname(os.path.abspath(owrx.__file__))))
except ImportError:
    pass
PY
)
    if [ -n "$trovato" ] && [ -d "$trovato/owrx" ]; then
        printf '%s' "$trovato"
        return 0
    fi
    for d in /usr/lib/python3/dist-packages /usr/local/lib/python3*/dist-packages \
             /usr/lib/python3*/site-packages /usr/local/lib/python3*/site-packages; do
        if [ -d "$d/owrx" ]; then printf '%s' "$d"; return 0; fi
    done
    return 1
}

versione_openwebrx() {
    python3 - <<'PY' 2>/dev/null
try:
    from owrx.version import openwebrx_version
    print(openwebrx_version)
except Exception:
    print("unknown")
PY
}

# The data directory holds settings.json, bookmarks.json and users.json. It is
# read from OpenWebRX's own configuration rather than guessed, because a
# wrong guess means backing up the wrong files.
trova_dati() {
    local trovato
    trovato=$(python3 - <<'PY' 2>/dev/null
try:
    from owrx.config.core import CoreConfig
    print(CoreConfig().get_data_directory())
except Exception:
    pass
PY
)
    [ -n "$trovato" ] || trovato=/var/lib/openwebrx
    printf '%s' "$trovato"
}

# --------------------------------------------------------------------------

fai_backup() {
    local destinazione="$1" installazione="$2" dati="$3"
    mkdir -p "$destinazione" || muori "Cannot create $destinazione"

    passo "Backing up to $destinazione"
    tar czf "$destinazione/openwebrx-files.tgz" \
        -C "$(dirname "$installazione")" \
        "$(basename "$installazione")/owrx" "$(basename "$installazione")/htdocs" \
        2>/dev/null || avviso "The file backup reported problems; check it before continuing"

    local f
    for f in settings.json bookmarks.json users.json bands.json; do
        [ -f "$dati/$f" ] && cp -a "$dati/$f" "$destinazione/" 2>/dev/null
    done

    # A backup nobody has checked is not a backup.
    local quanti
    quanti=$(tar tzf "$destinazione/openwebrx-files.tgz" 2>/dev/null | wc -l | tr -d ' ')
    [ "${quanti:-0}" -gt 0 ] || muori "The backup archive is unreadable - stopping before changing anything"
    dire "    $quanti files archived, plus the configuration"
}

# --------------------------------------------------------------------------

applica_file() {
    local sorgente="$1" installazione="$2"
    [ -d "$sorgente" ] || muori "Source tree not found: $sorgente"

    passo "Installing the ABMod files"
    local n=0 percorso relativo destinazione
    while IFS= read -r percorso; do
        relativo="${percorso#"$sorgente"/}"
        destinazione="$installazione/$relativo"
        mkdir -p "$(dirname "$destinazione")"
        cp "$percorso" "$destinazione"
        chmod 644 "$destinazione"
        n=$((n + 1))
    done < <(find "$sorgente" -type f)
    dire "    $n files installed"

    # Every python file must at least parse. A syntax error here takes the
    # whole receiver down, and it is far cheaper to find it now.
    passo "Checking the installed python"
    python3 - "$installazione" <<'PY' || muori "A python file does not compile - restore the backup"
import py_compile, sys, os
base = sys.argv[1]
errori = 0
for radice, _, files in os.walk(os.path.join(base, "owrx")):
    for f in files:
        if f.endswith(".py"):
            try:
                py_compile.compile(os.path.join(radice, f), doraise=True, cfile="/tmp/abmod-check.pyc")
            except Exception as e:
                print("  %s: %s" % (os.path.join(radice, f), e))
                errori += 1
sys.exit(1 if errori else 0)
PY
    dire "    all files compile"
}

# --------------------------------------------------------------------------

installa_dipendenze() {
    passo "Optional dependency: python3-xlrd"
    if python3 -c "import xlrd" 2>/dev/null; then
        dire "    already present"
        return 0
    fi
    if command -v apt-get >/dev/null 2>&1; then
        apt-get install -y python3-xlrd >/dev/null 2>&1 \
            && dire "    installed" \
            || avviso "Could not install it. The bookmark importer will read .xlsx and .csv but not the old .xls format."
    else
        avviso "No apt here. Install xlrd by hand if you want to import old .xls files."
    fi
}

svuota_varnish() {
    if systemctl is-active --quiet varnish 2>/dev/null; then
        passo "Clearing the Varnish cache"
        varnishadm "ban req.url ~ ." >/dev/null 2>&1 \
            && dire "    cleared" \
            || avviso "Could not clear it; do it by hand or visitors may get the old interface"
    fi
}

riavvia_e_verifica() {
    passo "Restarting OpenWebRX"
    systemctl restart openwebrx || muori "The service would not restart - restore the backup"

    local porta="${1:-8073}" atteso=20 i=0 codice=""
    dire "    waiting for it to answer..."
    while [ "$i" -lt "$atteso" ]; do
        codice=$(curl -s -o /dev/null -w '%{http_code}' --max-time 3 "http://127.0.0.1:$porta/" 2>/dev/null || true)
        [ "$codice" = "200" ] && break
        sleep 2
        i=$((i + 1))
    done

    if [ "$codice" != "200" ]; then
        errore "The receiver is not answering on port $porta (last code: ${codice:-none})."
        errore "Look at: journalctl -u openwebrx -n 50"
        return 1
    fi
    dire "    answering on port $porta"

    # A service that is up but logging tracebacks is not a success.
    local tracce
    tracce=$(journalctl -u openwebrx --since "2 minutes ago" --no-pager 2>/dev/null | grep -c "Traceback" || true)
    if [ "${tracce:-0}" -gt 0 ]; then
        avviso "$tracce tracebacks since the restart. Some may be from the shutdown; check with:"
        avviso "  journalctl -u openwebrx --since '2 minutes ago' | grep -A10 Traceback"
    else
        dire "    no errors in the log"
    fi
    return 0
}
