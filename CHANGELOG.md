# Changelog

*[In italiano](CHANGELOG.it.md)*

Everything here is relative to **OpenWebRX v1.2.2**, which is the version ABMod
is built and tested against. The reasoning behind each choice is in
[all the features](docs/en/features.md); this file is the list.

Dates are the day the change was finished and running on a live receiver.

## v1.0.17 — 2026-11-26

### Added

- **A DMR caller now shows what the radio ID database knows about them** -
  surname, town, state and country, not only the first name. None of this
  needed a new lookup: the whole record was already arriving with every call
  and all but one field was being thrown away. A hand-held radio with a
  contact list shows the lot, and there was no reason for a web receiver to
  show less. Missing fields are left out rather than printed as gaps, and an
  entry that repeats the country in its state field is not shown as
  "Italy, Italy".
- **Talkgroups have names**, so a call reads `222 (Italia)` instead of a bare
  number. The number stays, because that is what a radio is programmed with;
  the name sits beside it. The names come from BrandMeister's published list -
  about 1850 of them in some 45 kB - downloaded once a week and cached on
  disk, never in the path a metadata frame takes: a name is a convenience, and
  waiting on the network for one would delay the thing it decorates. Until the
  list arrives, calls show the number, which is what they showed before. Only
  group calls are named: on a direct call the target is somebody's radio ID,
  and naming that from a talkgroup table would be wrong rather than merely
  unhelpful. `digital_voice_dmr_talkgroup_lookup` turns the whole thing off.

## v1.0.16 — 2026-11-26

### Fixed

- **The sub-audible tone detector ran on modes that cannot carry a tone.** On
  a DMR signal it would occasionally report a CTCSS tone and write one into
  the log, which is not a false reading so much as a meaningless one: CTCSS is
  an analogue FM arrangement, and DMR, D-Star, YSF, NXDN and M17 carry their
  access control in the protocol with no room in the standard for a tone below
  the voice band. AM and SSB have none either. The detector now runs on
  narrowband FM and nothing else - a positive test rather than a list of
  exclusions - and switching to another mode clears the display instead of
  leaving the last tone on screen.

## v1.0.15 — 2026-11-26

### Fixed

- **A dongle served over the network lost its gain on every reconnection.**
  openwebrx sends the gain once, when it starts the connector, and the
  connector does not send it again when it reconnects by itself. rtl_tcp
  resets the tuner whenever a client connects, so a restart of the dongle
  server, a wi-fi blink or a pulled cable left the receiver at minimum
  gain - while the settings page, the saved configuration and the
  connector's own command line all still read correctly, which made it a
  thoroughly confusing fault to look at. Measured on a live receiver: the
  off-centre noise floor 14 dB down after a reconnection, with nothing
  changed.

  The gain is now re-asserted over the connector's control socket every 30
  seconds, but only for `rtl_tcp` and `soapy_remote` devices, where the
  hardware is not on this machine's own bus and can be re-opened without
  openwebrx noticing. Setting a tuner to the gain it already has costs
  nothing and is inaudible. A device set to automatic gain is left alone:
  re-sending that would be re-asking for a mode, not restoring a value.

## v1.0.14 — 2026-11-26

### Changed

- **The APRS parking does nothing unless the igate is on.** Feeding *Send
  received APRS data to the APRS-IS network* is the parking's only purpose, so
  with the igate off there is nothing to park for and the clock is no longer
  even started. The receiver stays on the centre frequency its operator saved.

### Added

- **Every refusal to park now says why.** Three ways out used to be silent -
  the igate being off, a listener still connected, a listener arriving while
  the clock ran - and a receiver that never parks for one of those reasons
  read exactly like a receiver with a fault. Each one now says which it is.

## v1.0.13 — 2026-11-26

### Fixed

- **A receiver whose saved default already was the APRS frequency never
  parked.** Whether to park was decided by comparing the idle frequency with
  the saved default, so a station with 144.800 saved as its default - the
  obvious setup for one that mostly gates - skipped parking even after a
  visitor had moved the centre away and left, and the gateway stayed dead
  until the next restart. The comparison is now against where the radio is
  actually pointing.
