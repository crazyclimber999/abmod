# Changelog

*[In italiano](CHANGELOG.it.md)*

Everything here is relative to **OpenWebRX v1.2.2**, which is the version ABMod
is built and tested against. The reasoning behind each choice is in
[all the features](docs/en/features.md); this file is the list.

Dates are the day the change was finished and running on a live receiver.

## Unreleased

### Documented

- **Why the igate stops when nobody is listening**, which is upstream
  behaviour and not a fault: OpenWebRX's background service handler registers
  with the SDR as an `INACTIVE` client, and the source only starts for a `USER`
  or `BACKGROUND` one, so services never start the radio - they attach to one
  already running for a listener. The cure is the `always-on` device setting,
  which exists but sits behind "Additional optional settings" where nobody
  finds it. Written up with what it costs: the dongle runs 24/7 and the load
  settles around 2.4 on a Pi 3, which on an under-powered Pi is what makes USB
  devices drop.

### Added

- **A Debian package, so a receiver installs ABMod with `apt-get install`.**
  The 31 files ABMod replaces are handled with **dpkg diversions** rather than
  copied over: the upstream file is kept beside its replacement as
  `<name>.openwebrx-original`, `apt-get remove abmod` genuinely restores it,
  and a later `openwebrx` upgrade writes to the diverted name instead of
  silently overwriting the modification. The 19 new files just install.

  It **refuses to install over an ABMod put there by hand**, naming the files,
  because diverting an already-modified file would record the modified copy as
  the original — and the damage only shows up at removal time, long after.
  `apt-get install --reinstall openwebrx` first, then the package.

  `Depends: openwebrx (>= 1.2.2), openwebrx (<< 1.2.3)`, which holds OpenWebRX
  at the version ABMod was built against. Whole files are replaced, so a
  different OpenWebRX is a different set of files; the constraint states that
  rather than hiding it.

  `packaging/build-deb.sh` builds it anywhere with `dpkg-dev`, the receiver
  included, and refuses to produce a package it cannot vouch for: it checks the
  diverted list against the `openwebrx` installed on the build machine, counts
  what reached the archive against the source tree, and rejects stray macOS
  AppleDouble files. `packaging/repo/build-repo.sh` turns the result into a
  signed APT repository, and `packaging/publish-pages.sh` publishes it to
  GitHub Pages at
  [crazyclimber999.github.io/abmod](https://crazyclimber999.github.io/abmod/) —
  then fetches what Pages actually serves and fails if any of it is missing.
  A GitHub Action builds and checks the package on every push; it holds no
  secrets and does not sign, because a signing key in a repository secret buys
  convenience with the one thing the key exists to prove. See
  [installing with apt-get](docs/en/apt.md).

## v1.0.1 — 2026-11-25

### Fixed

- **The centre frequency box lost the 12.5 kHz raster.** It was written with
  three decimals of a megahertz, which is kilohertz resolution, so 145.0125 MHz
  came out 145.012 — not a channel. It was not only cosmetic: the step buttons
  read that box back, so one rewrite put the tuned frequency 500 Hz off and
  every later step kept the error. One helper now formats every frequency the
  interface writes, printing the shortest text that reads back as the same
  frequency, so a 6.25 kHz raster survives too. Checked across the whole
  12.5 kHz raster from 144 to 146 MHz: 161 frequencies, all round-tripping
  unchanged. The box also follows the unit selector now instead of always
  assuming megahertz.
- **Dead `recallmemory` path removed**, both halves of it. The server
  authorised the message, dispatched it, tuned the SDR and answered
  `memory_recalled`, and the browser had a handler waiting for that answer —
  but nothing has ever sent the message: clicking a bookmark moves the
  demodulator client-side, which is the correct behaviour and the reason the
  server copy was written and then orphaned. Gone from `connection.py`
  (`_recall_memory`, `_find_memory`, `write_memory_recalled`) and from
  `openwebrx.js` (`on_memory_recalled` and its case).

## v1.0.0 — 2026-11-25

First published release. Running on two Raspberry Pi 3 receivers.

### Added

**Access control**

- A user management page at `/settings/users`: add, remove, enable, disable,
  change passwords, grant or revoke administrator.
- Two permission levels. A plain user reads and edits bookmarks; an
  administrator reaches the settings.
- Sessions stored on disk, mode `600`, with expired ones dropped on load.
- The logged-in user and the logout control in the receiver's status panel.

**Bookmarks**

- A bookmarks panel in the receiver, backed by OpenWebRX's own storage, with
  search, sorting, editing and deletion.
- One click tunes and sets the modulation.
- The same panel switches between bookmarks and the band plan.
- A band plan settings page at `/settings/bandplan`, editing the raw JSON so
  entries using modes this receiver cannot demodulate survive a round trip.
- Checkbox selection and bulk deletion in the bookmark editor, with select-all,
  shift-click ranges, and the names of the first five shown before anything is
  deleted.
- A `5tone` pseudo-modulation: stored on a bookmark, resolved to NFM plus the
  5-tone decoder when tuned.

**Importing a repeater list** (`/settings/bookmarkimport`)

- Reads `.xls`, `.xlsx` and `.csv`, from a web address or an uploaded file.
- Column mapping from dropdowns, guessed from the file's own headers; a
  two-part name with a chosen separator, and any other columns appended in
  brackets.
- Region filter with a row count per region.
- Modulation translation per source value, including *(ignore import)*. Modes
  the receiver cannot demodulate are listed but not selectable.
- A preview of every row that will be imported, 25 at a time.
- The whole arrangement savable as the import default.
- One bookmark per frequency: the best-heard station is kept and the rest
  dropped, optionally displacing a bookmark already held on that frequency.
- Counts of what is being left out, always.

**Listenability estimate**

- Elevation data: SRTM at one arc-second from a public tile service needing no
  account, stored reduced to three arc-seconds, validated against known
  heights.
- A propagation model: ground profile along the great circle, effective earth
  radius of 4/3, knife-edge diffraction by Deygout's method, free-space loss,
  and the antenna's gain in that direction. The answer is a margin in dB.
- A beyond-the-horizon flag instead of a guess, because out there the
  obstruction is the curve of the earth and what happens is weather.
- Antenna description in the settings: height above ground, gain, and an
  optional horizontal pattern.
- The highest point of a six-character locator square used as the far station's
  position, the centre for a four-character one.
- Elevation-data status and download in the general settings, under the radius
  that decides how much to keep, and on the import page.

**Decoders**

- A **5-tone (SELCALL)** decoder covering CCIR/EEA, ZVEI1, ZVEI2, DZVEI, EIA
  and CCITT at once from one shared FFT, reporting which standard produced each
  sequence, with a per-standard filter that counts what it is hiding.
- A **2-tone paging** decoder, with parabolic interpolation of the FFT peak so
  the measured frequency is the result and the tone plan only a label.

**The map**

- Drawn with Leaflet on OpenStreetMap tiles instead of the Google Maps API: no
  key, no billing account, nothing handed to visitors. The tile source is
  configurable.
- A day/night terminator computed in place of the Google-specific overlay.
- The receiver location picker in the settings rebuilt on Leaflet: drag, click
  or type, all three in step.

**APRS**

- Positions pulled from aprs.fi for a list of watched callsigns, polled by the
  receiver and pushed down the websocket, so the API key never reaches the
  browser. Clamped to one query a minute.
- The igate settings gathered onto the APRS page with the rest, antenna height,
  gain and direction included.
- A configurable beacon interval.
- A button that works the APRS-IS passcode out from the callsign, in the
  browser, and a warning when the field holds something that is not a passcode.

**Save Defaults**

- An administrator can store the current centre frequency and sample rate as
  the startup defaults.
- Frequency step buttons: 25 kHz on the single arrows, 1 MHz on the double.

### Changed

- The compiled JavaScript bundles are sent with `Cache-Control: max-age=0`
  instead of `max-age=3600`. The browser revalidates and gets a 304 with no
  body when nothing changed — measured at 0 bytes against 229 KB — so a deploy
  is never invisible for an hour.
- The message panels are laid out as one table instead of two, so the headings
  stay over their columns.

### Fixed

- **Bookmarks were readable without logging in.** Hiding the button left the
  websocket commands behind it answering anyone who sent them; the check is now
  on the server, and the tags on the frequency scale appear only once logged in.
- **The logout did not log out.** Upstream's redirected to a page saying logout
  was happening and left the session alive.
- **Sessions no longer die on restart.** They lived in memory, and any change
  under `owrx/` needs a restart, which logged everyone out.
- **You can no longer lock yourself out** of the settings: the last
  administrator cannot be removed, nor can you take the rights off the account
  you are logged in as.
- **A start-up race.** A websocket arriving during start-up could hit
  `multiprocessing.connection` while another thread was importing it, raising
  `ImportError` and dropping that connection. The module is loaded before any
  thread starts.
