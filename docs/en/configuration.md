# Configuration

*[In italiano](../it/configurazione.md)* · [back to the README](../../README.md)

Everything below is under **Settings**, and everything under Settings needs an
administrator. The settings ABMod adds are grouped with the ones they belong
beside.

---

## Receiver details

Nothing new here, but **the coordinates matter more than they used to**. They
decide where the map centres, what the APRS beacon transmits, and the point the
listenability filter measures every path from. A receiver still carrying the
coordinates of the machine it was cloned from will give confident, wrong
answers.

---

## Map settings

| Setting | What it does |
| --- | --- |
| **Map tile URL** | Template of the tile server, in the usual `{z}/{x}/{y}` scheme. The default is OpenStreetMap. |
| **Map tile attribution** | The credit shown in the corner. Whoever serves the tiles decides what must appear here, so read their terms before changing the URL. |
| **Map retention time** | How long a station stays on the map after it was last heard. Also the age beyond which an aprs.fi position is ignored. |

No API key, anywhere.

---

## APRS: positions from aprs.fi (incoming)

Shows stations you cannot hear yourself.

| Setting | What it does |
| --- | --- |
| **aprs.fi API key** | From "My account" on aprs.fi. The key stays on the server and is never sent to the browser. Empty switches the whole thing off. |
| **Callsigns to watch** | Comma separated, for example `N0CALL-9, N0CALL-7`. aprs.fi answers at most 20 names per query, so longer lists are split. |
| **Polling interval** | Default 300 s. **Clamped to a minimum of 60 s**, because aprs.fi's terms ask for no more than one query a minute. |

---

## APRS: igate (outgoing)

Forwards what the receiver hears to APRS-IS. This is the opposite direction to
the settings above, and it **transmits under your callsign**.

| Setting | What it does |
| --- | --- |
| **Station callsign** | How the receiver identifies itself on APRS-IS. Leaving it at `N0CALL` would put your station on the network under a placeholder. |
| **Send received APRS data** | The master switch. |
| **APRS-IS server** | `euro.aprs2.net` and friends. |
| **APRS-IS passcode** | **A number derived from your callsign**, not a website password. There is a button beside the field that works it out for you; the SSID makes no difference, so `N0CALL`, `N0CALL-1` and `N0CALL-10` share one passcode. Get it wrong and the server accepts the connection, marks it *unverified*, and silently discards everything you send. |
| **Send the receiver position** | Beacons where you are. Check the coordinates first: this makes them public. |
| **Beacon interval** | How often the position repeats, in minutes. A fixed station does not need to shout: 30 is normal, under 10 is poor manners on a shared network. Clamped to 5–240. |
| **Beacon symbol, text, antenna height, gain, direction** | What the beacon carries. |

### The igate stops when nobody is listening

This one costs people weeks, so it is worth stating plainly: **with no
listeners connected, the receiver shuts the SDR down, and the igate stops with
it.** Positions then age out of aprs.fi and the station looks dead, while every
setting on this page reads as correct.

It is not a fault. OpenWebRX's background service handler registers itself with
the SDR as an `INACTIVE` client, and the source only starts for a `USER` or
`BACKGROUND` one, so services never start the radio — they attach to a radio
already running for a listener. The moment the last listener leaves,
`checkStatus()` stops it.

The cure is a setting that already exists and is easy to miss, because it is an
*optional* field: **Settings → SDR device → Additional optional settings →
"Keep device running at all times" → Add → tick → save.** That writes
`always-on` into the device, and the source then never idles down.

What it costs: the dongle runs 24 hours a day, the packet decoder with it, and
the load settles around 2.4 on a Raspberry Pi 3 instead of near zero. On a Pi
that is already short of power this is exactly the combination that makes USB
devices drop out — check `vcgencmd get_throttled` before and after, and if the
low nibble is anything but 0 you have an under-voltage problem to fix first.

### Two more things that are not obvious

- The igate only runs for a **background decoder**, so a packet service must be
  configured and running. Nothing is forwarded from a browser session.
- **Two stations cannot be verified on APRS-IS under the same callsign at the
  same time.** If you run more than one receiver, give each a different SSID.
- **A settings page left open overwrites what changed behind it.** Saving a
  form that was loaded before a change writes the old values back. If the
  passcode stops working after you save something else, press the button
  beside it and save again.

---

## Receiving antenna

Used by the listenability filter.

| Setting | What it does |
| --- | --- |
| **Height above ground** | Where the antenna is, not where the receiver is. Decides how far your horizon reaches and what the signal must clear. |
| **Gain** | 2 dBi is a plain vertical. |
| **Horizontal pattern** | Gain relative to the figure above, in dB, as numbers read evenly around the compass **starting at north**. Eight values are one every 45°, thirty-six are one every 10°. For example `0,-3,-10,-18,-25,-18,-10,-3` is a beam pointing north. **Leave it empty for an omnidirectional antenna**, which is what is assumed when nothing is given. |

---

## Listenability estimate

| Setting | What it does |
| --- | --- |
| **Terrain data radius** | How far around the receiver elevation data is kept. Roughly 1.3 MB of download and 0.4 MB on disk per kilometre of radius: 200 km is about 250 MB fetched and 85 MB stored. |
| **Assumed transmitter power** | No repeater list carries the power of its stations, so one figure stands for all of them. 40 dBm is 10 W. |
| **Assumed remote antenna height** | Above the ground at the far end. The ground itself comes from the elevation data. |
| **Usable signal level** | The level at which a signal counts as listenable. −116 dBm is about what narrow FM needs to be readable. |

### Downloading the elevation data

Under the radius field this page says how much of the data is actually there:
how many tiles out of how many, how much disk they take, and, when some are
missing, roughly how much there is left to fetch. A **Download** button appears
when something is missing, and while it runs the line refreshes every few
seconds. Leaving the page does not stop it. The same control is on the import
page.

Two things about that figure. It always describes the radius that is **saved**,
not the one typed in the box, so change the radius, press *Apply and save*, and
check again. And a tile that is entirely sea does not exist at the source, so on
a coastal receiver the count never reaches the full number — that is normal, not
a failed download.

"Apply and save" deliberately does **not** start the download. The radius is a
setting; the data it describes is a few hundred megabytes from a public tile
service, and a settings save that quietly pulls 250 MB over a domestic line,
with no progress and nothing to stop, is a surprise that gets blamed on
something else entirely.

---

## Users

At `/settings/users`. Add, remove, enable, disable, change passwords, grant or
revoke administrator.

Two levels: a plain user reads and edits the bookmarks, an administrator
reaches the settings. The page will not let you remove the last administrator
or take the rights off the account you are using.

The first user has to be made from the command line:

```bash
sudo openwebrx admin adduser <name>
```

---

## Files, and which ones are yours

| Path | What it is |
| --- | --- |
| `/var/lib/openwebrx/settings.json` | Everything above. **Holds your API keys — keep it mode `600`.** Per receiver; never copy it between machines without editing the location. |
| `/var/lib/openwebrx/bookmarks.json` | Your bookmarks. |
| `/var/lib/openwebrx/users.json` | Accounts and password hashes. |
| `/var/lib/openwebrx/sessions.json` | Live logins. Mode `600`; safe to delete, everyone just logs in again. |
| `/var/lib/openwebrx/terrain/` | Elevation tiles. Safe to delete; the general settings offer to fetch them again. |

The installer never touches the first three.