- **Coming back from parking went to the parked frequency, not the default.**
  `sdr.props` is a stack whose top layer is the profile's own object, the one
  that lives inside the live configuration, so every retune - the parking
  included - writes straight through into it. Asked what the default was, the
  configuration answered with wherever the receiver was pointing. The saved
  centre frequency is now read from `settings.json`, which only Save Defaults
  writes, so an operator who saves a new default while the receiver is parked
  gets that new one on the way back.
- **The APRS idle clock is armed at start-up too.** Until now only a listener
  leaving started it, so a receiver that had just been restarted and that
  nobody had visited since never parked at all - which is precisely the
  situation the rule exists for. It is now armed once when the receiver comes
  up, and still does nothing unless the rule is switched on.

## v1.0.12 — 2026-11-26

### Added

- **The receiver can park on the APRS frequency while nobody is listening.**
  The igate and a listener want the receiver on two different frequencies, and
  they never want it at the same time: the packet service only runs where a
  band plan entry for it falls inside the sampled window, so a listener who
  tunes elsewhere takes the gateway down. With this on, the last listener to
  leave starts a clock - ten minutes by default - and when it runs out the
  receiver moves itself to the configured APRS frequency; the moment someone
  connects it goes back to the centre frequency saved for the profile, before
  that client is told anything, so what it sees is already true.

  Only the running properties are written, never `settings.json`: a parked
  receiver that is restarted comes back on its default, which is the right way
  round for a temporary state. The wait is there because a listener who
  reloads the page is gone and back within seconds, and parking in between
  would cost them a device restart.

  Three settings under General settings → APRS: igate, off by default. It
  needs *Keep device running at all times* on the device, and the module says
  so in the log rather than parking a radio that is switched off. The cost is
  stated plainly on the settings page: **any** visitor connecting stops the
  gateway, not only the operator.

### Fixed

- **DMR produced nothing at all when a digital mode was switched on.** The
  metadata-only chain ended in a SHORT audio stream, as upstream's digiham
  chain does - it has an AGC there, which this one does not need.
  `ClientDemodulatorChain._connect` rebuilds the audio buffer whenever the
  demodulator's output format changes and hands the new reader to the
  secondary demodulator; ABMod's 5-tone and 2-tone decoders read audio as
  FLOAT, so a SHORT buffer made them raise `ValueError: invalid reader format`.

  `Chain.replace` re-raises that, which aborted `setDemodulator` halfway: the
  old demodulator had already been stopped and swapped for a placeholder, the
  new one was never attached, and from then on `self.demodulator` was `None` -
  so the next call failed too, with `AttributeError: 'NoneType' object has no
  attribute 'setSampleRate'`. The receiver was left with no demodulator at
  all: no metadata, no audio, and nothing shown on the page.

  The chain now outputs FLOAT, like every analog mode, so the buffer is never
  rebuilt and nothing is re-wired. Found on a live receiver; the earlier tests
  had always selected DMR with no secondary mode running, which is the one
  path that worked.

### Changed

- **The source is in English throughout.** Comments and local names in the
  bookmark importer, the bulk editor, the terrain and passcode helpers, the
  CTCSS detector and the receiver panels were still Italian in places. Renames
  and comments only. The Italian header names in the importer's column guesser
  stay: those are spreadsheet headings to match, not language. The dead
  `ctcssSpegni()` is gone, and the `ctcss-margine` CSS class is now
  `ctcss-margin` in both index.html and openwebrx.js.

## v1.0.11 — 2026-11-26

### Added

- **DMR without the AMBE codec: identities and talkgroups, no voice.** DMR
  needs two things, and only one of them is free. digiham, which synchronises
  on the TDMA bursts and extracts both the voice frames and the signalling, is
  in the Debian repository. The AMBE+2 decoder is not: codecserver ships one
  driver, `libambe3k.so`, and that is not a software codec at all - it drives
  an AMBE-3000 chip over a serial port. Without the hardware
  `MbeSynthesizer.hasAmbe()` is false, and upstream then withdraws the whole
  mode, signalling included, although the signalling never passes through the
  codec.

  It does not have to go that way. In upstream's own chain the metadata leaves
  by its own route - `self.decoder.setMetaWriter(buffer)`, the decoder, not the
  synthesizer - so a chain that stops at the decoder still reports who is
  transmitting, on which talkgroup and in which timeslot, resolved against
  RadioID by the existing parser and shown in the panel the DMR mode already
  has. ABMod builds that chain whenever the codec is missing, and upstream's
  full chain whenever it is there, so an AMBE-3000 dongle would turn the audio
  on with no further change. The absence of audio is announced in the
  receiver's log, because a mode that normally carries sound and suddenly does
  not looks like a fault.

  The slot filter, the metadata panel and the bandplan entries all work
  unchanged: the mode is still `dmr`, with the same name and the same
  bandwidth.

