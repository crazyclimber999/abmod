# Everything ABMod adds

*[In italiano](../it/funzionalita.md)* · [back to the README](../../README.md)

Each section says what changed and, where the choice was not obvious, why.
Figures quoted are measured on a Raspberry Pi 3 against the Italian repeater
list, not estimated.

---

## 1. Access control

Upstream OpenWebRX has a login for the settings. ABMod extends it and fixes
what was missing.

- **Bookmarks need a login.** Hiding the button was not enough: the websocket
  commands behind it were answering anyone who sent them, so the check is on
  the server. The tags on the frequency scale also appear only once logged in.
- **Settings need an administrator.** Two levels, not one: a plain user can
  read and edit the bookmarks, an administrator reaches the settings.
- **A user management page** at `/settings/users` — add, remove, enable,
  disable, change passwords, grant or revoke administrator.
- **You cannot lock yourself out.** The page refuses to remove the last
  administrator, or to take the rights off the one you are logged in as.
- **A logout that logs out.** Upstream's was a placeholder that redirected to
  a page saying "logout happening here" and left the session alive.
- **Sessions survive a restart.** They used to live only in memory, and every
  restart — needed for any change under `owrx/` — logged everyone out. They
  are now on disk, mode `600`, with expired ones dropped on load.
- **Who you are, in the status panel**, with the logout beside it, rather than
  in the top bar.

## 2. The bookmarks panel

A panel in the receiver itself, backed by OpenWebRX's own bookmark storage —
not a parallel list.

- Search, sort by name or frequency, edit, delete.
- One click tunes **and** sets the modulation. Setting the centre frequency
  alone does not move the demodulator, which is why the first version appeared
  to tune to the wrong place.
- A dropdown switches the same panel between **bookmarks and the band plan**,
  so both are editable from the receiver.
- With FM or NFM selected, a **"Decode 5 tone"** box stores the bookmark as
  `5tone`, which the receiver resolves to NFM plus the decoder.

## 3. Editable band plan

The band plan is editable from the panel and from its own settings page at
`/settings/bandplan`. Edits work on the raw JSON rather than on parsed objects,
so entries using modes this receiver cannot demodulate — DMR, D-Star — survive
a round trip instead of being silently dropped.

## 4. Save Defaults

An administrator can store the receiver's current centre frequency and sample
rate as the startup defaults. Gain and squelch were deliberately left out:
they belong in the configuration file, and squelch is a per-listener setting
that never appears in the receiver's own properties.

Beside it, **frequency step buttons**: single arrows move 25 kHz, double
arrows 1 MHz, up and down.

## 5. 5-tone (SELCALL) decoder

Decodes **CCIR/EEA, ZVEI1, ZVEI2, DZVEI, EIA and CCITT at once** and reports
which standard produced each sequence. One FFT per window is shared between
all six; running a Goertzel per standard would cost several times as much.

The panel has a button per standard so you can show only the ones that make
sense on the frequency you are listening to — and it **counts what the filter
is hiding**, because a filter that discards in silence is indistinguishable
from a decoder that has failed.

Measured: **120 of 120** correct across the six standards at their own tone
lengths, **10 of 10** at every tone length from 40 ms to 250 ms, and **zero
false positives** on 30 seconds of noise. About 13% of one core while running.

Three things it gets right that are easy to get wrong:

- **A repeated digit sent as one long tone.** Many systems send `3,1,1,0,1`
  as four tones, the middle one twice as long. The length of a single tone is
  measured from the burst itself, never read from a table of nominal
  durations: a system sending 150 ms tones against a table saying 100 ms turns
  every single tone into two digits.
- **The squelch opening.** The burst of noise before a call adds a spurious
  leading digit, so the sequence is read from the end of the call, not the
  start.
- **The repeat tone in CCIR is 2110 Hz**, not the 2400 Hz that several
  references give — 2400 is the group tone. With the wrong value the third
  tone of every call falls outside the table, the sequence comes out four
  digits long, and nothing is ever emitted.

## 6. 2-tone paging decoder

A separate decoder, not a variation of the one above: a page is one tone held
about a second followed by a different, longer one.

