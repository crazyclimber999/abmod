# ABMod for OpenWebRX

*[Leggi in italiano](README.it.md)*

A set of modifications to **OpenWebRX**, the open source SDR web receiver, for
amateur radio stations that want bookmarks worth keeping, selective-call
decoding, a map that needs no API key, and a way to import a national repeater
list without drowning in it.

ABMod is **not a fork**. It is a collection of changed and added files that
drop into an existing OpenWebRX installation, and it can be removed again by
restoring the backup the installer takes for you.

---

## Two ways in

**You have no OpenWebRX yet** → [Installing from scratch](docs/en/install.md)

```bash
git clone https://github.com/crazyclimber999/abmod.git abmod
cd abmod
sudo ./install/install.sh
```

**You already run OpenWebRX** → [Upgrading an existing receiver](docs/en/upgrade.md)

```bash
git clone https://github.com/crazyclimber999/abmod.git abmod
cd abmod
sudo ./install/upgrade.sh
```

**Or with apt** → [Installing with apt-get](docs/en/apt.md)

```bash
sudo apt-get install abmod
```

from the repository at
[crazyclimber999.github.io/abmod](https://crazyclimber999.github.io/abmod/),
once a receiver has been told about it. ABMod is a Debian package that replaces
the openwebrx files through dpkg diversions, so `apt-get remove abmod` puts the
originals back and a later OpenWebRX upgrade cannot overwrite the modification
in silence.

Either way nothing is changed until a backup has been taken **and read back**,
and the script checks afterwards that the receiver really answered. If it did
not, one command puts everything back:

```bash
sudo ./install/rollback.sh /root/abmod-backup-YYYYmmdd-HHMMSS
```

Your `settings.json`, your bookmarks and your users are never touched by
either script.

---

## What it adds

A fuller account, with the reasoning, is in
[all the features](docs/en/features.md).

**Access control.** Bookmarks need a login; the settings need an administrator.
A user management page, real roles, a logout that actually logs out — upstream's
was a placeholder that did nothing — and sessions that survive a restart.

**Bookmarks that earn their place.** A panel in the receiver with search,
sorting, editing and one-click tuning. An editable band plan beside it. Bulk
selection and deletion in the editor, because a list with a repeater database
in it runs to hundreds of rows.

**Import a repeater list.** Read `.xls`, `.xlsx` or `.csv` from a URL or a
file, map the columns from dropdowns, filter by region, translate the source's
own modulation names, preview every row that will be imported, and save the
whole arrangement as the default for next time.

**Decide what you can actually hear.** Optionally, the importer measures the
ground between you and each station — real elevation data, path profiles,
diffraction over ridges, your antenna's height and pattern — and keeps only
what should be receivable. On the Italian repeater list that is 1031 bookmarks
down to 167, and the ones it drops are behind mountains.

**Selective calling.** A **5-tone (SELCALL)** decoder covering CCIR/EEA, ZVEI1,
ZVEI2, DZVEI, EIA and CCITT at once, with a per-standard filter, and a
**2-tone paging** decoder that measures the actual tone frequencies rather than
guessing from a table.

**A map without Google.** Leaflet on OpenStreetMap: no API key, no billing
account, nothing handed to your visitors. Day/night terminator included, and
the receiver-location picker in the settings works the same way.

**APRS, both directions.** Positions pulled from aprs.fi for stations out of
your range — the API key stays on the server — and the APRS-IS igate settings
gathered into one place next to them.

---

## Requirements

- **OpenWebRX v1.2.2.** ABMod was built and tested against it. The upgrade
  script warns and asks before touching anything else.
- **Python 3.7+** with `numpy`, which OpenWebRX already needs.
- `python3-xlrd`, only to import the old binary `.xls` format. The installer
  offers it; `.xlsx` and `.csv` need nothing extra.
- About **85 MB of disk** if you use the listenability filter, for elevation
  data within the radius you choose.

Tested on a Raspberry Pi 3 running Raspberry Pi OS (bullseye).

---

The list of changes against upstream is in the [changelog](CHANGELOG.md).

---

## Credits

**OpenWebRX** is the work of **Jakob Ketterl, DD5JFK**, and its contributors.

- Author: [Jakob Ketterl, DD5JFK](http://www.justjakob.de/)
- Homepage: [www.openwebrx.de](https://www.openwebrx.de)
- Source: [github.com/jketterl/openwebrx](https://github.com/jketterl/openwebrx)
- Mailing list: [groups.io/g/openwebrx](https://groups.io/g/openwebrx)

That credit stays as it is, here and in the receiver's own interface. Nothing
in ABMod replaces it.

**ABMod** is by **IU2QDA** — [www.iu2qda.it](https://www.iu2qda.it).

Also used: [Leaflet](https://leafletjs.com/) for the map; map tiles from
[OpenStreetMap](https://www.openstreetmap.org/copyright) contributors;
position data from [aprs.fi](https://aprs.fi/); APRS symbols from the
[aprs-symbols](https://github.com/hessu/aprs-symbols) project; elevation data
from NASA's SRTM, served as public terrain tiles.

The importer was written against the Italian repeater list published by
**IK2ANE**, which is his work and carries its own terms — free for radio
amateurs, private use, with attribution, no commercial use. **No repeater data
is included in this repository.**

---

## Licence

OpenWebRX is under the **GNU Affero General Public License v3**, so ABMod is
too. The full text is in [LICENSE.txt](LICENSE.txt), taken verbatim from
upstream.

The AGPL matters more than usual here. Running a modified version as a network
service — which is exactly what a web SDR is — obliges you to offer its source
to the people using it. Publishing this repository is what satisfies that, and
the receiver's interface carries a link back to it.