## v1.0.10 — 2026-11-26

### Fixed

- **The DS badge disappeared on a page reload**, even with the receiver still
  below the tuner's floor. It was being sent with the initial configuration,
  which is assembled before the device is attached and therefore cannot yet
  say which input is in use. It now goes out from `handleSdrAvailable`, which
  runs on the first connection and again after every source restart.

## v1.0.9 — 2026-11-26

### Fixed

- **The direct sampling switch left the receiver on the wrong frequency.** The
  mode was decided and the connector restarted *before* the new centre
  frequency was written, so it came up on the old frequency in the new mode and
  then had to be retuned over the control socket - which for a tuner asked to
  reach 6 MHz never worked. Measured on a live receiver: it ended on 15.001
  MHz, neither the frequency it left nor the one it was asked for.

  The frequency now goes into the properties first. The connector builds its
  command line from those properties, so it comes up already tuned and already
  in the right mode, and no retune is needed at all.

- **The waterfall froze after the switch.** Upstream's connection only listens
  for the source becoming RUNNING, which is enough while a source never stops
  with a listener still attached. Restarting the device for direct sampling
  does exactly that, so the old dsp chain stayed wired to a process that had
  gone and `handleSdrAvailable` then reconfigured that same dead chain instead
  of building a new one. The connection now tears its dsp down on STOPPING as
  well, and the rebuild on RUNNING does the rest.

- **The DS badge is refreshed on every retune**, not only when the mode
  changes, so it stays honest even when another listener moved the radio.

## v1.0.8 — 2026-11-26

### Added

- **Direct sampling switches itself on below the tuner's floor.** An R820T
  cannot tune under about 24 MHz; below that the only way in is the ADC's own
  input. Tuning the receiver there now puts the device into direct sampling on
  the Q branch, and coming back above it puts it back.

  The decision is made on the **top** of the sampled window rather than its
  centre: a window centred at 23 MHz reaches 24.25 and the tuner can serve all
  of it, so switching on the centre alone would hand perfectly good spectrum to
  an input that has no filtering in front of it.

  It costs a restart, and that is not hidden. Direct sampling is a command line
  option of the connector, while frequency travels live over the control
  socket, so the process has to go round again - `ConnectorSource` sends every
  property change down that socket and never restarts, and switching profiles
  does the same. The receiver therefore drops audio for a few seconds, and says
  so in the log before it does.

  Measured on the hardware first, with `rtl_connector` itself: at 6 and 7 MHz
  with direct sampling on, discrete lines stand **29 dB above the noise floor**,
  against a 2m control that behaves exactly as expected. A disconnected Q
  branch does not do that.

  While it is on, a **DS** badge sits beside the Set button, the same size as
  it, so the receiver says which input it is listening through rather than
  leaving you to work it out from the frequency. It is sent with the
  configuration, so it is also right for someone who connects to a receiver
  that is already down there.

## v1.0.7 — 2026-11-25

### Removed

- **The prefix box in the 5-tone panel**, added in 1.0.6 and taken out at the
  operator's request: he would rather see everything the decoder produces and
  judge it himself. The per-standard buttons and the count of what they hide
  stay as they were.

  The spectral purity gate in the decoder is untouched and is not a filter on
  results: it decides whether a 25 ms window contains a tone at all, and it is
  what took the same recording from 1 true call to 9.

## v1.0.6 — 2026-11-25

### Added

