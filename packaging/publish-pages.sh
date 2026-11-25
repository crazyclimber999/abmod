#!/bin/bash
#
# Publishes the APT repository to the gh-pages branch, which GitHub Pages
# serves at https://crazyclimber999.github.io/abmod/
#
# It comes in two halves, because the two things it needs rarely live on the
# same machine:
#
#   --build  needs dpkg-deb, dpkg-scanpackages and the signing key, so it runs
#            on a Debian box - in practice the receiver.
#   --push   needs credentials to push to GitHub, so it runs wherever those
#            are - in practice the machine you work on.
#
#   on the receiver:   packaging/publish-pages.sh --build --out ~/abmod-apt
#   copy it back:      scp -r pi@receiver:abmod-apt ./apt
#   on your machine:   packaging/publish-pages.sh --push ./apt
#
# With neither flag it does both, which works only where both halves can.
#
# Signing happens in --build, never in CI. Signing in a GitHub Action would
# mean putting the private key in a repository secret, and a key whose whole
# job is to prove the packages came from you is worth more than the
# convenience of not typing a command.
#
set -euo pipefail

qui="$(cd "$(dirname "$0")" && pwd)"
radice="$(cd "$qui/.." && pwd)"
versione="$(cat "$qui/VERSION")"
remoto="https://github.com/crazyclimber999/abmod.git"
base_pubblica=https://crazyclimber999.github.io/abmod

fase=entrambe
chiave=""
uscita=""
dryrun=no
while [ $# -gt 0 ]; do
    case "$1" in
        --build) fase=build; shift ;;
        --push)  fase=push; uscita="$2"; shift 2 ;;
        --out)   uscita="$2"; shift 2 ;;
        --key)   chiave="$2"; shift 2 ;;
        --dry-run) dryrun=yes; shift ;;
        *) echo "unknown option: $1" >&2; exit 1 ;;
    esac
done

dire() { printf '  %s\n' "$*"; }
passo() { printf '\n%s\n' "$*"; }
muori() { printf '\npublish-pages: %s\n\n' "$*" >&2; exit 1; }

# ========================================================== build and sign

costruisci() {
    command -v gpg >/dev/null || muori "gpg not found"
    if ! command -v dpkg-deb >/dev/null || ! command -v dpkg-scanpackages >/dev/null; then
        cat >&2 <<SENZADPKG

--build has to run on a Debian machine: building the package needs dpkg-deb and
indexing the repository needs dpkg-scanpackages, and neither exists here.

Run this half on the receiver, where the signing key is, then bring the result
back and run --push here:

    tar czf - --exclude .git . | ssh pi@receiver 'mkdir -p ~/abmod && tar xzf - -C ~/abmod'
    ssh pi@receiver 'cd ~/abmod && packaging/publish-pages.sh --build --out ~/abmod-apt'
    scp -r pi@receiver:abmod-apt ./apt
    packaging/publish-pages.sh --push ./apt

On a Mac, set COPYFILE_DISABLE=1 on that tar or it invents AppleDouble files.

SENZADPKG
        exit 1
    fi

    # ---------------------------------------------------------------- the key
    if [ -z "$chiave" ]; then
        # No mapfile: macOS still ships bash 3.2 and this script runs there too.
        trovate="$(gpg --list-secret-keys --with-colons 2>/dev/null | awk -F: '$1=="fpr"{print $10}' | sort -u)"
        quante=0
        [ -n "$trovate" ] && quante="$(printf '%s\n' "$trovate" | wc -l | tr -d ' ')"
        case "$quante" in
            0) cat >&2 <<SENZACHIAVE

No signing key here, and this repository should not be published unsigned.

Unsigned, every receiver has to be told [trusted=yes] to use it at all, and
that flag does not skip a formality: it disables the check that the package
being installed is the one that was published. apt installs as root, so that
check is what stands between a swapped package and root on the receiver.

Make a key - you choose the passphrase, which is why this script will not make
one for you:

    gpg --full-generate-key

