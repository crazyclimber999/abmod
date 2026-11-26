import json
import logging
import threading
import pickle
import re
from abc import ABC, ABCMeta, abstractmethod
from datetime import datetime, timedelta
from urllib import request
from urllib.error import HTTPError

from csdr.module import PickleModule
from owrx.aprs import AprsParser, AprsLocation
from owrx.config import Config
from owrx.map import Map, LatLngLocation
from owrx.bands import Bandplan

logger = logging.getLogger(__name__)


class Enricher(ABC):
    def __init__(self, parser):
        self.parser = parser

    @abstractmethod
    def enrich(self, meta, callback):
        pass


class RadioIDCache(object):
    sharedInstance = None

    @staticmethod
    def getSharedInstance():
        if RadioIDCache.sharedInstance is None:
            RadioIDCache.sharedInstance = RadioIDCache()
        return RadioIDCache.sharedInstance

    def __init__(self):
        self.cache = {}
        self.cacheTimeout = timedelta(seconds=86400)

    def isValid(self, mode, radio_id):
        key = self.__key(mode, radio_id)
        if key not in self.cache:
            return False
        entry = self.cache[key]
        return entry["timestamp"] + self.cacheTimeout > datetime.now()

    def __key(self, mode, radio_id):
        return "{}-{}".format(mode, radio_id)

    def put(self, mode, radio_id, value):
        self.cache[self.__key(mode, radio_id)] = {"timestamp": datetime.now(), "data": value}

    def get(self, mode, radio_id):
        if not self.isValid(mode, radio_id):
            return None
        return self.cache[self.__key(mode, radio_id)]["data"]


class RadioIDEnricher(Enricher):
    def __init__(self, mode, parser):
        super().__init__(parser)
        self.mode = mode
        self.threads = {}
        self.callbacks = {}

    def _fillCache(self, id):
        data = self._downloadRadioIdData(id)
        RadioIDCache.getSharedInstance().put(self.mode, id, data)
        if id in self.callbacks:
            while self.callbacks[id]:
                self.callbacks[id].pop()(data)
            del self.callbacks[id]
        del self.threads[id]

    def _downloadRadioIdData(self, id):
        try:
            logger.debug("requesting radioid metadata for mode=%s and id=%s", self.mode, id)
            res = request.urlopen("https://www.radioid.net/api/{0}/user/?id={1}".format(self.mode, id), timeout=30)
            if res.status != 200:
                logger.warning("radioid API returned error %i for mode=%s and id=%s", res.status, self.mode, id)
                return None
            data = json.loads(res.read().decode("utf-8"))
            if "count" in data and data["count"] > 0 and "results" in data:
                for item in data["results"]:
                    if "id" in item and item["id"] == id:
                        return item
        except json.JSONDecodeError:
            logger.warning("unable to parse radioid response JSON")
        except HTTPError as e:
            logger.warning("radioid responded with error: %s", str(e))

        return None

    def enrich(self, meta, callback):
        config_key = "digital_voice_{}_id_lookup".format(self.mode)
        if not Config.get()[config_key]:
            return meta
        if "source" not in meta:
            return meta
        id = int(meta["source"])
        cache = RadioIDCache.getSharedInstance()
        if not cache.isValid(self.mode, id):
            if id not in self.threads:
                self.threads[id] = threading.Thread(target=self._fillCache, args=[id], daemon=True)
                self.threads[id].start()
            if id not in self.callbacks:
                self.callbacks[id] = []

            def onFinish(data):
                if data is not None:
                    meta["additional"] = data
                callback(meta)

            self.callbacks[id].append(onFinish)
            return meta
        data = cache.get(self.mode, id)
        if data is not None:
            meta["additional"] = data
        return meta


class DigihamEnricher(Enricher, metaclass=ABCMeta):
    def parseCoordinate(self, meta, mode):
        for key in ["lat", "lon"]:
            if key in meta:
                meta[key] = float(meta[key])
        callsign = self.getCallsign(meta)
        if callsign is not None and "lat" in meta and "lon" in meta:
            loc = LatLngLocation(meta["lat"], meta["lon"])
            Map.getSharedInstance().updateLocation(callsign, loc, mode, self.parser.getBand())
        return meta

    @abstractmethod
    def getCallsign(self, meta):
        pass


