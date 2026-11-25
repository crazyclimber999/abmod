#!/bin/bash
#
# Turns one or more .deb files into an APT repository that apt-get can be
# pointed at. Produces a directory you copy to any plain web server - there is
# nothing dynamic about an APT repository, it is files.
#
# Usage:
#   packaging/repo/build-repo.sh --out /var/www/abmod abmod_1.0.0_all.deb
#   packaging/repo/build-repo.sh --out ... --key <gpg-key-id> abmod_*.deb
#
# Without --key the repository is unsigned, and every apt-get on every
# receiver has to be told to trust it anyway ([trusted=yes]), which also
# disables the check that the files are the ones you published. Sign it.
#
set -euo pipefail

suite="${SUITE:-bullseye}"
componente=main
architetture="all"
uscita=""
chiave=""
pacchetti=()

while [ $# -gt 0 ]; do
    case "$1" in
        --out) uscita="$2"; shift 2 ;;
        --key) chiave="$2"; shift 2 ;;
        --suite) suite="$2"; shift 2 ;;
        -*) echo "unknown option: $1" >&2; exit 1 ;;
        *) pacchetti+=("$1"); shift ;;
    esac
done

dire() { printf '  %s\n' "$*"; }
muori() { printf '\nbuild-repo: %s\n\n' "$*" >&2; exit 1; }

[ -n "$uscita" ] || muori "--out is required"
[ ${#pacchetti[@]} -gt 0 ] || muori "give it at least one .deb"
command -v dpkg-scanpackages >/dev/null || muori "dpkg-scanpackages not found. Install dpkg-dev."

pool="$uscita/pool/$componente"
binario="$uscita/dists/$suite/$componente/binary-all"
install -d "$pool" "$binario"

for p in "${pacchetti[@]}"; do
    [ -f "$p" ] || muori "no such file: $p"
    install -m 644 "$p" "$pool/$(basename "$p")"
    dire "pooled $(basename "$p")"
done

# Paths inside Packages must be relative to the repository root, which is why
# this runs from there rather than passing absolute paths.
(cd "$uscita" && dpkg-scanpackages --multiversion "pool/$componente" /dev/null > "dists/$suite/$componente/binary-all/Packages")
gzip -9nc "$binario/Packages" > "$binario/Packages.gz"
dire "$(grep -c '^Package:' "$binario/Packages") package(s) indexed"

# The Release file lists the indices with their sizes and hashes. apt refuses
# anything whose hash does not match, which is the point.
scrivi_release() {
    local dist="$uscita/dists/$suite"
    {
        printf 'Origin: ABMod\n'
        printf 'Label: ABMod for OpenWebRX\n'
        printf 'Suite: %s\n' "$suite"
        printf 'Codename: %s\n' "$suite"
        printf 'Architectures: %s\n' "$architetture"
        printf 'Components: %s\n' "$componente"
        printf 'Description: ABMod packages for OpenWebRX\n'
        printf 'Date: %s\n' "$(date -Ru)"
        for algoritmo in MD5Sum:md5sum SHA256:sha256sum; do
            printf '%s:\n' "${algoritmo%%:*}"
            local comando="${algoritmo##*:}"
            (cd "$dist" && find . -type f ! -name 'Release*' ! -name 'InRelease' -printf '%P\n' | sort | while IFS= read -r f; do
                printf ' %s %16d %s\n' "$($comando "$f" | cut -d' ' -f1)" "$(stat -c%s "$f")" "$f"
            done)
        done
    } > "$dist/Release"
}
scrivi_release
dire "Release written"

if [ -n "$chiave" ]; then
    rm -f "$uscita/dists/$suite/Release.gpg" "$uscita/dists/$suite/InRelease"
    gpg --default-key "$chiave" --armor --detach-sign \
        --output "$uscita/dists/$suite/Release.gpg" "$uscita/dists/$suite/Release"
    gpg --default-key "$chiave" --clearsign \
        --output "$uscita/dists/$suite/InRelease" "$uscita/dists/$suite/Release"
    gpg --export --armor "$chiave" > "$uscita/abmod-archive-keyring.asc"
    dire "signed with $chiave, public key at $uscita/abmod-archive-keyring.asc"
    firmato=yes
else
    dire "NOT signed - see the note in this script's header"
    firmato=no
fi

printf '\n  Repository ready in %s\n' "$uscita"
printf '  Serve that directory over http(s), then on each receiver:\n\n'
if [ "$firmato" = yes ]; then
    printf '    sudo curl -fsSL https://YOUR.HOST/abmod-archive-keyring.asc \\\n'
    printf '      -o /usr/share/keyrings/abmod.asc\n'
    printf '    echo "deb [signed-by=/usr/share/keyrings/abmod.asc] https://YOUR.HOST/ %s %s" \\\n' "$suite" "$componente"
    printf '      | sudo tee /etc/apt/sources.list.d/abmod.list\n'
else
    printf '    echo "deb [trusted=yes] https://YOUR.HOST/ %s %s" \\\n' "$suite" "$componente"
    printf '      | sudo tee /etc/apt/sources.list.d/abmod.list\n'
fi
printf '    sudo apt-get update && sudo apt-get install abmod\n\n'
