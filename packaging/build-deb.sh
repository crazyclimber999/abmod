#!/bin/bash
#
# Builds abmod_<version>_all.deb from src/.
#
# Run it on any Debian machine with dpkg-dev - the receiver itself will do, it
# only writes into a temporary directory. The package is Architecture: all
# because everything in it is python, javascript and html, so a package built
# on a laptop installs on a Raspberry Pi unchanged.
#
set -euo pipefail

qui="$(cd "$(dirname "$0")" && pwd)"
radice="$(cd "$qui/.." && pwd)"
sorgente="$radice/src"
versione="$(cat "$qui/VERSION")"
uscita="${1:-$radice}"

dire() { printf '  %s\n' "$*"; }
muori() { printf '\nbuild-deb: %s\n\n' "$*" >&2; exit 1; }

command -v dpkg-deb >/dev/null || muori "dpkg-deb not found. Install dpkg-dev."
[ -d "$sorgente" ] || muori "Source tree not found: $sorgente"

# ---------------------------------------------------------------- the file list

# Lines that are not comments, with whitespace collapsed: the same list the
# maintainer scripts need, and the list this build checks against reality.
diverted="$(grep -vE '^\s*(#|$)' "$qui/diverted-files.txt")"
quanti_diverted="$(printf '%s\n' "$diverted" | wc -l | tr -d ' ')"

# If openwebrx is installed here, the list can be checked rather than trusted.
# A file ABMod replaces that openwebrx does NOT own needs no diversion; one it
# does own and the list omits would make dpkg refuse to unpack the package.
if dpkg-query -W openwebrx >/dev/null 2>&1; then
    posseduti="$(dpkg -L openwebrx | sort)"
    atteso="$(cd "$sorgente" && find . -type f ! -name '._*' ! -name '.DS_Store' | sed 's|^\./||' | sort | while IFS= read -r rel; do
        if printf '%s\n' "$posseduti" | grep -qxF "/usr/lib/python3/dist-packages/$rel"; then
            printf '%s\n' "$rel"
        fi
    done)"
    if [ "$atteso" != "$(printf '%s\n' "$diverted" | sort)" ]; then
        printf '\nbuild-deb: diverted-files.txt does not match the openwebrx installed here.\n' >&2
        printf 'Regenerate it with packaging/list-diverted.sh and commit the result.\n\n' >&2
        diff <(printf '%s\n' "$diverted" | sort) <(printf '%s\n' "$atteso") >&2 || true
        exit 1
    fi
    dire "diverted list checked against the openwebrx installed here: matches"
else
    dire "openwebrx not installed here - diverted list taken on trust"
fi

# ------------------------------------------------------------------ the staging

stanza="$(mktemp -d)"
trap 'rm -rf "$stanza"' EXIT

install -d "$stanza/usr/lib/python3/dist-packages"
# The exclusions matter: this tree is edited on a Mac, and a tar of it invents
# an AppleDouble "._name" beside every file carrying an extended attribute.
# One of those shipped inside a package is at best noise and at worst a file
# the receiver tries to import.
trova_sorgenti() {
    (cd "$sorgente" && find . -type f ! -name '._*' ! -name '.DS_Store' "$@")
}
trova_sorgenti -print0 | while IFS= read -r -d '' percorso; do
    rel="${percorso#./}"
    install -D -m 644 "$sorgente/$rel" "$stanza/usr/lib/python3/dist-packages/$rel"
done
n_file="$(find "$stanza/usr/lib/python3/dist-packages" -type f | wc -l | tr -d ' ')"
dire "$n_file files staged ($quanti_diverted of them diverted, $((n_file - quanti_diverted)) new)"

# Documentation, where a Debian package is expected to keep it.
doc="$stanza/usr/share/doc/abmod"
install -D -m 644 "$radice/README.md"      "$doc/README.md"
install -D -m 644 "$radice/README.it.md"   "$doc/README.it.md"
install -D -m 644 "$radice/CHANGELOG.md"   "$doc/CHANGELOG.md"
install -D -m 644 "$qui/debian/copyright"  "$doc/copyright"
gzip -9nc "$qui/debian/changelog.Debian" > "$doc/changelog.Debian.gz"
chmod 644 "$doc/changelog.Debian.gz"

# ----------------------------------------------------------- the control part

install -d -m 755 "$stanza/DEBIAN"
dimensione="$(du -sk "$stanza" | cut -f1)"
lista_una_riga="$(printf '%s\n' "$diverted" | tr '\n' ' ' | sed 's/ *$//')"

sostituisci() {
    sed -e "s|@VERSION@|$versione|g" \
        -e "s|@SIZE@|$dimensione|g" \
        -e "s|@FILES@|$lista_una_riga|g" "$1"
}

sostituisci "$qui/debian/control.in"  > "$stanza/DEBIAN/control"
for script in preinst postinst postrm; do
    sostituisci "$qui/debian/$script.in" > "$stanza/DEBIAN/$script"
    chmod 755 "$stanza/DEBIAN/$script"
    bash -n "$stanza/DEBIAN/$script" || muori "$script does not parse"
done
dire "maintainer scripts generated and syntax checked"

(cd "$stanza" && find usr -type f -print0 | xargs -0 md5sum | sed 's| usr/| usr/|' > DEBIAN/md5sums)
chmod 644 "$stanza/DEBIAN/md5sums"

# ------------------------------------------------------------------- the build

pacchetto="$uscita/abmod_${versione}_all.deb"
dpkg-deb --root-owner-group --build "$stanza" "$pacchetto" >/dev/null
dire "built $pacchetto"
dire "$(du -h "$pacchetto" | cut -f1) on disk"

# A package that does not list what you expect is worth catching here.
elenco="$stanza/contenuto.txt"
dpkg-deb --contents "$pacchetto" > "$elenco"
atteso_n="$(trova_sorgenti | wc -l | tr -d ' ')"
dentro_n="$(grep -c ' \./usr/lib/python3/dist-packages/.*[^/]$' "$elenco" || true)"
[ "$dentro_n" = "$atteso_n" ] || muori "package holds $dentro_n of $atteso_n source files - do not ship it"
grep -q 'dist-packages/owrx/terrain.py$' "$elenco" || muori "a known file is missing - do not ship it"
if grep -q '/\._' "$elenco"; then
    muori "package contains AppleDouble files - do not ship it"
fi
dire "contents verified: $dentro_n files, nothing stray"

printf '\n  Install it with:\n    sudo apt-get install %s\n\n' "$pacchetto"
