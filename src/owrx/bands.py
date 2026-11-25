from owrx.modes import Modes
from owrx.config.core import CoreConfig
from datetime import datetime, timezone
import json
import os

import logging

logger = logging.getLogger(__name__)


class Band(object):
    def __init__(self, dict):
        self.name = dict["name"]
        self.lower_bound = dict["lower_bound"]
        self.upper_bound = dict["upper_bound"]
        self.frequencies = []
        if "frequencies" in dict:
            availableModes = [mode.modulation for mode in Modes.getAvailableModes()]
            for (mode, freqs) in dict["frequencies"].items():
                if mode not in availableModes:
                    logger.info(
                        'Modulation "{mode}" is not available, bandplan bookmark will not be displayed'.format(
                            mode=mode
                        )
                    )
                    continue
                if not isinstance(freqs, list):
                    freqs = [freqs]
                for f in freqs:
                    if not self.inBand(f):
                        logger.warning(
                            "Frequency for {mode} on {band} is not within band limits: {frequency}".format(
                                mode=mode, frequency=f, band=self.name
                            )
                        )
                        continue
                    self.frequencies.append({"mode": mode, "frequency": f})

    def inBand(self, freq):
        return self.lower_bound <= freq <= self.upper_bound

    def getName(self):
        return self.name

    def getDialFrequencies(self, range):
        (low, hi) = range
        return [e for e in self.frequencies if low <= e["frequency"] <= hi]


class Bandplan(object):
    sharedInstance = None

    @staticmethod
    def getSharedInstance():
        if Bandplan.sharedInstance is None:
            Bandplan.sharedInstance = Bandplan()
        return Bandplan.sharedInstance

    def __init__(self):
        self.bands = []
        self.file_modified = None
        # The copy in the data directory comes first and is the editable one:
        # /etc/openwebrx/bands.json belongs to the package, is owned by root and
        # is not writable by the openwebrx user. It stays as the default.
        self.fileList = [Bandplan._getBandsFile(), "/etc/openwebrx/bands.json", "bands.json"]

    @staticmethod
    def _getBandsFile():
        coreConfig = CoreConfig()
        return "{data_directory}/bands.json".format(data_directory=coreConfig.get_data_directory())

    def store(self, bands_json):
        """
        Writes the bandplan to the data directory. _refresh() picks the change up
        on the next access through the file modification time.
        """
        with open(Bandplan._getBandsFile(), "w") as f:
            json.dump(bands_json, f, indent=4)
        self.file_modified = None

    # ------------------------------------------------------------------
    # editing helpers
    #
    # These work on the RAW json and never on the parsed Band objects: the
    # loader silently drops modes that are not currently available and
    # frequencies outside their band bounds, so rebuilding the file from the
    # parsed objects would delete them. Both the websocket handler and the
    # settings page go through here.
    # ------------------------------------------------------------------

    def loadRaw(self):
        for file in self.fileList:
            try:
                with open(file, "r") as f:
                    return json.load(f)
            except FileNotFoundError:
                continue
        return []

    def listEntries(self):
        entries = []
        for band in self.loadRaw():
            for mode, value in (band.get("frequencies") or {}).items():
                for freq in value if isinstance(value, list) else [value]:
                    entries.append(
                        {"band": band.get("name"), "modulation": mode, "frequency": freq, "name": mode}
                    )
        return entries

    @staticmethod
    def removeFromRaw(raw, band_name, mode, freq):
        removed = False
        for band in raw:
            if band_name is not None and band.get("name") != band_name:
                continue
            freqs = band.get("frequencies") or {}
            if mode not in freqs:
                continue
            values = freqs[mode] if isinstance(freqs[mode], list) else [freqs[mode]]
            kept = [f for f in values if f != freq]
            if len(kept) != len(values):
                removed = True
                if not kept:
                    del freqs[mode]
                else:
                    # keep the original shape: a single value stays a scalar
                    freqs[mode] = kept if len(kept) > 1 else kept[0]
        return removed

    def saveEntry(self, mode, freq, original=None):
        """
        Inserts or moves an entry. Returns (ok, message). The band is derived
        from the frequency, so an entry can never land outside its bounds.
        """
        mode = (mode or "").strip()
        freq = int(freq)
        if not mode or freq <= 0:
            return False, "A mode and a valid frequency are required"

        raw = self.loadRaw()
        band = next((b for b in raw if b.get("lower_bound", 0) <= freq <= b.get("upper_bound", 0)), None)
        if band is None:
            return False, "No band covers {0:.4f} MHz".format(freq / 1e6)

        if original:
            Bandplan.removeFromRaw(
                raw, original.get("band"), original.get("modulation"), int(original.get("frequency", 0))
            )

        freqs = band.setdefault("frequencies", {})
        values = freqs.get(mode)
        values = (values if isinstance(values, list) else [values]) if values is not None else []
        if freq not in values:
            values.append(freq)
        values.sort()
        freqs[mode] = values if len(values) > 1 else values[0]

        self.store(raw)
        return True, "Saved in band {0}".format(band.get("name"))

    def deleteEntry(self, band_name, mode, freq):
        raw = self.loadRaw()
        if not Bandplan.removeFromRaw(raw, band_name, mode, int(freq)):
            return False, "Entry not found"
        self.store(raw)
        return True, "Entry deleted"

    def _refresh(self):
        modified = self._getFileModifiedTimestamp()
        if self.file_modified is None or modified > self.file_modified:
            logger.debug("reloading bands from disk due to file modification")
            self.bands = self._loadBands()
            self.file_modified = modified

    def _getFileModifiedTimestamp(self):
        timestamp = 0
        for file in self.fileList:
            try:
                timestamp = os.path.getmtime(file)
                break
            except FileNotFoundError:
                pass
        return datetime.fromtimestamp(timestamp, timezone.utc)

    def _loadBands(self):
        for file in self.fileList:
            try:
                f = open(file, "r")
                bands_json = json.load(f)
                f.close()
                return [Band(d) for d in bands_json]
            except FileNotFoundError:
                pass
            except json.JSONDecodeError:
                logger.exception("error while parsing bandplan file %s", file)
                return []
            except Exception:
                logger.exception("error while processing bandplan from %s", file)
                return []
        return []

    def findBands(self, freq):
        self._refresh()
        return [band for band in self.bands if band.inBand(freq)]

    def findBand(self, freq):
        bands = self.findBands(freq)
        if bands:
            return bands[0]
        else:
            return None

    def collectDialFrequencies(self, range):
        self._refresh()
        return [e for b in self.bands for e in b.getDialFrequencies(range)]
