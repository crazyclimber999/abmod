# Upgrading an existing receiver

*[In italiano](../it/aggiornamento.md)* · [back to the README](../../README.md)

For a machine already running OpenWebRX. Your configuration, bookmarks and
users are kept.

## Before you start

- **OpenWebRX v1.2.2.** ABMod was built and tested against it. The script
  warns and asks before touching anything else.
- Root, through `sudo`.
- Two minutes of downtime while the service restarts.

## Upgrade

```bash
git clone <this repository> abmod
cd abmod
sudo ./install/upgrade.sh
```

What it does, in order:

1. **Finds OpenWebRX** rather than assuming where it is — Debian, pip and
   different python versions all put it somewhere different.
2. **Checks the version** and asks if it is not 1.2.2.
3. **Backs up** `owrx/` and `htdocs/`, plus `settings.json`, `bookmarks.json`,
   `users.json` and `bands.json`, into `/root/abmod-backup-<timestamp>` — and
   reads the archive back before going on. A backup nobody has checked is not
   a backup.
4. **Installs the ABMod files** and checks every python file compiles. A
   syntax error here takes the whole receiver down, and it is far cheaper to
   find it now.
5. **Offers `python3-xlrd`**, only needed to import old `.xls` files.
6. **Restarts and waits for the receiver to answer**, then reports any
   tracebacks in the log.
7. **Clears the Varnish cache** if you run one.

Nothing is changed before step 3 succeeds.

## After the upgrade

**The bookmarks and the settings now need a login.** If you have no users yet,
create one before you need it:

```bash
sudo openwebrx admin adduser <name>
```

**Set the antenna height** under Settings → General → Receiving antenna. The
listenability filter needs it, and the default of 10 m is only a guess about
your station.

**Check your receiver coordinates** under Receiver details. They were probably
right already, but ABMod now uses them for more than the map.

Everything else keeps working as it did. Your existing bookmarks are untouched
and appear in the new panel.

## Rolling back

```bash
sudo ./install/rollback.sh /root/abmod-backup-YYYYmmdd-HHMMSS
```

This restores `owrx/` and `htdocs/` from the archive. It deliberately does
**not** restore your configuration: the upgrade never changed it, so what is
on the machine now is yours and more recent. Copies are in the backup
directory if you want them.

## Upgrading ABMod itself later

Pull the new version and run `upgrade.sh` again. It takes a fresh backup every
time and the same checks apply.
