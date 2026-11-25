"""
Terrain elevation data.

Whether a repeater can be heard is decided by what stands between it and the
receiver, so the importer needs to know the shape of the ground. The data is
SRTM, served as plain big-endian 16-bit integers: no authentication, and no
image library to install, which matters because the receiver has neither PIL
nor rasterio.

Tiles arrive at 1 arc-second (about 30 m) and are stored at 3 arc-seconds
(about 90 m). A ninety metre grid is far finer than a VHF path profile needs
and makes each tile 2.9 MB instead of 25.9 MB.
"""

from owrx.config.core import CoreConfig

from urllib.request import Request, urlopen

import gzip
import math
import os
import threading

import numpy as np

import logging

logger = logging.getLogger(__name__)

# SRTM served as gzipped .hgt, no account needed
TILE_URL = "https://elevation-tiles-prod.s3.amazonaws.com/skadi/{ns}{lat:02d}/{ns}{lat:02d}{ew}{lon:03d}.hgt.gz"
USER_AGENT = "OpenWebRX terrain fetcher"
DOWNLOAD_TIMEOUT = 180

# one arc-second in, three arc-seconds out
STORED_SIDE = 1201
VOID = -32768

# how many tiles stay in memory at once. Each is 2.9 MB, and the receiver has
# under a gigabyte of RAM, so this is deliberately modest.
CACHE_TILES = 24

# Beyond this the box is too big for its highest point to mean anything: a four
# character locator spans a degree, and its summit is unrelated to the station.
MAX_BOX_DEGREES = 0.15