**The measured frequency is the result; the tone plan is only a label.** The
tones are long, so the FFT peak can be refined by fitting a parabola through
its neighbours — measured error 0.0 to 0.3 Hz. Published tone plans disagree
with each other, so a pair that matches nothing is still reported as
"947.2 / 332.6 Hz" and remains useful.

Measured: 5 of 5 real pages decoded with the right plan, 6 of 6 negatives
rejected — a single long tone, a second tone shorter than the first, two
nearly identical tones, noise, silence, tones too short — and 23× faster than
real time.

Tone tables for Motorola Quick Call II groups 1–6 and the ZVEI tones are
included. They only ever add a name, never filter, so an error in them costs a
label and nothing else.

## 7. The map, without Google

Upstream draws the map with the Google Maps API, which needs a key tied to a
billing account — and hands that key to every visitor, because the browser
loads the API with it. ABMod draws the same map with **Leaflet on
OpenStreetMap tiles**.

- No key, no billing account, nothing to leak.
- The tile source is configurable, so any provider serving the usual
  `{z}/{x}/{y}` scheme can be used instead. Whoever serves the tiles decides
  what attribution must appear, so check their terms before changing it.
- **Day/night terminator** computed in place of the Google-specific overlay,
  and checked against the real solar position before being trusted.
- **APRS symbol markers** keep working, drawn from the sprite sheets your
  OpenWebRX already installs.
- The **receiver location picker** in the settings is Leaflet too: drag the
  marker, click the map, or type the coordinates — all three stay in step.

## 8. APRS

**Incoming — positions from aprs.fi.** A receiver only hears what is in range.
Give ABMod an aprs.fi API key and a list of callsigns to watch, and their last
known positions appear on the map beside the stations you heard yourself.

**The key never reaches the browser.** aprs.fi ties it to an account and
rate-limits on it; a key handed to the page would be usable by every visitor.
The receiver polls and pushes the results down the websocket it already has
open. Polling is clamped to one query a minute at most, which is what aprs.fi's
terms ask for, and positions older than the map's retention time are skipped.

**Outgoing — the igate.** OpenWebRX can forward what it hears to APRS-IS and
beacon its own position. Those settings existed but were on a different page
from everything else APRS; they are now gathered with the rest, complete with
the antenna height, gain and direction fields.

Two things worth knowing, because neither is obvious:

- The igate only runs for a **background decoder**. Nothing is forwarded from
  a browser session, so a packet service has to be configured and running.
- The **passcode is a number derived from your callsign**, not a website
  password. Without it the server accepts the connection and marks it
  *unverified*, then silently discards everything you send.

## 9. Importing a repeater list

At `/settings/bookmarkimport`, reachable from the bookmark editor.

**Formats.** `.xls` through `xlrd`, `.xlsx` through the standard library
alone, `.csv` with the delimiter sniffed and a utf-8 / latin-1 fallback. From
a web address or a file you upload. An example file is downloadable.

**Nothing is assumed about the layout.** The columns are mapped from
dropdowns, guessed from the file's own headers as a starting point. Two parts
make up the name, with a separator you choose, and any other columns can be
appended in brackets.

**Filter by region**, with a tick box per region and a count of the rows each
one holds.

**Translate the modulations.** No published list uses the receiver's names.
Each value in the source is mapped to a mode — or to *(ignore import)* to leave
those rows out entirely. Modes the receiver cannot demodulate are listed but
not selectable, so it is plain why DMR cannot be chosen rather than looking
like an omission.

**Preview every row**, 25 at a time, numbered, with page controls — not just
the first 25, because what you are checking is what the mapping did to the
other thousand.

**Save the whole arrangement as the default**: source URL, header row, column
mapping, units, regions, modulation table and the filter's own thresholds.

**One bookmark per channel.** A national list reuses the same frequency dozens
of times — 24 different repeaters share 145.750 MHz in the Italian one. Keep
the one heard best and drop the rest. Optionally let an imported station
displace a bookmark you already had on that frequency.

**It tells you what it is leaving out**, always: how many rows the
listenability filter removed, and how many are about to collapse into each
other because their names are not distinct enough.

