# Installing with apt-get

*[In italiano](../it/apt.md)* · [back to the README](../../README.md)

The third way in, beside [installing from nothing](install.md) and
[upgrading an existing receiver](upgrade.md): a Debian package, so a receiver
gets ABMod the same way it gets everything else.

```bash
sudo apt-get install abmod
```

Removing it puts the original OpenWebRX files back:

```bash
sudo apt-get remove abmod
```

---

## What the package actually does

ABMod replaces **31 files that the `openwebrx` package owns** and adds **19 of
its own**. dpkg refuses, correctly, to let one package unpack over another's
files, so the 31 are handled with **dpkg diversions**.

A diversion tells dpkg "this path belongs to someone else now". The upstream
file is renamed to `<name>.openwebrx-original` and kept, ABMod's version takes
the real path, and removing the package reverses it. Two things follow that a
copy script could never give you:

- **`apt-get remove abmod` really does restore upstream.** Not from a backup
  taken at install time, but from the files dpkg itself set aside.
- **A later `openwebrx` upgrade cannot silently overwrite the modification.**
  It writes to the diverted name instead, where it sits harmlessly.

### It refuses to install over a hand-installed ABMod

If `install.sh` or `upgrade.sh` has already copied ABMod over those 31 files,
the package stops before changing anything and says so. This is not caution for
its own sake: diverting a file that has already been modified would record the
*modified* file as the original, and a later `apt-get remove` would restore it
and call it upstream. The mess is quiet and only shows up much later.

Put the originals back first — this touches no settings, bookmarks or users —
and install again:

```bash
sudo apt-get install --reinstall openwebrx
```

```bash
sudo apt-get install abmod
```

The receiver runs plain OpenWebRX for the minute in between.

### openwebrx is held at the version ABMod was built against

The package declares `Depends: openwebrx (>= 1.2.2), openwebrx (<< 1.2.3)`.
Because whole files are replaced rather than patched, a different OpenWebRX is
a different set of files and ABMod's copies would be wrong in ways that are
hard to see. So while ABMod is installed, apt will hold openwebrx where it is.

That is the honest expression of the situation, not a limitation being hidden.
If you want to upgrade OpenWebRX, remove ABMod, upgrade, and install an ABMod
built against the new version.

---

## Building the package

On any Debian machine with `dpkg-dev` — the receiver itself will do, it only
writes into a temporary directory:

```bash
./packaging/build-deb.sh
```

It produces `abmod_1.0.0_all.deb`. The package is `Architecture: all`, because
everything in it is Python, JavaScript and HTML, so one built on a laptop
installs on a Raspberry Pi unchanged.

The build refuses to produce a package it cannot vouch for. It checks the list
of diverted files against the `openwebrx` actually installed on the build
machine, counts the files that made it into the archive against the source
tree, and fails on either mismatch. If you edit `src/`, that is all automatic;
if the file list ever needs regenerating:

```bash
./packaging/list-diverted.sh pi@receiver
```

---

## The repository: crazyclimber999.github.io/abmod

Served by GitHub Pages from the `gh-pages` branch, which is why that branch
holds the packages and their indices and `main` does not. The `.nojekyll` file
on it is not decoration: without it Pages runs the tree through Jekyll, which
drops directories beginning with an underscore and is free to rewrite what it
takes for a page.

On each receiver, once:

```bash
sudo curl -fsSL https://crazyclimber999.github.io/abmod/abmod-archive-keyring.asc -o /usr/share/keyrings/abmod.asc
```

```bash
echo "deb [signed-by=/usr/share/keyrings/abmod.asc] https://crazyclimber999.github.io/abmod/ bullseye main" | sudo tee /etc/apt/sources.list.d/abmod.list
```

```bash
sudo apt-get update && sudo apt-get install abmod
```

### Publishing a new version

```bash
packaging/publish-pages.sh
```

It builds the package, builds a signed repository from it, pushes the result to
`gh-pages`, and then **fetches what Pages actually serves** and fails if any of
it is missing. A publish that reports success without that check has told you
about its own intentions, not about the state of the world.

`--dry-run` builds and commits locally without pushing.

It has to run on a Debian machine, because building a `.deb` needs `dpkg-deb`
and indexing a repository needs `dpkg-scanpackages` — in practice the receiver.
It says so if you run it anywhere else.

### Where the signing key lives, and why it is not in CI

The GitHub Action builds the package and runs its checks on every push, and
holds no secrets. It does not sign and it does not publish.

Signing in CI would mean putting the private key in a repository secret. A key
whose whole job is to prove the packages came from you is worth more than the
convenience of not typing a command, so that trade is not made by default here.
It is a defensible trade — most distributions make it — but it should be made
knowingly.

Which leaves the key wherever you put it, with the honest costs:

- **On the receiver**, where the publish script runs: simplest, one machine, and
  the key sits on a box reachable from the internet.
- **In a GitHub secret**: an Action publishes on a tag and you never type
  anything, and the key has left your hands.
- **On your own machine**, with the repository built on the receiver and only
  the `Release` file brought back to sign: the key never moves, at the cost of
  a two-step publish.

The script does not create a key, and that is deliberate: a signing key needs a
passphrase, and choosing someone else's passphrase is not a favour. Make one
with

```bash
gpg --full-generate-key
```

take the defaults, use a name and an address you are content to publish, and
set a passphrase. The script finds it by itself if it is the only one.

### Without a repository at all

The package installs perfectly well from a file, which needs no hosting and no
signing:

```bash
sudo apt-get install ./abmod_1.0.0_all.deb
```

`apt-get` rather than `dpkg -i`, so dependencies are resolved. This is the
right answer for one or two receivers you administer yourself — the repository
earns its keep when you stop wanting to copy a file around by hand.

---

## Checking what you got

```bash
dpkg -l abmod
```

```bash
dpkg-divert --list | grep abmod | wc -l
```

The second should say **31**. If it says 0 while the package is installed,
something has gone wrong and upstream's files are live — the receiver will run,
but it will not be ABMod.