class TalkgroupNames(object):
    """
    Names for DMR talkgroups, so a call reads "222 (Italia)" and not just a
    number.

    A hand-held radio knows these from its contact list, written in when the
    codeplug was built. A web receiver has no codeplug, so the names come from
    BrandMeister's published list: about 1850 entries in some 45 kB, which is
    one download rather than a request per call.

    It is cached on disk and refreshed weekly. The download happens on a
    thread, never in the path a metadata frame takes: a talkgroup name is a
    convenience, and waiting on the network for one would delay the thing it
    is supposed to be decorating. Until it arrives, calls show the bare
    number, which is what they showed before.
    """

    URL = "https://api.brandmeister.network/v2/talkgroup/"
    MAX_AGE = timedelta(days=7)
    sharedInstance = None
    creationLock = threading.Lock()

    @staticmethod
    def getSharedInstance():
        with TalkgroupNames.creationLock:
            if TalkgroupNames.sharedInstance is None:
                TalkgroupNames.sharedInstance = TalkgroupNames()
        return TalkgroupNames.sharedInstance

    def __init__(self):
        self.names = {}
        self.loadedAt = None
        self.downloading = False
        self.lock = threading.Lock()
        self._loadFromDisk()

    def _cachePath(self):
        from owrx.config.core import CoreConfig

        return "{0}/talkgroups.json".format(CoreConfig().get_data_directory())

    def _loadFromDisk(self):
        try:
            path = self._cachePath()
            with open(path) as f:
                stored = json.load(f)
            names = stored.get("names") or {}
            when = datetime.fromtimestamp(stored.get("timestamp") or 0)
            if names:
                with self.lock:
                    self.names = {str(k): v for k, v in names.items()}
                    self.loadedAt = when
                logger.debug("loaded %d talkgroup names from %s", len(names), path)
        except FileNotFoundError:
            pass
        except Exception:
            logger.debug("could not read the cached talkgroup names; will download")

    def _saveToDisk(self, names):
        try:
            with open(self._cachePath(), "w") as f:
                json.dump({"timestamp": datetime.now().timestamp(), "names": names}, f)
        except Exception:
            # Not being able to cache it only means downloading it again later.
            logger.debug("could not cache the talkgroup names")

    def _stale(self):
        return self.loadedAt is None or self.loadedAt + TalkgroupNames.MAX_AGE < datetime.now()

    def _download(self):
        try:
            logger.debug("downloading the talkgroup names from %s", TalkgroupNames.URL)
            res = request.urlopen(TalkgroupNames.URL, timeout=30)
            if res.status != 200:
                logger.warning("talkgroup list returned error %i", res.status)
                return
            data = json.loads(res.read().decode("utf-8"))
            if not isinstance(data, dict) or not data:
                logger.warning("the talkgroup list was not the expected mapping")
                return
            names = {str(k): str(v) for k, v in data.items() if v}
            with self.lock:
                self.names = names
                self.loadedAt = datetime.now()
            logger.debug("got %d talkgroup names", len(names))
            self._saveToDisk(names)
        except Exception as e:
            logger.warning("could not download the talkgroup names: %s", str(e))
        finally:
            self.downloading = False

    def get(self, talkgroup):
        """The name for this talkgroup, or None. Never blocks."""
        try:
            key = str(int(talkgroup))
        except (TypeError, ValueError):
            return None
        with self.lock:
            name = self.names.get(key)
            stale = self._stale()
            busy = self.downloading
        if stale and not busy:
            self.downloading = True
            threading.Thread(target=self._download, daemon=True).start()
        return name


