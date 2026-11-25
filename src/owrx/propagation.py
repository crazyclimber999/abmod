"""
Whether a station can realistically be heard from this receiver.

The question the bookmark importer asks is not "is there line of sight" but
"how much signal is left". In VHF and UHF an obstacle does not cut a link off,
it attenuates it: a first attempt at this refused a repeater four kilometres
away across flat ground because the first Fresnel zone was not quite clear,
which is obviously wrong. So the result here is a margin in dB, not a verdict.

The model is the standard one for this job:

  * the ground profile is sampled along the great circle between the two ends
  * the earth is given an effective radius of 4/3 of the real one, which is the
    usual allowance for how the troposphere bends a radio wave downwards
  * obstacles are treated as knife edges, by Deygout's method: the worst
    obstruction is found, its loss computed from ITU-R P.526, and the two
    stretches either side of it examined the same way. Single knife edge alone
    is too kind to a path that crosses several ridges.
  * free space loss and the antenna's gain in that direction finish the budget

What it cannot know: buildings and trees, which SRTM only partly contains, and
the power of the far station, which no repeater list carries. The transmitter
power is therefore an assumption the operator sets, and the answer is only ever
an estimate.
"""

from owrx.terrain import MAX_BOX_DEGREES

import math

import numpy as np

import logging

logger = logging.getLogger(__name__)

EARTH_RADIUS = 6371000.0
# effective earth radius factor for standard atmospheric refraction
K_FACTOR = 4.0 / 3.0
LIGHT = 299792458.0

# samples along the path; 150 over 200 km is about one every 1.3 km, which is
# finer than the 90 m grid needs at that range and cheap once vectorised
PROFILE_SAMPLES = 150
# how deep Deygout's recursion goes. Three edges is the usual compromise.
MAX_EDGES = 3
# Deygout's method is known to over-predict when no single edge dominates: the
# knife edge formula never returns less than about 6 dB once an edge counts at
# all, so a nearly clear path that happens to graze three times collects 18 dB
# it does not deserve. Measured here: four kilometres of flat ground came out
# at 23 dB. The sub-paths are therefore only examined when the main edge is a
# real obstruction rather than a graze.
RECURSE_ABOVE_NU = 0.5


def locator_to_latlon(locator):
    """Maidenhead to decimal degrees, at the centre of the square."""
    locator = (locator or "").strip().upper()
    if len(locator) < 4:
        return None
    try:
        lon = (ord(locator[0]) - 65) * 20.0 - 180.0 + (ord(locator[2]) - 48) * 2.0
        lat = (ord(locator[1]) - 65) * 10.0 - 90.0 + (ord(locator[3]) - 48) * 1.0
    except (IndexError, TypeError):
        return None
    if len(locator) >= 6 and locator[4].isalpha() and locator[5].isalpha():
        lon += (ord(locator[4]) - 65) * (2.0 / 24.0) + (1.0 / 24.0)
        lat += (ord(locator[5]) - 65) * (1.0 / 24.0) + (0.5 / 24.0)
        half = (1.0 / 24.0, 0.5 / 24.0)
    else:
        lon += 1.0
        lat += 0.5
        half = (1.0, 0.5)
    if not (-180.0 <= lon <= 180.0 and -90.0 <= lat <= 90.0):
        return None
    return lat, lon, half[1], half[0]


def station_position(terrain, locator):
    """
    Where to put a station known only by its locator.

    Returns (lat, lon, ground_height, precise). A repeater stands on high
    ground, so for a six character square the highest point in it is a far
    better guess than the middle. For a four character square - a degree
    across - the highest point is some unrelated mountain, so the centre is
    used instead and `precise` says so.
    """
    parsed = locator_to_latlon(locator)
    if parsed is None:
        return None
    lat, lon, half_lat, half_lon = parsed

    precise = max(half_lat, half_lon) <= MAX_BOX_DEGREES
    ground = None
    if precise:
        ground = terrain.highestNearby(lat, lon, half_lat, half_lon)
    if ground is None:
        ground = terrain.elevation(lat, lon)
    if ground is None:
        return None
    return lat, lon, ground, precise