## 10. Can you actually hear it?

The most involved piece. Optionally, the importer works out what the ground
between you and each station does to the signal.

**Elevation data** is SRTM at one arc-second, from a public tile service that
needs no account, stored reduced to three arc-seconds — 2.9 MB a tile instead
of 25.9 MB, about 85 MB for a 200 km radius. It is validated against known
heights before being used.

It is fetched from the **general settings**, under the radius that decides how
much of it to keep, and from the import page as well. The page says how many
tiles are there and how many are missing, and the download is a button rather
than something "Apply and save" does quietly — a settings save that pulls a few
hundred megabytes with no progress and no way to stop it is a surprise that
gets blamed on something else.

**The model** is the standard one: the ground profile along the great circle,
the earth given an effective radius of 4/3 for atmospheric refraction,
obstacles treated as knife edges by Deygout's method, then free-space loss and
your antenna's gain in that direction. The answer is a **margin in decibels**,
not a yes or no.

That matters. A first version demanding clear line of sight declared a
repeater four kilometres away across flat ground unreachable. In VHF an
obstacle attenuates, it does not cut off.

**Your antenna** is described in the settings: height above ground, gain, and
an optional horizontal pattern given as numbers read evenly around the compass
from north. Leave the pattern empty and the antenna is omnidirectional.

**Where the far station stands.** A six-character locator is a rectangle about
five kilometres across — too coarse to pick a point. A repeater sits on high
ground, so the highest point in the square is used instead of the middle: for
the square holding Monte Resegone that is 1643 m rather than 1130 m, and the
summit is where the antenna actually is. For a four-character locator, which
spans a whole degree, the highest point would be an unrelated mountain, so the
centre is used instead.

**Beyond the horizon it says so** rather than guessing. A knife edge's loss
grows slowly with distance while the real obstruction out there is the curve of
the earth, which diffracts far worse; left alone the model called a repeater
270 km away receivable. What happens past the horizon is weather, not geometry.

Measured on 1584 repeaters: 5.4 ms each, four seconds for the lot. Within
150 km there are 397 and **the terrain excludes 103** — a quarter of what a
distance filter alone would import.

**What it cannot know**: buildings and trees, and the power of the far
station, which no repeater list carries. The transmitter power is an
assumption you set. It is an estimate, and a good one, but an estimate.

## 11. Bulk deletion

Once a repeater list has been imported the bookmark editor runs to hundreds of
rows. Each row now has a checkbox, the header has a select-all, **shift-click
selects a range**, and the button names the first five before deleting
anything. The deletion goes as one request rather than one per row.

If the list changed since the page was loaded, it says so instead of reporting
a successful deletion of nothing.

## 12. CTCSS sub-audible tone readout

The tone is shown under the frequency readout and written to the log, and it
**stays** once read: CTCSS is a property of the channel, not of the moment, so
clearing it when the carrier drops would show it for two seconds and then
remove exactly the information that was wanted. It is replaced when a
different tone is heard, and forgotten when you retune.

It is decoded **in the browser, from the same samples the speaker gets**. That
is not a shortcut — it is where the tone actually survives. OpenWebRX's NFM
chain ends in a de-emphasis, which is a low-pass, so it lifts the sub-audible
end rather than removing it, and there is no high-pass anywhere in that chain
to strip it. A radio filters CTCSS out so you do not hear it; this one does
not, which is why there is something left to measure.

Measured on a live transmission: the tone stood **34.7 times** the surrounding
noise floor, **0.20 Hz** from the nominal 107.2 Hz. 39 standard tones are
tested with a Goertzel each over a two-second window after decimating to about
1 kHz, which costs a few hundred thousand operations a second — far less than
a transform would. Two seconds is not caution, it is resolution: the closest
pairs in the table are about 2.5 Hz apart and a shorter window smears them
together. A reading needs two consecutive windows to agree, because a
transmission that has only just opened often gives one good window and one
ragged one.

