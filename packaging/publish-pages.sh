#!/bin/bash
#
# Builds the package, builds a signed APT repository from it, and publishes the
# result to the gh-pages branch, which GitHub Pages serves at
# https://crazyclimber999.github.io/abmod/
#
# Signing happens HERE, on your machine, not in CI. That is deliberate: signing
# in a GitHub Action would mean putting the private key in a repository secret,
# and a signing key whose job is to prove the packages came from you is worth
# rather more than the convenience of not typing a command. The Action builds
# and checks the package; publishing it is one command you run.
#
# Usage:
#   packaging/publish-pages.sh                 # one secret key present: uses it
#   packaging/publish-pages.sh --key <keyid>   # pick one explicitly
#   packaging/publish-pages.sh --dry-run       # build everything, push nothing
#
set -euo pipefail

qui="$(cd "$(dirname "$0")" && pwd)"
radice="$(cd "$qui/.." && pwd)"
versione="$(cat "$qui/VERSION")"
remoto="https://github.com/crazyclimber999/abmod.git"

chiave=""
dryrun=no
while [ $# -gt 0 ]; do
    case "$1" in
        --key) chiave="$2"; shift 2 ;;
        --dry-run) dryrun=yes; shift ;;
        *) echo "unknown option: $1" >&2; exit 1 ;;
    esac
done

dire() { printf '  %s\n' "$*"; }
passo() { printf '\n%s\n' "$*"; }
muori() { printf '\npublish-pages: %s\n\n' "$*" >&2; exit 1; }

command -v gpg >/dev/null || muori "gpg not found"

# Building a .deb and indexing a repository need Debian's own tools, so this
# runs on a Debian machine - in practice the receiver. That is also where the
# signing key has to be, which is a real trade-off and worth stating plainly:
# a key on a receiver reachable from the internet is more exposed than one on
# a laptop. The alternatives are a key in a GitHub secret, so an Action can
# publish, or keeping the whole repository on your own web space. Pick
# knowingly rather than by default.
if ! command -v dpkg-deb >/dev/null || ! command -v dpkg-scanpackages >/dev/null; then
    cat >&2 <<SENZADPKG

This has to run on a Debian machine: building the package needs dpkg-deb and
indexing the repository needs dpkg-scanpackages, and neither exists here.

Run it on the receiver, with the signing key there:

    tar czf - --exclude .git . | ssh pi@receiver 'mkdir -p ~/abmod && tar xzf - -C ~/abmod'
    ssh -t pi@receiver 'cd ~/abmod && packaging/publish-pages.sh'

On a Mac, set COPYFILE_DISABLE=1 on that tar or it invents AppleDouble files.

SENZADPKG
    exit 1
fi

# ------------------------------------------------------------------- the key

if [ -z "$chiave" ]; then
    # No mapfile: macOS still ships bash 3.2, and this script is meant to run
    # on the machine that holds the key.
    trovate="$(gpg --list-secret-keys --with-colons 2>/dev/null | awk -F: '$1=="fpr"{print $10}' | sort -u)"
    quante=0
    [ -n "$trovate" ] && quante="$(printf '%s\n' "$trovate" | wc -l | tr -d ' ')"
    case "$quante" in
        0) cat >&2 <<SENZACHIAVE

No signing key found, and this repository should not be published unsigned.

Unsigned, every receiver has to be told [trusted=yes] to use the repository at
all, and that flag does not skip a formality: it disables the check that the
package being installed is the one that was published. On a machine that runs
as a network service, that is the wrong corner to cut.

Make a key - you choose the passphrase, which is why this script will not make
one for you:

    gpg --full-generate-key

Take the defaults (ECC, sign only is fine), give it a name and an address you
are happy to publish, and set a passphrase. Then run this again.

SENZACHIAVE
           exit 1 ;;
        1) chiave="$trovate"; dire "signing with the only key present: $chiave" ;;
        *) printf '\npublish-pages: several secret keys here - pick one with --key:\n\n' >&2
           gpg --list-secret-keys --keyid-format=long >&2
           exit 1 ;;
    esac
fi
gpg --list-secret-keys "$chiave" >/dev/null 2>&1 || muori "no secret key matching $chiave"

# ------------------------------------------------------------ build and index

passo "Building the package"
"$qui/build-deb.sh" "$radice" | sed 's/^/  /'
pacchetto="$radice/abmod_${versione}_all.deb"
[ -f "$pacchetto" ] || muori "the package was not produced"

lavoro="$(mktemp -d)"
trap 'rm -rf "$lavoro"' EXIT

passo "Building the signed repository"
"$qui/repo/build-repo.sh" --out "$lavoro/apt" --key "$chiave" "$pacchetto" | sed 's/^/  /'

for atteso in dists/bullseye/Release dists/bullseye/InRelease dists/bullseye/Release.gpg abmod-archive-keyring.asc; do
    [ -f "$lavoro/apt/$atteso" ] || muori "the repository is missing $atteso"
done
dire "signatures and keyring present"

# ---------------------------------------------------------------- the publish

passo "Publishing to gh-pages"
git clone -q --depth 1 --branch gh-pages "$remoto" "$lavoro/pages" \
    || muori "could not fetch the gh-pages branch"
cd "$lavoro/pages"

# index.html and .nojekyll live on that branch and are not ours to regenerate;
# everything the repository itself owns is replaced wholesale, so a package
# that was withdrawn does not linger in the pool.
rm -rf dists pool abmod-archive-keyring.asc
cp -R "$lavoro/apt/dists" "$lavoro/apt/pool" .
cp "$lavoro/apt/abmod-archive-keyring.asc" .
[ -f .nojekyll ] || muori "the gh-pages branch has lost its .nojekyll - Pages would mangle the tree"

if git diff --quiet && git diff --cached --quiet && [ -z "$(git status --porcelain)" ]; then
    dire "nothing changed - already published"
    exit 0
fi

git add -A
git -c commit.gpgsign=false commit -q -m "Publish abmod $versione" \
    -m "Signed with $chiave. Built by packaging/publish-pages.sh."

if [ "$dryrun" = yes ]; then
    dire "--dry-run: committed locally in $lavoro/pages, nothing pushed"
    trap - EXIT
    printf '\n  Inspect it, then delete %s when done.\n\n' "$lavoro"
    exit 0
fi

git push -q origin gh-pages
dire "pushed"

passo "Checking what is actually served"
base=https://crazyclimber999.github.io/abmod
for tentativo in 1 2 3 4 5 6 7 8; do
    codice="$(curl -s -o /dev/null -w '%{http_code}' "$base/dists/bullseye/InRelease")"
    [ "$codice" = 200 ] && break
    sleep 15
done
[ "$codice" = 200 ] || muori "Pages is not serving InRelease yet (HTTP $codice) - check again in a minute"
for percorso in dists/bullseye/InRelease dists/bullseye/main/binary-all/Packages.gz \
                "pool/main/abmod_${versione}_all.deb" abmod-archive-keyring.asc; do
    codice="$(curl -s -o /dev/null -w '%{http_code}' "$base/$percorso")"
    [ "$codice" = 200 ] || muori "$percorso is not being served (HTTP $codice)"
    dire "$percorso served"
done

cat <<FATTO

  Published: $base

  On each receiver, once:

    sudo curl -fsSL $base/abmod-archive-keyring.asc \\
      -o /usr/share/keyrings/abmod.asc
    echo "deb [signed-by=/usr/share/keyrings/abmod.asc] $base/ bullseye main" \\
      | sudo tee /etc/apt/sources.list.d/abmod.list

  and from then on:

    sudo apt-get update && sudo apt-get install abmod

FATTO