class TerrainData(object):
    sharedInstance = None
    creationLock = threading.Lock()

    @staticmethod
    def getSharedInstance():
        with TerrainData.creationLock:
            if TerrainData.sharedInstance is None:
                TerrainData.sharedInstance = TerrainData()
        return TerrainData.sharedInstance

    def __init__(self):
        self.cache = {}
        self.order = []
        self.lock = threading.Lock()

    @staticmethod
    def directory():
        return "{0}/terrain".format(CoreConfig().get_data_directory())

    @staticmethod
    def tileName(lat, lon):
        ns = "N" if lat >= 0 else "S"
        ew = "E" if lon >= 0 else "W"
        return "{0}{1:02d}{2}{3:03d}".format(ns, abs(lat), ew, abs(lon))

    def tilePath(self, lat, lon):
        return "{0}/{1}.bin".format(TerrainData.directory(), TerrainData.tileName(lat, lon))

    def _load(self, lat, lon):
        key = (lat, lon)
        with self.lock:
            if key in self.cache:
                return self.cache[key]

        path = self.tilePath(lat, lon)
        tile = None
        try:
            raw = np.fromfile(path, dtype="<i2")
            if raw.size == STORED_SIDE * STORED_SIDE:
                tile = raw.reshape(STORED_SIDE, STORED_SIDE)
        except (FileNotFoundError, OSError):
            tile = None
        except Exception:
            logger.exception("error while reading terrain tile %s", path)
            tile = None

        with self.lock:
            self.cache[key] = tile
            self.order.append(key)
            while len(self.order) > CACHE_TILES:
                self.cache.pop(self.order.pop(0), None)
        return tile

    def elevation(self, lat, lon):
        """Ground height in metres, or None where there is no data."""
        tlat, tlon = int(math.floor(lat)), int(math.floor(lon))
        tile = self._load(tlat, tlon)
        if tile is None:
            return None
        row = int(round((tlat + 1 - lat) * (STORED_SIDE - 1)))
        col = int(round((lon - tlon) * (STORED_SIDE - 1)))
        if not (0 <= row < STORED_SIDE and 0 <= col < STORED_SIDE):
            return None
        value = int(tile[row, col])
        return None if value <= VOID + 1 else float(value)

    def elevations(self, lats, lons):
        """
        Ground height for many points at once.

        A path profile needs a hundred or more samples, and doing them one at a
        time costs more than the rest of the calculation put together. The
        points are grouped by the tile they fall in, so each tile is looked up
        once and indexed in bulk.
        """
        lats = np.asarray(lats, dtype=np.float64)
        lons = np.asarray(lons, dtype=np.float64)
        out = np.full(lats.shape, np.nan, dtype=np.float32)

        tlat = np.floor(lats).astype(np.int32)
        tlon = np.floor(lons).astype(np.int32)
        for key in set(zip(tlat.tolist(), tlon.tolist())):
            tile = self._load(key[0], key[1])
            if tile is None:
                continue
            which = (tlat == key[0]) & (tlon == key[1])
            rows = np.rint((key[0] + 1 - lats[which]) * (STORED_SIDE - 1)).astype(np.int32)
            cols = np.rint((lons[which] - key[1]) * (STORED_SIDE - 1)).astype(np.int32)
            np.clip(rows, 0, STORED_SIDE - 1, out=rows)
            np.clip(cols, 0, STORED_SIDE - 1, out=cols)
            values = tile[rows, cols].astype(np.float32)
            values[values <= VOID + 1] = np.nan
            out[which] = values
        return out

    def highestNearby(self, lat, lon, half_lat, half_lon):
        """
        The highest ground inside a box, used to place a repeater.

        A six character locator is a rectangle about five kilometres across,
        which is far too coarse to pick a point for a path profile. A repeater
        sits on high ground, so the top of its square is a much better guess
        than the middle of it: for the square holding the Resegone that is the
        difference between 1130 m and 1643 m, and the summit is where the
        antenna actually is.

        This only holds for a SMALL square. A four character locator covers one
        degree by two, and its highest point is whatever mountain happens to
        fall in it - for JN46 that is Monte Rosa at 3971 m, which says nothing
        about a repeater somewhere in the same hundred kilometres. The caller
        has to decide; see MAX_BOX_DEGREES.
        """
        tlat, tlon = int(math.floor(lat)), int(math.floor(lon))
        tile = self._load(tlat, tlon)
        if tile is None:
            return None

        def rows(value):
            return int(round((tlat + 1 - value) * (STORED_SIDE - 1)))

        def cols(value):
            return int(round((value - tlon) * (STORED_SIDE - 1)))

        r0, r1 = sorted((rows(lat + half_lat), rows(lat - half_lat)))
        c0, c1 = sorted((cols(lon - half_lon), cols(lon + half_lon)))
        r0, c0 = max(0, r0), max(0, c0)
        r1, c1 = min(STORED_SIDE - 1, r1), min(STORED_SIDE - 1, c1)
        if r1 < r0 or c1 < c0:
            return None

        block = tile[r0 : r1 + 1, c0 : c1 + 1]
        block = block[block > VOID + 1]
        if block.size == 0:
            return None
        return float(block.max())

    # ---------------------------------------------------------------- download

    @staticmethod
    def tilesFor(lat, lon, radius_km):
        """Every tile touching a circle of this radius."""
        dlat = radius_km / 111.0
        dlon = radius_km / (111.0 * max(0.1, math.cos(math.radians(lat))))
        out = []
        for la in range(int(math.floor(lat - dlat)), int(math.floor(lat + dlat)) + 1):
            for lo in range(int(math.floor(lon - dlon)), int(math.floor(lon + dlon)) + 1):
                out.append((la, lo))
        return out

    def missing(self, lat, lon, radius_km):
        return [t for t in TerrainData.tilesFor(lat, lon, radius_km) if not os.path.exists(self.tilePath(*t))]

    def fetchTile(self, lat, lon):
        """Downloads one tile and stores it reduced to three arc-seconds."""
        os.makedirs(TerrainData.directory(), exist_ok=True)
        path = self.tilePath(lat, lon)
        if os.path.exists(path):
            return True

        url = TILE_URL.format(
            ns="N" if lat >= 0 else "S", lat=abs(lat), ew="E" if lon >= 0 else "W", lon=abs(lon)
        )
        request = Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urlopen(request, timeout=DOWNLOAD_TIMEOUT) as response:
                payload = gzip.decompress(response.read())
        except Exception as e:
            # the sea has no tiles, and a 403 there is normal rather than a fault
            logger.info("no terrain tile for %s (%s)", TerrainData.tileName(lat, lon), e)
            return False

        side = int(round(math.sqrt(len(payload) / 2)))
        if side * side * 2 != len(payload):
            logger.warning("unexpected terrain tile size for %s", TerrainData.tileName(lat, lon))
            return False

        data = np.frombuffer(payload, dtype=">i2").reshape(side, side)
        if side != STORED_SIDE:
            step = (side - 1) // (STORED_SIDE - 1)
            data = data[::step, ::step][:STORED_SIDE, :STORED_SIDE]
        if data.shape != (STORED_SIDE, STORED_SIDE):
            logger.warning("could not reduce terrain tile %s", TerrainData.tileName(lat, lon))
            return False

        # written to a temporary name first, so an interrupted download never
        # leaves a half tile that reads as valid
        temporary = path + ".part"
        data.astype("<i2").tofile(temporary)
        os.replace(temporary, path)
        return True

    def download(self, lat, lon, radius_km, progress=None):
        wanted = TerrainData.tilesFor(lat, lon, radius_km)
        done, failed = 0, 0
        for index, (la, lo) in enumerate(wanted):
            if self.fetchTile(la, lo):
                done += 1
            else:
                failed += 1
            if progress is not None:
                progress(index + 1, len(wanted), done, failed)
        with self.lock:
            self.cache.clear()
            self.order.clear()
        return done, failed

    def status(self, lat, lon, radius_km):
        wanted = TerrainData.tilesFor(lat, lon, radius_km)
        have = [t for t in wanted if os.path.exists(self.tilePath(*t))]
        size = 0
        try:
            for name in os.listdir(TerrainData.directory()):
                if name.endswith(".bin"):
                    size += os.path.getsize("{0}/{1}".format(TerrainData.directory(), name))
        except FileNotFoundError:
            pass
        return {"wanted": len(wanted), "have": len(have), "bytes": size}