It runs on narrowband FM and nothing else. CTCSS is an analogue FM
arrangement, so there is nothing to look for on AM or SSB, and the digital
modes - DMR, D-Star, YSF, NXDN, M17 - carry their access control in the
protocol with no room in the standard for a tone below the voice band.
Looking there could only produce a false reading and a line in the log
asserting something that cannot be true. Switching to one of those modes
clears the display rather than leaving the last tone on screen.

## 13. Automatic direct sampling below the tuner's floor

An R820T cannot tune below roughly 24 MHz. Below that the only way in is the
ADC's own input — direct sampling — which on an RTL-SDR v3 is wired to the Q
branch. ABMod switches to it when the receiver is tuned under that floor, and
back out again when it returns, and marks the state with a **DS** badge beside
the Set button.

The awkward part is that direct sampling is not a tunable parameter. It is a
command line option of the connector, while the frequency travels live over
the control socket, so setting the property alone changes nothing: the
connector was started with the old value and keeps it. The device therefore has
to be stopped and started, every listener loses a few seconds of audio, and
that is announced in the log rather than suffered in silence.

Two details decide whether it works at all:

- **The frequency is written before the mode.** The other way round, the
  connector comes up on the old frequency in the new mode and then has to be
  retuned over the control socket — which for a tuner asked to reach 6 MHz
  never works. Measured before the fix: the receiver ended on 15.001 MHz,
  neither the frequency it left nor the one it was asked for.
- **The decision is made on the top of the sampled window, not its centre.** A
  window centred at 23 MHz reaches up to 24.25 MHz and the tuner can serve all
  of it. Direct sampling has no filtering in front of it and everything strong
  folds in, so taking it when the tuner would have done is the worse choice.

Measured on this hardware at 6 and 7 MHz with direct sampling on: discrete
lines stand **29 dB** above the noise floor, which a disconnected input does
not produce. An HF antenna is still needed for any of it to be useful.

## 14. DMR identities without the AMBE codec

DMR needs two things, and only one of them is free. digiham, which
synchronises on the TDMA bursts and extracts both the voice frames and the
signalling, is in the Debian repository. The AMBE+2 decoder is not:
codecserver ships a single driver, `libambe3k.so`, and that is not a software
codec at all — it drives an AMBE-3000 chip over a serial port. Without that
hardware upstream withdraws the whole mode, signalling included, even though
the signalling never passes through the codec.

In upstream's own chain the metadata leaves by its own route — the decoder's
`setMetaWriter`, not the synthesizer's — so a chain that stops at the decoder
still reports **who is transmitting, on which talkgroup, in which timeslot**,
resolved against RadioID by the parser that is already there and shown in the
panel the DMR mode already has. ABMod builds that chain when the codec is
missing and upstream's full chain when it is present, so an AMBE-3000 dongle
would turn the audio on with no further change.

What is lost is the audio, and only the audio. That is said in the log when
the mode is selected, because a mode that normally carries sound and suddenly
does not looks like a fault. The slot filter, the metadata panel and the
bandplan entries are untouched: the mode is still `dmr`, with the same name
and the same bandwidth.

## 15. The gateway runs when nobody is listening

The igate and a listener want the receiver on two different frequencies. The
packet service only runs where a band plan entry for it falls inside the
sampled window, so a listener who tunes away from 144.800 takes the gateway
down with them — which is why that is one of the two things that silently kill
an igate.

They never want it at the same time, though. Nobody is listening at four in
the morning, which is exactly when the gateway could be working. So,
optionally: the last listener to leave starts a clock, ten minutes by default,
and when it runs out the receiver moves itself to the APRS frequency. The
moment someone connects it goes back to the centre frequency saved for the
profile — before that client is told anything, so what it sees is already
true.

Three things this gets right by construction:

- **Only the running properties are written, never `settings.json`.** A parked
  receiver that is restarted comes back on its default. The parking is a
  temporary state, not a configuration, and it behaves like one.
- **The default is re-read from `settings.json` when going back**, not from the
  live configuration and not remembered from before parking. The live
  configuration looks like the obvious place and is the wrong one: the property
  stack's top layer is the profile's own object, so every retune writes
  straight through into it, and asked what the default is it answers with
  wherever the receiver happens to be pointing. `settings.json` is written only
  by Save Defaults, which is the intent worth honouring - so an operator who
  saves a new default while the receiver is parked gets that new one back.