class DmrEnricher(DigihamEnricher, RadioIDEnricher):
    # callsign must be uppercase alphanumeric and at the beginning
    # if there's anything after the callsign, it must be separated by a whitespace
    talkerAliasRegex = re.compile("^([A-Z0-9]+)(\\s.*)?$")

    def __init__(self, parser):
        super().__init__("dmr", parser)

    def getCallsign(self, meta):
        # there's no explicit callsign data in dmr, so we can only rely on one of the following:
        # a) a callsign provided by a radioid lookup
        if "additional" in meta and "callsign" in meta["additional"]:
            return meta["additional"]["callsign"]
        # b) a callsign in the talker alias
        if "talkeralias" in meta:
            matches = DmrEnricher.talkerAliasRegex.match(meta["talkeralias"])
            if matches:
                return matches.group(1)

    def addTalkgroupName(self, meta):
        """Name the talkgroup of a group call, when it can be named."""
        try:
            if not Config.get()["digital_voice_dmr_talkgroup_lookup"]:
                return meta
            # Only a group call has a talkgroup: on a direct call "target" is
            # somebody's radio ID, and naming it from a talkgroup table would
            # be wrong rather than merely unhelpful.
            if meta.get("type") != "group" or "target" not in meta:
                return meta
            name = TalkgroupNames.getSharedInstance().get(meta["target"])
            if name:
                meta["target_name"] = name
        except Exception:
            logger.debug("could not name the talkgroup")
        return meta

    def enrich(self, meta, callback):
        def asyncParse(meta):
            self.parseCoordinate(meta, "DMR")
            self.addTalkgroupName(meta)
            callback(meta)
        meta = super().enrich(meta, asyncParse)
        meta = self.parseCoordinate(meta, "DMR")
        meta = self.addTalkgroupName(meta)
        return meta


class YsfMetaEnricher(DigihamEnricher):
    def getCallsign(self, meta):
        if "source" in meta:
            return meta["source"]

    def enrich(self, meta, callback):
        meta = self.parseCoordinate(meta, "YSF")
        return meta


class DStarEnricher(DigihamEnricher):
    def getCallsign(self, meta):
        if "ourcall" in meta:
            return meta["ourcall"]

    def enrich(self, meta, callback):
        meta = self.parseCoordinate(meta, "D-Star")
        meta = self.parseDprs(meta)
        return meta

    def parseDprs(self, meta):
        if "dprs" in meta:
            try:
                # we can send the DPRS stuff through our APRS parser to extract the information
                # TODO: only third-party parsing accepts this format right now
                parser = AprsParser()
                dprsData = parser.parseThirdpartyAprsData(meta["dprs"])
                if "data" in dprsData:
                    data = dprsData["data"]
                    if "lat" in data and "lon" in data:
                        # TODO: we could actually get the symbols from the parsed APRS data and show that on the meta panel
                        meta["lat"] = data["lat"]
                        meta["lon"] = data["lon"]

                        if "ourcall" in meta:
                            # send location info to map as well (it will show up with the correct symbol there!)
                            loc = AprsLocation(data)
                            Map.getSharedInstance().updateLocation(meta["ourcall"], loc, "DPRS", self.parser.getBand())
            except Exception:
                logger.exception("Error while parsing DPRS data")

        return meta


class MetaParser(PickleModule):
    def __init__(self):
        self.enrichers = {
            "DMR": DmrEnricher(self),
            "YSF": YsfMetaEnricher(self),
            "DSTAR": DStarEnricher(self),
            "NXDN": RadioIDEnricher("nxdn", self),
        }
        self.currentMetaData = None
        self.band = None
        super().__init__()

    def process(self, meta):
        self.currentMetaData = None
        if "protocol" in meta:
            protocol = meta["protocol"]
            if protocol in self.enrichers:
                self.currentMetaData = meta = self.enrichers[protocol].enrich(meta, self.receive)
        return meta

    def receive(self, meta):
        # we may have moved on in the meantime
        if meta is not self.currentMetaData:
            return
        self.writer.write(pickle.dumps(meta))

    def setDialFrequency(self, freq):
        self.band = Bandplan.getSharedInstance().findBand(freq)

    def getBand(self):
        return self.band
