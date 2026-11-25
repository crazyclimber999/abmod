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

## Publishing a repository

An APT repository is just files on a web server — nothing dynamic. This builds
one:

```bash
./packaging/repo/build-repo.sh --out ./apt --key <your-gpg-key-id> abmod_1.0.0_all.deb
```

Then copy that directory to somewhere reachable over HTTP, and on each
receiver:

```bash
sudo curl -fsSL https://your.host/abmod-archive-keyring.asc -o /usr/share/keyrings/abmod.asc
```

```bash
echo "deb [signed-by=/usr/share/keyrings/abmod.asc] https://your.host/ bullseye main" | sudo tee /etc/apt/sources.list.d/abmod.list
```

```bash
sudo apt-get update && sudo apt-get install abmod
```

**Sign it.** Without `--key` the repository is unsigned, every receiver has to
be told `[trusted=yes]` to use it at all, and that flag does not just skip a
formality — it disables the check that the package you are installing is the
one that was published. On a machine that runs as a network service, reached
from outside, that is the wrong corner to cut.

### Where to put it

Three honest options, with what each actually costs:

**Your own web space.** Any static hosting you already control. Nothing to set
up beyond an upload, the URL is yours, and it keeps working if GitHub does not.
This is the one to choose if you have it.

**GitHub Pages.** Free and reliable, but Pages will not serve a private
repository — so this means publishing the package, and the package contains the
source. If the repository is deliberately private, this option is not available
without changing that decision.

**A receiver serving the others.** One Pi with a web server and the repository
directory under it. Fine on a local network and genuinely useful for a cluster
of receivers; useless to anyone outside it, and it means a receiver is also a
small web server.

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