- **A prefix filter in the 5-tone panel.** On a network where every call
  starts with the same digits, typing them in the small box beside the
  standard buttons hides everything else. On the channel this was built
  against that takes CCIR precision from 75% to 100%.

  It is a filter, not a rule the decoder applies by itself, and the difference
  matters. The obvious heuristic - reject any sequence built from fewer than
  three distinct tones - would have reached 90% on the same data and was
  **not** adopted: the network's own operator confirmed that `31111` is a
  valid address, and a selective-call system that silently drops a real call
  costs far more than a visible line that is obviously not yours. The prefix
  is visible, reversible, kept in the browser, and the count underneath still
  reports everything it is hiding.

## v1.0.5 — 2026-11-25

### Changed

- **The sub-audible tone now stays on screen** once it has been read, instead
  of disappearing when the carrier drops. CTCSS only exists while someone is
  transmitting, but it is a property of the channel rather than of the moment:
  clearing it at the end of each over showed it for two seconds and then took
  away the very thing worth knowing. It is replaced when a different tone is
  heard, and forgotten when the tuning moves - a tone belongs to the frequency
  it was heard on. The log line names that frequency.

## v1.0.4 — 2026-11-25

### Fixed

- **The CTCSS block was nested inside the websocket message handler**, so its
  state lived in that function rather than at file scope. It worked - the
  feeder is called from the same function - but nothing could inspect or reuse
  it, and a variable that only appears to be global is a trap for the next
  change. Moved out.

## v1.0.3 — 2026-11-25

### Added

- **The sub-audible CTCSS tone, read from the audio and shown in the
  receiver**, under the frequency, and written to the receiver's log when it
  changes. It is detected in the browser with a Goertzel bank over the 39
  standard tones, on audio decimated to 1 kHz, in two-second windows - a
  continuous tone is in no hurry, and the length buys the resolution the
  closest pairs in the table need.

  That this works at all was measured, not assumed. OpenWebRX's NFM chain is
  `FmDemod → Limit → NfmDeemphasis → Agc`: no high-pass anywhere, and the
  de-emphasis is a low-pass, so it lifts the sub-audible end rather than
  removing it. Most radios filter CTCSS out so you do not hear it; this one
  does not. On six minutes of real traffic the tone came out at **107.2 Hz,
  34.7 times the surrounding noise floor and 0.20 Hz from nominal** - measured
  on audio pulled through the websocket and decoded from ADPCM, which is
  exactly what a browser gets, so the compression does not cost it.

### Fixed

- **The 5-tone decoder was reporting almost nothing but rubbish, and missing
  almost every real call.** It compared the winning tone only against the
  runner-up *within the same standard's own eleven tones*, and never asked
  whether that tone stood out from the broadband floor. Speech has energy
  everywhere, so each of the six standards found its own "dominant" tone in
  the same breath of voice - which is why six different sequences kept
  arriving at the same instant.

  The gate added is spectral purity: the strongest bin against the **median of
  the whole 500-3000 Hz band**. Measured on six minutes of recorded traffic,
  against the ground truth that every call on that channel is CCIR and starts
  with 31: a true call reaches 122, speech peaks at 38, a silent channel at 6.
  The threshold is 20.

  It does not only remove rubbish. Without the gate the noise windows
  interleaved with the real tones and corrupted the digit runs before they
  could be emitted, so the calls never came out at all. On that recording the
  decoder went from **1 true call and 108 false ones to 9 true and 3 false**,
  and CCIR precision from 9% to 75%.

## v1.0.2 — 2026-11-25

### Fixed

- **The 5-tone panel's heading covered the first results** once the
  "hidden by the filter" notice appeared. OpenWebRX gives every message panel's
  tbody its own scrollbox - `display: block`, `overflow: auto` and a fixed
  `height: 150px` - and ABMod overrode only the display. A height on a
  `table-row-group` acts as a *minimum*, so with few rows the browser stretched
  each from 18px to 25px, and the box scrolled 6px inside a wrapper that was
  already scrolling, pushing the first row up under the sticky heading.
  Measured at **24px of overlap**, now 0. All three properties are undone, for
  the 2-tone panel as well. The notice is also one line instead of two, because
  the panel grows upward from the bottom of the screen and every extra line
  moves the whole thing.

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