- **It does nothing unless the igate is on.** The parking has no purpose of
  its own: it exists to feed *Send received APRS data to the APRS-IS network*.
  With that off, moving the receiver away from the frequency its operator
  saved buys nothing, so the clock is never even started.
- **It refuses to park a radio that is switched off.** Without *Keep device
  running at all times* the source stops as soon as the last listener leaves,
  so moving its frequency would achieve nothing. It says so in the log instead.
- **Every refusal says why, in the log.** A receiver that never parks because
  visitors keep arriving reads exactly like one that never parks because
  something is broken, so each way out says which it is: the igate is off, a
  listener is still connected, a listener arrived while the clock ran, the
  radio is already on the APRS frequency.
- **The clock is armed at start-up too**, not only when a listener leaves. A
  receiver that has just been restarted and that nobody has visited since is
  exactly the one that should be gatewaying, and waiting for a visitor to
  arrive and leave again before parking would have it the wrong way round.
- **"Already there?" is asked of where the radio is pointing now**, not of the
  saved default. A station that mostly gates will have 144.800 saved as its
  default, and it is precisely that receiver that needs parking after a visitor
  has moved the centre away and left. Comparing against the default would skip
  that case and leave the gateway dead until the next restart; comparing
  against the current frequency parks when it has to and keeps quiet when the
  receiver is already where it belongs.

The cost is real and stated on the settings page: **any** visitor connecting
stops the gateway, not only the operator. On a busy public receiver that can
mean it rarely runs. It is off by default.

## 16. The gain survives a reconnection

Only matters when the SDR is served over the network - `rtl_tcp` or
`soapy_remote` - and then it matters a great deal.

openwebrx sends the gain to the connector once, when it starts it. The
connector does not send it again when it reconnects by itself, and rtl_tcp
resets the tuner whenever a client connects. So a restart of the dongle
server, a wi-fi blink or a pulled cable leaves the receiver at minimum gain,
and nothing says so: the settings page, the saved configuration and the
connector's own command line all still read the value you chose. The only
sign is a waterfall gone dark, which looks like an antenna problem or a dead
preamplifier rather than a setting that never arrived.

So for those device types the gain is re-asserted over the control socket
every thirty seconds. Setting a tuner to the gain it already has costs
nothing and is inaudible, which is what makes repeating it the right answer
rather than detecting the reconnection - the detection would have to be
reliable, and the repetition does not.

A device left on automatic gain is skipped on purpose: re-sending `auto`
would be re-asking for a mode rather than restoring a value.

## 17. Smaller things

- **The compiled JavaScript is no longer cached for an hour.** Upstream sends
  the bundles with `Cache-Control: max-age=3600`, which licenses a browser to
  keep them without asking — so a deploy could be legitimately invisible for
  sixty minutes, and a fix already on the receiver looked like a fix that had
  failed. Now `max-age=0`: the browser revalidates and gets a 304 with no body
  when nothing changed, measured at 0 bytes against 229 KB.
- **A start-up race, fixed.** A websocket arriving during start-up could hit
  `multiprocessing.connection` while another thread was importing it, raising
  `ImportError` and dropping that connection. The module is now loaded before
  any thread starts.
- **The message panels lay out correctly.** Upstream splits them into two
  tables, which drift apart by the width of the scrollbar and leave every
  heading out of line with its column.

---

## What ABMod deliberately does not change

- **Your configuration.** `settings.json`, bookmarks and users are never
  touched by the installer.
- **The receiver tuning commands stay open.** Any visitor can retune the
  receiver, change the gain or open the squelch, for everybody. That is
  upstream's behaviour and it is normal for a public WebSDR. Be aware that the
  change reaches the stored configuration, so an administrator saving any
  settings page afterwards makes it permanent. If you would rather not have
  that, it is the one thing worth adding yourself.
- **DMR, D-Star, YSF and NXDN still need a codec.** OpenWebRX has the modes;
  what is missing is an AMBE codec for codecserver, which is a licensing
  decision rather than a coding one.