def distance_bearing(lat1, lon1, lat2, lon2):
    """Great circle distance in metres and bearing in degrees."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    dp = p2 - p1
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    distance = 2 * EARTH_RADIUS * math.asin(min(1.0, math.sqrt(a)))
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return distance, (math.degrees(math.atan2(y, x)) + 360.0) % 360.0


def _interpolate(lat1, lon1, lat2, lon2, fractions):
    """Points along the great circle, all at once."""
    p1, l1 = math.radians(lat1), math.radians(lon1)
    p2, l2 = math.radians(lat2), math.radians(lon2)
    d = 2 * math.asin(
        math.sqrt(
            math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin((l2 - l1) / 2) ** 2
        )
    )
    if d == 0:
        return np.full(len(fractions), lat1), np.full(len(fractions), lon1)
    f = np.asarray(fractions, dtype=np.float64)
    a = np.sin((1 - f) * d) / math.sin(d)
    b = np.sin(f * d) / math.sin(d)
    x = a * math.cos(p1) * math.cos(l1) + b * math.cos(p2) * math.cos(l2)
    y = a * math.cos(p1) * math.sin(l1) + b * math.cos(p2) * math.sin(l2)
    z = a * math.sin(p1) + b * math.sin(p2)
    return np.degrees(np.arctan2(z, np.hypot(x, y))), np.degrees(np.arctan2(y, x))


def horizon_distance(height_m):
    """How far the geometric horizon is for an antenna this high, in metres."""
    if height_m <= 0:
        return 0.0
    return math.sqrt(2.0 * K_FACTOR * EARTH_RADIUS * height_m)


def knife_edge_loss(nu):
    """ITU-R P.526 single knife edge, the classic approximation."""
    if nu < -0.78:
        return 0.0
    return 6.9 + 20.0 * math.log10(math.sqrt((nu - 0.1) ** 2 + 1.0) + nu - 0.1)


def free_space_loss(distance_m, frequency_hz):
    if distance_m < 1.0:
        return 0.0
    return 32.44 + 20.0 * math.log10(distance_m / 1000.0) + 20.0 * math.log10(frequency_hz / 1e6)


class AntennaPattern(object):
    """
    Gain by direction. With no pattern given the antenna is omnidirectional,
    which is what a vertical on a mast is, and what the operator gets if they
    leave the field empty.
    """

    def __init__(self, gain_dbi=2.0, pattern=None):
        self.gain = float(gain_dbi)
        self.pattern = None
        if pattern:
            values = []
            for part in str(pattern).replace(";", ",").split(","):
                part = part.strip()
                if not part:
                    continue
                try:
                    values.append(float(part))
                except ValueError:
                    continue
            if len(values) >= 2:
                self.pattern = values

    def isDirectional(self):
        return self.pattern is not None

    def gainAt(self, azimuth):
        if self.pattern is None:
            return self.gain
        # the values are read as evenly spaced around the full circle, so a
        # list of 36 is one every ten degrees and 8 is one every forty five
        n = len(self.pattern)
        position = (azimuth % 360.0) / 360.0 * n
        low = int(math.floor(position)) % n
        high = (low + 1) % n
        weight = position - math.floor(position)
        relative = self.pattern[low] * (1 - weight) + self.pattern[high] * weight
        return self.gain + relative


class PropagationModel(object):
    """
    One receiver, many far stations.

    Built once per import run: the receiver's position, antenna and the
    assumptions about the other end do not change between rows.
    """

    def __init__(
        self,
        terrain,
        rx_lat,
        rx_lon,
        rx_height=10.0,
        antenna=None,
        remote_height=20.0,
        remote_erp_dbm=40.0,
        sensitivity_dbm=-116.0,
    ):
        self.terrain = terrain
        self.rx_lat = float(rx_lat)
        self.rx_lon = float(rx_lon)
        self.rx_height = float(rx_height)
        self.antenna = antenna or AntennaPattern()
        self.remote_height = float(remote_height)
        self.remote_erp = float(remote_erp_dbm)
        self.sensitivity = float(sensitivity_dbm)

        self.rx_ground = self.terrain.elevation(self.rx_lat, self.rx_lon)
        self._fractions = np.linspace(0.0, 1.0, PROFILE_SAMPLES + 2)[1:-1]

    def hasTerrain(self):
        return self.rx_ground is not None

    def _diffraction(self, heights, distances, total, wavelength, tx_alt, rx_alt, depth=0):
        """
        Deygout: the worst edge, then the stretches either side of it.

        A single knife edge is far too kind to a path that crosses more than
        one ridge, which in the Alps is most of them.
        """
        if depth >= MAX_EDGES or len(heights) == 0:
            return 0.0

        d1 = distances
        d2 = total - distances
        valid = (d1 > 1.0) & (d2 > 1.0) & np.isfinite(heights)
        if not np.any(valid):
            return 0.0

        bulge = (d1 * d2) / (2.0 * K_FACTOR * EARTH_RADIUS)
        ray = tx_alt + (rx_alt - tx_alt) * (d1 / total)
        # positive where the ground pokes above the direct ray
        clearance = (heights + bulge) - ray
        nu = clearance * np.sqrt(2.0 / wavelength * (1.0 / d1 + 1.0 / d2))
        nu = np.where(valid, nu, -9.0)

        index = int(np.argmax(nu))
        peak = float(nu[index])
        if peak <= -0.78:
            return 0.0

        loss = knife_edge_loss(peak)
        if peak <= RECURSE_ABOVE_NU:
            return loss

        edge_alt = float(heights[index] + bulge[index])
        edge_d = float(d1[index])

        before = slice(0, index)
        after = slice(index + 1, len(heights))
        if index > 0:
            loss += self._diffraction(
                heights[before], distances[before], edge_d, wavelength, tx_alt, edge_alt, depth + 1
            )
        if index < len(heights) - 1:
            loss += self._diffraction(
                heights[after], distances[after] - edge_d, total - edge_d, wavelength,
                edge_alt, rx_alt, depth + 1,
            )
        return loss

    def evaluate(self, lat, lon, frequency_hz, remote_ground=None, remote_height=None):
        """
        The budget to one station. Returns None when terrain data is missing.
        """
        distance, bearing = distance_bearing(self.rx_lat, self.rx_lon, lat, lon)
        if distance < 1.0:
            return None
        if self.rx_ground is None:
            return None
        if remote_ground is None:
            remote_ground = self.terrain.elevation(lat, lon)
        if remote_ground is None:
            return None

        height = self.remote_height if remote_height is None else float(remote_height)
        tx_alt = self.rx_ground + self.rx_height
        rx_alt = remote_ground + height
        wavelength = LIGHT / frequency_hz

        lats, lons = _interpolate(self.rx_lat, self.rx_lon, lat, lon, self._fractions)
        heights = self.terrain.elevations(lats, lons)
        distances = self._fractions * distance

        usable = np.isfinite(heights)
        diffraction = 0.0
        if np.any(usable):
            diffraction = self._diffraction(
                heights[usable].astype(np.float64),
                distances[usable],
                distance,
                wavelength,
                tx_alt,
                rx_alt,
            )

        fspl = free_space_loss(distance, frequency_hz)
        gain = self.antenna.gainAt(bearing)
        received = self.remote_erp - fspl - diffraction + gain
        margin = received - self.sensitivity

        # Beyond the radio horizon this model stops being meaningful. A knife
        # edge is a sharp obstruction and its loss grows only slowly with
        # distance, while the real obstruction out there is the curve of the
        # earth itself, which diffracts far worse: left alone the model called
        # a repeater 270 km away in Tuscany receivable. What happens past the
        # horizon is tropospheric ducting and lift - a matter of the weather,
        # not of the ground - so it is reported as beyond prediction rather
        # than guessed at.
        #
        # Each end's horizon is measured from its height above the LOWEST
        # ground along the path, so a repeater on a summit gets the long
        # horizon it deserves instead of the few kilometres its mast alone
        # would give.
        floor = float(np.nanmin(heights)) if np.any(usable) else min(self.rx_ground, remote_ground)
        reach = horizon_distance(max(1.0, tx_alt - floor)) + horizon_distance(max(1.0, rx_alt - floor))
        beyond = distance > reach

        return {
            "distance_km": round(distance / 1000.0, 1),
            "bearing": round(bearing),
            "free_space_db": round(fspl, 1),
            "diffraction_db": round(diffraction, 1),
            "antenna_gain_db": round(gain, 1),
            "margin_db": round(margin, 1),
            "horizon_km": round(reach / 1000.0, 1),
            "beyond_horizon": bool(beyond),
            "quality": "beyond_horizon" if beyond else PropagationModel.quality(margin),
        }

    @staticmethod
    def quality(margin_db):
        if margin_db >= 20:
            return "strong"
        if margin_db >= 6:
            return "workable"
        if margin_db >= 0:
            return "marginal"
        return "unlikely"