SENZACHIAVE
               exit 1 ;;
            1) chiave="$trovate"; dire "signing with the only key here: $chiave" ;;
            *) printf '\npublish-pages: several secret keys here - pick one with --key:\n\n' >&2
               gpg --list-secret-keys --keyid-format=long >&2
               exit 1 ;;
        esac
    fi
    gpg --list-secret-keys "$chiave" >/dev/null 2>&1 || muori "no secret key matching $chiave"

    [ -n "$uscita" ] || muori "--build needs --out <directory>"
    rm -rf "$uscita"

    passo "Building the package"
    "$qui/build-deb.sh" "$radice" | sed 's/^/  /'
    pacchetto="$radice/abmod_${versione}_all.deb"
    [ -f "$pacchetto" ] || muori "the package was not produced"

    passo "Building the signed repository"
    "$qui/repo/build-repo.sh" --out "$uscita" --key "$chiave" "$pacchetto" | sed 's/^/  /'

    for atteso in dists/bullseye/Release dists/bullseye/InRelease \
                  dists/bullseye/Release.gpg abmod-archive-keyring.asc \
                  "pool/main/abmod_${versione}_all.deb"; do
        [ -f "$uscita/$atteso" ] || muori "the repository is missing $atteso"
    done
    dire "indices, signatures, keyring and package all present"

    # A signature nobody checked is a signature that might not verify. Check it
    # against the public half exactly as it will be published, not against the
    # keyring that happens to be lying around on this machine.
    anello="$(mktemp -d)"
    chmod 700 "$anello"
    gpg --homedir "$anello" --quiet --import "$uscita/abmod-archive-keyring.asc" 2>/dev/null
    if ! gpg --homedir "$anello" --quiet --verify "$uscita/dists/bullseye/Release.gpg" \
            "$uscita/dists/bullseye/Release" 2>/dev/null; then
        rm -rf "$anello"; muori "Release.gpg does not verify against the published key"
    fi
    if ! gpg --homedir "$anello" --quiet --verify "$uscita/dists/bullseye/InRelease" 2>/dev/null; then
        rm -rf "$anello"; muori "InRelease does not verify against the published key"
    fi
    rm -rf "$anello"
    dire "both signatures verify against the key that will be published"

    printf '\n  Built in %s\n' "$uscita"
    printf '  Bring it to a machine that can push, and run:\n'
    printf '    packaging/publish-pages.sh --push <that directory>\n\n'
}

# ================================================================== publish

pubblica() {
    [ -n "$uscita" ] || muori "--push needs the directory that --build produced"
    [ -d "$uscita/dists" ] || muori "$uscita does not look like a built repository"
    uscita="$(cd "$uscita" && pwd)"

    lavoro="$(mktemp -d)"
    trap 'rm -rf "$lavoro"' EXIT

    passo "Fetching the gh-pages branch"
    git clone -q --depth 1 --branch gh-pages "$remoto" "$lavoro/pages" \
        || muori "could not fetch gh-pages"
    cd "$lavoro/pages"

    # index.html and .nojekyll live on that branch and are not ours to
    # regenerate. Everything the repository itself owns is replaced wholesale,
    # so a withdrawn package does not linger in the pool.
    rm -rf dists pool abmod-archive-keyring.asc
    cp -R "$uscita/dists" "$uscita/pool" .
    cp "$uscita/abmod-archive-keyring.asc" .
    [ -f .nojekyll ] || muori "gh-pages has lost its .nojekyll - Pages would mangle the tree"

    if [ -z "$(git status --porcelain)" ]; then
        dire "nothing changed - already published"
        return 0
    fi

    git add -A
    git -c commit.gpgsign=false commit -q -m "Publish abmod $versione" \
        -m "Built and signed by packaging/publish-pages.sh --build."

    if [ "$dryrun" = yes ]; then
        trap - EXIT
        printf '  --dry-run: committed in %s, nothing pushed.\n\n' "$lavoro/pages"
        return 0
    fi

    git push -q origin gh-pages
    dire "pushed"

    passo "Checking what Pages actually serves"
    # A push that succeeded says what was sent, not what the world can see.
    codice=000
    for tentativo in 1 2 3 4 5 6 7 8 9 10; do
        codice="$(curl -s -o /dev/null -w '%{http_code}' "$base_pubblica/dists/bullseye/InRelease")"
        [ "$codice" = 200 ] && break
        sleep 15
    done
    [ "$codice" = 200 ] || muori "Pages is not serving InRelease yet (HTTP $codice) - try again shortly"

    for percorso in dists/bullseye/InRelease dists/bullseye/Release dists/bullseye/Release.gpg \
                    dists/bullseye/main/binary-all/Packages.gz \
                    "pool/main/abmod_${versione}_all.deb" abmod-archive-keyring.asc; do
        codice="$(curl -s -o /dev/null -w '%{http_code}' "$base_pubblica/$percorso")"
        [ "$codice" = 200 ] || muori "$percorso is not served (HTTP $codice)"
        dire "$percorso"
    done

    # And the package being served must be the package that was built.
    somma() { if command -v sha256sum >/dev/null; then sha256sum; else shasum -a 256; fi; }
    locale="$(somma < "$uscita/pool/main/abmod_${versione}_all.deb" | cut -d' ' -f1)"
    servito="$(curl -fsSL "$base_pubblica/pool/main/abmod_${versione}_all.deb" | somma | cut -d' ' -f1)"
    [ "$locale" = "$servito" ] || muori "the served package is not the one built ($locale vs $servito)"
    dire "the served package matches the built one"

    cat <<FATTO

  Published: $base_pubblica

  On each receiver, once:

    sudo curl -fsSL $base_pubblica/abmod-archive-keyring.asc \\
      -o /usr/share/keyrings/abmod.asc
    echo "deb [signed-by=/usr/share/keyrings/abmod.asc] $base_pubblica/ bullseye main" \\
      | sudo tee /etc/apt/sources.list.d/abmod.list

  and from then on:

    sudo apt-get update && sudo apt-get install abmod

FATTO
}

case "$fase" in
    build) costruisci ;;
    push)  pubblica ;;
    entrambe)
        [ -n "$uscita" ] || uscita="$radice/apt"
        costruisci
        pubblica
        ;;
esac
