"""
Positions pulled from the aprs.fi database.

The receiver only ever hears the stations inside its own range, which on VHF
is a circle of a few tens of kilometres. aprs.fi knows where everything else
is, so a short list of callsigns can be watched there and drawn on the same
map, next to the stations the receiver heard itself.

The API key never leaves the server. aprs.fi ties the key to an account and
rate-limits on it, so a key handed to the browser would be visible to every
visitor and usable by any of them; the positions reach the map through the
websocket the receiver already has open.
"""

from owrx.config import Config
from owrx.map import Map
from owrx.aprs import AprsLocation, getSymbolData

from urllib.parse import urlencode
from urllib.request import Request, urlopen
from datetime import datetime

import json
import threading
import time

import logging

logger = logging.getLogger(__name__)


class AprsFiPoller(object):
    sharedInstance = None
    creationLock = threading.Lock()

    # aprs.fi takes at most 20 callsigns in one query
    MAX_NAMES_PER_REQUEST = 20
    # their terms ask for no more than one query per minute; the setting is
    # clamped to this so a careless value cannot get the key banned
    MIN_INTERVAL = 60
    ENDPOINT = "https://api.aprs.fi/api/get"
    # a generic identifier: the receiver's owner is not disclosed to aprs.fi
    # beyond what the API key itself already tells them
    USER_AGENT = "OpenWebRX-aprsfi/1.0"

    @staticmethod
    def getSharedInstance():
        with AprsFiPoller.creationLock:
            if AprsFiPoller.sharedInstance is None:
                AprsFiPoller.sharedInstance = AprsFiPoller()
        return AprsFiPoller.sharedInstance

    @staticmethod
    def start():
        AprsFiPoller.getSharedInstance()._start()

    def __init__(self):
        self.thread = None
        self.doRun = False

    def _start(self):
        if self.thread is not None:
            return
        self.doRun = True
        self.thread = threading.Thread(target=self._loop, daemon=True, name="aprsfi_poller")
        self.thread.start()

    def stop(self):
        self.doRun = False

    def _config(self):
        pm = Config.get()

        def get(key, fallback):
            return pm[key] if key in pm else fallback

        key = (get("aprsfi_api_key", "") or "").strip()
        raw = get("aprsfi_callsigns", "") or ""
        if isinstance(raw, str):
            names = [n.strip().upper() for n in raw.replace(";", ",").split(",")]
        else:
            names = [str(n).strip().upper() for n in raw]
        names = [n for n in names if n]

        interval = get("aprsfi_poll_interval", 300)
        try:
            interval = int(interval)
        except (TypeError, ValueError):
            interval = 300
        interval = max(AprsFiPoller.MIN_INTERVAL, interval)

        return key, names, interval

    def _loop(self):
        # nothing is configured at first boot, so do not hammer the log
        while self.doRun:
            interval = 300
            try:
                key, names, interval = self._config()
                if key and names:
                    self.poll(key, names)
            except Exception:
                logger.exception("error while polling aprs.fi")
            for _ in range(interval):
                if not self.doRun:
                    return
                time.sleep(1)

    def poll(self, key, names):
        for i in range(0, len(names), AprsFiPoller.MAX_NAMES_PER_REQUEST):
            chunk = names[i : i + AprsFiPoller.MAX_NAMES_PER_REQUEST]
            try:
                self._query(key, chunk)
            except Exception:
                logger.exception("error while querying aprs.fi for %s", ",".join(chunk))

    def _query(self, key, names):
        url = "{0}?{1}".format(
            AprsFiPoller.ENDPOINT,
            urlencode({"name": ",".join(names), "what": "loc", "apikey": key, "format": "json"}),
        )
        request = Request(url, headers={"User-Agent": AprsFiPoller.USER_AGENT})
        with urlopen(request, timeout=20) as response:
            data = json.loads(response.read().decode("utf-8"))

        if data.get("result") != "ok":
            # the key being wrong or exhausted is the usual reason, and it will
            # not fix itself, so say which it was instead of retrying silently
            logger.warning(
                "aprs.fi refused the query: %s (%s)",
                data.get("description", "no description"),
                data.get("code", "no code"),
            )
            return

        entries = data.get("entries") or []
        logger.debug("aprs.fi returned %d position(s) for %d callsign(s)", len(entries), len(names))
        for entry in entries:
            try:
                self._report(entry)
            except Exception:
                logger.exception("error while handling an aprs.fi entry")

    def _maxAge(self):
        pm = Config.get()
        # the map drops a station this long after it was last updated, so a
        # position already older than that would appear and immediately age out
        return pm["map_position_retention_time"] if "map_position_retention_time" in pm else 2 * 60 * 60

    def _report(self, entry):
        callsign = entry.get("name")
        if not callsign:
            return

        lasttime = entry.get("lasttime") or entry.get("time")
        if lasttime is not None:
            age = datetime.now().timestamp() - float(lasttime)
            if age > self._maxAge():
                logger.debug("skipping %s: position is %d s old", callsign, age)
                return

        data = {"lat": float(entry["lat"]), "lon": float(entry["lng"])}

        comment = entry.get("comment")
        if comment:
            data["comment"] = comment

        # aprs.fi gives the symbol as two characters: the table, then the code
        symbol = entry.get("symbol")
        if symbol and len(symbol) >= 2:
            data["symbol"] = getSymbolData(symbol[1], symbol[0])

        for key, target in [("course", "course"), ("speed", "speed")]:
            value = entry.get(key)
            if value not in (None, ""):
                try:
                    data[target] = float(value)
                except (TypeError, ValueError):
                    pass

        Map.getSharedInstance().updateLocation(callsign, AprsLocation(data), "APRS (aprs.fi)", None)
