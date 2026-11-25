# Installing from scratch

*[In italiano](../it/installazione.md)* · [back to the README](../../README.md)

For a machine with no OpenWebRX on it. If you already run OpenWebRX, use
[upgrade.md](upgrade.md) instead — it keeps your configuration.

## Before you start

- A Debian-like system: Raspberry Pi OS, Debian, Ubuntu. Tested on a
  Raspberry Pi 3 with Raspberry Pi OS bullseye.
- An SDR the OpenWebRX documentation supports.
- Root, through `sudo`.

## Install

```bash
git clone <this repository> abmod
cd abmod
sudo ./install/install.sh
```

The script installs OpenWebRX from its packages, takes a backup of the
untouched installation, applies ABMod on top, checks every python file
compiles, restarts, and waits for the receiver to answer before telling you it
worked.

If the `openwebrx` package is not available on your machine, the script stops
and says so. Add OpenWebRX's own package repository — the current instructions
are in [its wiki](https://github.com/jketterl/openwebrx/wiki) — and run the
script again. It carries on from there. ABMod deliberately does not ship a
copy of those repository addresses: a stale URL baked in here would fail
confusingly a year from now.

## Then, in this order

**1. Create the first administrator.** The settings and the bookmarks need a
login, and without this nobody can get in:

```bash
sudo openwebrx admin adduser <name>
```

**2. Open `http://<the machine>:8073/settings`** and set at least:

- **Receiver details** — name, location, and the coordinates. The coordinates
  are not decoration: they decide what the map centres on, where the APRS
  beacon says you are, and what the listenability filter measures from.
- **SDR devices and profiles** — your receiver and the bands you want.
- **Receiving antenna** — height above ground, at least.

**3. Optional, under General settings:**

- an **aprs.fi API key**, to show stations you cannot hear yourself
- an **APRS-IS passcode**, to forward what you do hear
- the **terrain data radius**, if you want the listenability filter

See [configuration.md](configuration.md) for what each setting does.

## If something goes wrong

The script prints the backup directory. To undo everything:

```bash
sudo ./install/rollback.sh /root/abmod-backup-YYYYmmdd-HHMMSS
```

To see what the receiver is complaining about:

```bash
journalctl -u openwebrx -n 50
```
