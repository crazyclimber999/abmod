from owrx.controllers.template import WebpageController
from owrx.controllers.admin import AdminAuthorizationMixin
from owrx.controllers.settings import SettingsBreadcrumb
from owrx.controllers import BodySizeError
from owrx.bookmarks import Bookmark, Bookmarks
from owrx.modes import Modes
from owrx.breadcrumb import Breadcrumb, BreadcrumbItem, BreadcrumbMixin
from owrx.config import Config
from owrx.terrain import TerrainData
from owrx.propagation import (
    PropagationModel,
    AntennaPattern,
    station_position,
    locator_to_latlon,
)
from owrx import bookmarkimport

import json
import threading

import logging

logger = logging.getLogger(__name__)


class BookmarkImportController(AdminAuthorizationMixin, BreadcrumbMixin, WebpageController):
    """
    Importing a repeater list into the bookmarks.

    The server only fetches or receives the file, turns it into a table and
    later stores what the operator confirmed. Everything in between - which
    column is the frequency, which regions to take, how the source names its
    modulations - happens in the browser, so no half-finished import has to be
    kept on the receiver between requests.
    """

    # the same ceiling the fetcher uses, applied to hand-uploaded files
    MAX_UPLOAD = bookmarkimport.MAX_BYTES

    def get_breadcrumb(self) -> Breadcrumb:
        return (
            SettingsBreadcrumb()
            .append(BreadcrumbItem("Bookmark editor", "settings/bookmarks"))
            .append(BreadcrumbItem("Import", "settings/bookmarkimport"))
        )

    def _storedSetup(self):
        """
        The remembered import setup, or the built-in starting point.

        Anything stored that is unreadable falls back to the defaults rather
        than leaving the page with nothing preselected. The two older keys are
        still read, so a mapping saved before the whole page became storable
        is not lost.
        """
        setup = dict(bookmarkimport.DEFAULT_IMPORT_SETUP)
        setup["modmap"] = dict(bookmarkimport.DEFAULT_MODULATION_MAP)
        config = Config.get()

        raw = config["bookmark_import_setup"] if "bookmark_import_setup" in config else ""
        if raw:
            try:
                stored = json.loads(raw)
                if isinstance(stored, dict):
                    setup.update(stored)
            except Exception:
                logger.exception("stored bookmark import setup is unreadable; using the default")
        else:
            # superseded by the key above, read so an older saved mapping survives
            legacy = config["bookmark_import_modmap"] if "bookmark_import_modmap" in config else ""
            if legacy:
                try:
                    stored = json.loads(legacy)
                    if isinstance(stored, dict):
                        setup["modmap"] = stored
                except Exception:
                    logger.exception("stored bookmark import mapping is unreadable; using the default")
            if "bookmark_import_fallback" in config and config["bookmark_import_fallback"]:
                setup["fallback"] = config["bookmark_import_fallback"]

        setup["modmap"] = {
            bookmarkimport.normalise_key(k): str(v) for k, v in (setup.get("modmap") or {}).items()
        }
        return setup

    def template_variables(self):
        variables = super().template_variables()
        available = {m.modulation: m.name for m in Modes.getAvailableModes()}
        everything = {m.modulation: m.name for m in Modes.getModes()}

        variables["modes"] = json.dumps(available)
        # shown in the dropdown but not selectable, so it is obvious why DMR
        # cannot be picked rather than looking like an omission
        variables["unavailable_modes"] = json.dumps(
            {k: v for k, v in everything.items() if k not in available}
        )
        setup = self._storedSetup()
        variables["modmap"] = json.dumps(setup["modmap"])
        variables["fallback"] = setup["fallback"]
        variables["importsetup"] = json.dumps(setup)
        return variables

    def indexAction(self):
        self.serve_template("settings/bookmarkimport.html", **self.template_variables())

    def _json(self, obj, code=200):
        self.send_response(json.dumps(obj), code=code, content_type="application/json")

    def parseAction(self):
        """Fetches or receives a spreadsheet and returns it as a table."""
        try:
            filename = None
            if "url" in self.request.query:
                url = self.request.query["url"][0]
                data = bookmarkimport.fetch(url)
                filename = url
            else:
                if "filename" in self.request.query:
                    filename = self.request.query["filename"][0]
                try:
                    data = self.get_body(BookmarkImportController.MAX_UPLOAD)
                except BodySizeError:
                    self._json({"error": "The file is too large"}, code=400)
                    return
                if not data:
                    self._json({"error": "No file received"}, code=400)
                    return

            rows, sheets, sheet = bookmarkimport.parse(data, filename)
        except bookmarkimport.ImportError_ as e:
            self._json({"error": str(e)}, code=400)
            return
        except Exception as e:
            logger.exception("error while reading an imported spreadsheet")
            self._json({"error": "Could not read the file: {0}".format(e)}, code=400)
            return

        if not rows:
            self._json({"error": "The file has no rows"}, code=400)
            return

        width = max(len(r) for r in rows)
        self._json(
            {
                "columns": [
                    {"index": i, "label": bookmarkimport.column_label(i)} for i in range(width)
                ],
                "rows": [r + [""] * (width - len(r)) for r in rows],
                "sheets": sheets,
                "sheet": sheet,
            }
        )

    def applyAction(self):
        """Stores the bookmarks the operator confirmed in the browser."""
        try:
            body = self.get_body(BookmarkImportController.MAX_UPLOAD)
            payload = json.loads(body.decode("utf-8"))
        except Exception:
            self._json({"error": "Could not read the request"}, code=400)
            return

        incoming = payload.get("bookmarks")
        if not isinstance(incoming, list) or not incoming:
            self._json({"error": "Nothing to import"}, code=400)
            return
        # "replace" throws away what is stored; the default only adds
        replace = payload.get("replace") is True

        known = {m.modulation for m in Modes.getAvailableModes()}
        prepared = []
        skipped = 0
        for entry in incoming:
            try:
                name = str(entry["name"]).strip()[:120]
                frequency = int(round(float(entry["frequency"])))
                modulation = str(entry["modulation"]).strip()
            except (KeyError, TypeError, ValueError):
                skipped += 1
                continue
            # a bookmark the receiver cannot tune or demodulate is worse than
            # no bookmark at all, so it is dropped rather than stored broken
            if not name or frequency <= 0 or modulation not in known:
                skipped += 1
                continue
            prepared.append(Bookmark({"name": name, "frequency": frequency, "modulation": modulation}))

        if not prepared:
            self._json({"error": "No usable rows: check the column mapping", "skipped": skipped}, code=400)
            return

        bookmarks = Bookmarks.getSharedInstance()
        existing = [] if replace else list(bookmarks.getBookmarks())

        # Re-importing an updated list must not duplicate what is already
        # stored, so an entry that matches one already there is left alone.
        #
        # The name is PART of that identity, and leaving it out was a bad bug:
        # a national repeater list reuses the same channel all over the
        # country - 24 different repeaters share 145.750 MHz in the Italian
        # one - so keying on frequency and modulation alone collapsed 1031
        # rows into 252 bookmarks, each keeping whichever name happened to be
        # processed last. Milan would be overwritten by Florence.
        def identity(bookmark):
            return (bookmark.getName().strip().lower(), bookmark.getFrequency(), bookmark.getModulation())

        index = {identity(b): b for b in existing}

        # When a frequency is already bookmarked by something with a different
        # name, the two are different stations and by default they coexist.
        # With this on, the imported one takes the other's place instead: the
        # operator wants one bookmark per channel, not two tags on top of each
        # other on the frequency scale.
        #
        # Only what was already stored can be displaced - the rows arriving in
        # this run keep their own identity, so two repeaters sharing a channel
        # still both arrive if the operator asked for that.
        # Matched on the FREQUENCY ALONE, whatever modulation each carries.
        # Keying it on frequency and modulation together looked tidier and was
        # wrong twice over: the switch says "when a frequency is already
        # bookmarked", and a receiver can only be tuned to one thing at a time
        # anyway - two bookmarks on one frequency are two tags on top of each
        # other on the scale, whether or not they claim different modes.
        replace_on_frequency = payload.get("replaceOnFrequency") is True
        by_frequency = {}
        if replace_on_frequency:
            for b in existing:
                by_frequency.setdefault(b.getFrequency(), []).append(b)

        added = 0
        updated = 0
        replaced = 0
        for bookmark in prepared:
            key = identity(bookmark)
            if key in index:
                updated += 1
                continue
            if replace_on_frequency:
                displaced = by_frequency.pop(bookmark.getFrequency(), None)
                for old_bookmark in displaced or []:
                    try:
                        existing.remove(old_bookmark)
                        index.pop(identity(old_bookmark), None)
                        replaced += 1
                    except ValueError:
                        pass
            existing.append(bookmark)
            index[key] = bookmark
            added += 1

        bookmarks.bookmarks = existing
        bookmarks.store()

        self._json({
            "added": added,
            "updated": updated,
            "replaced": replaced,
            "skipped": skipped,
            "total": len(existing),
        })

    # how far the stored setup is allowed to go, so a malformed or hostile
    # payload cannot grow the config file without bound
    MAX_REGIONS = 500
    MAX_MODMAP = 500
    MAX_URL = 2048

    def defaultsAction(self):
        """Remembers the whole import setup for next time."""
        try:
            body = self.get_body(BookmarkImportController.MAX_UPLOAD)
            payload = json.loads(body.decode("utf-8"))
        except Exception:
            self._json({"error": "Could not read the request"}, code=400)
            return
        if not isinstance(payload, dict):
            self._json({"error": "Nothing to save"}, code=400)
            return

        known = {m.modulation for m in Modes.getAvailableModes()}
        setup = {}

        url = str(payload.get("url") or "").strip()
        if url:
            # the fetcher refuses anything else anyway; refusing it here as
            # well means a bad URL is never stored in the first place
            if not (url.startswith("http://") or url.startswith("https://")):
                self._json({"error": "Only http and https URLs can be stored"}, code=400)
                return
            setup["url"] = url[: BookmarkImportController.MAX_URL]

        try:
            setup["headerRow"] = max(0, int(payload.get("headerRow", 0)))
        except (TypeError, ValueError):
            setup["headerRow"] = 0

        fields = payload.get("fields")
        if isinstance(fields, dict):
            cleaned = {}
            for name in ("name1", "name2", "frequency", "modulation", "region", "locator"):
                if name in fields:
                    try:
                        cleaned[name] = int(fields[name])
                    except (TypeError, ValueError):
                        continue
            for name in ("separator", "unit"):
                if name in fields:
                    cleaned[name] = str(fields[name])[:16]
            setup["fields"] = cleaned

        extras = payload.get("extras")
        if isinstance(extras, list):
            out = []
            for value in extras:
                try:
                    out.append(int(value))
                except (TypeError, ValueError):
                    continue
            setup["extras"] = out

        regions = payload.get("regions")
        if isinstance(regions, list):
            setup["regions"] = [str(r)[:200] for r in regions][: BookmarkImportController.MAX_REGIONS]

        mapping = payload.get("modmap")
        if isinstance(mapping, dict):
            cleaned = {}
            for source, target in list(mapping.items())[: BookmarkImportController.MAX_MODMAP]:
                target = str(target)
                # an empty target means "use the fallback", which is a real
                # choice; anything else must be a mode this receiver has, or
                # the marker for leaving the rows out. Storing a mode that does
                # not exist would silently drop all of its rows at import time.
                if target and target != bookmarkimport.SKIP and target not in known:
                    continue
                cleaned[bookmarkimport.normalise_key(source)] = target
            setup["modmap"] = cleaned

        fallback = str(payload.get("fallback") or "")
        setup["fallback"] = fallback if fallback in known else bookmarkimport.DEFAULT_FALLBACK

        reach = payload.get("reach")
        if isinstance(reach, dict):
            cleaned = {}
            for name, lo, hi in (("margin", -200.0, 200.0), ("distance", 1.0, 5000.0)):
                if name in reach:
                    try:
                        cleaned[name] = max(lo, min(hi, float(reach[name])))
                    except (TypeError, ValueError):
                        continue
            cleaned["horizon"] = reach.get("horizon") is True
            cleaned["nearest"] = reach.get("nearest") is True
            setup["reach"] = cleaned

        config = Config.get()
        config["bookmark_import_setup"] = json.dumps(setup)
        # the two older keys are superseded; clearing them keeps one source of
        # truth instead of two that can disagree
        config["bookmark_import_modmap"] = ""
        config["bookmark_import_fallback"] = ""
        Config.get().store()

        self._json({
            "saved": len(setup.get("modmap", {})),
            "regions": len(setup.get("regions", [])),
            "fallback": setup["fallback"],
            "url": setup.get("url", ""),
        })

    def resetDefaultsAction(self):
        config = Config.get()
        config["bookmark_import_setup"] = ""
        config["bookmark_import_modmap"] = ""
        config["bookmark_import_fallback"] = ""
        Config.get().store()
        self._json(self._storedSetup())

    MAX_PROPAGATION_ENTRIES = 5000

    def _propagationModel(self):
        """Builds the model from the receiver's own settings, or None."""
        config = Config.get()

        def number(key, fallback):
            try:
                return float(config[key]) if key in config else fallback
            except (TypeError, ValueError):
                return fallback

        if "receiver_gps" not in config:
            return None, "The receiver location is not set under Receiver details."
        gps = config["receiver_gps"]
        try:
            lat, lon = float(gps["lat"]), float(gps["lon"])
        except (KeyError, TypeError, ValueError):
            return None, "The receiver location is not usable."

        terrain = TerrainData.getSharedInstance()
        if terrain.elevation(lat, lon) is None:
            return None, (
                "No elevation data for the receiver's own position. "
                "Download it before using this filter."
            )

        pattern = config["receiver_antenna_pattern"] if "receiver_antenna_pattern" in config else ""
        antenna = AntennaPattern(number("receiver_antenna_gain", 2.0), pattern)

        model = PropagationModel(
            terrain,
            lat,
            lon,
            rx_height=number("receiver_antenna_height", 10.0),
            antenna=antenna,
            remote_height=number("propagation_remote_height", 20.0),
            remote_erp_dbm=number("propagation_remote_erp", 40.0),
            sensitivity_dbm=number("propagation_sensitivity", -116.0),
        )
        return model, None

    def propagationAction(self):
        """
        Works out, for each row, how much signal would be left.

        The browser sends only what it has - a locator and a frequency - and
        gets back a margin in dB. The terrain data and the receiver's own
        antenna never leave the server.
        """
        try:
            body = self.get_body(BookmarkImportController.MAX_UPLOAD)
            payload = json.loads(body.decode("utf-8"))
            entries = payload.get("entries")
        except Exception:
            self._json({"error": "Could not read the request"}, code=400)
            return
        if not isinstance(entries, list):
            self._json({"error": "Nothing to work out"}, code=400)
            return

        model, problem = self._propagationModel()
        if model is None:
            self._json({"error": problem}, code=400)
            return

        terrain = TerrainData.getSharedInstance()
        results = []
        # the same locator appears dozens of times in a repeater list, once per
        # channel on the same site, and the path profile does not depend on the
        # frequency until the very last step
        places = {}

        for entry in entries[: BookmarkImportController.MAX_PROPAGATION_ENTRIES]:
            locator = str((entry or {}).get("locator") or "").strip()
            try:
                frequency = float((entry or {}).get("frequency") or 0)
            except (TypeError, ValueError):
                frequency = 0.0

            if not locator or frequency <= 0:
                results.append({"status": "no_locator"})
                continue
            if locator_to_latlon(locator) is None:
                results.append({"status": "no_locator"})
                continue

            if locator not in places:
                places[locator] = station_position(terrain, locator)
            place = places[locator]
            if place is None:
                results.append({"status": "no_terrain"})
                continue

            lat, lon, ground, precise = place
            outcome = model.evaluate(lat, lon, frequency, remote_ground=ground)
            if outcome is None:
                results.append({"status": "no_terrain"})
                continue
            outcome["status"] = "ok"
            outcome["precise"] = precise
            results.append(outcome)

        self._json({"results": results})

    def terrainAction(self):
        """How much elevation data is in place, and fetches what is missing."""
        config = Config.get()
        try:
            gps = config["receiver_gps"]
            lat, lon = float(gps["lat"]), float(gps["lon"])
        except Exception:
            self._json({"error": "The receiver location is not set."}, code=400)
            return
        try:
            radius = float(config["terrain_radius_km"]) if "terrain_radius_km" in config else 200.0
        except (TypeError, ValueError):
            radius = 200.0

        terrain = TerrainData.getSharedInstance()
        action = ""
        try:
            body = self.get_body(BookmarkImportController.MAX_UPLOAD)
            if body:
                action = json.loads(body.decode("utf-8")).get("action", "")
        except Exception:
            action = ""

        if action == "download":
            missing = terrain.missing(lat, lon, radius)
            if missing:
                # a few hundred megabytes, so it runs in its own thread and the
                # page asks again rather than holding the request open
                threading.Thread(
                    target=terrain.download,
                    args=(lat, lon, radius),
                    daemon=True,
                    name="terrain_download",
                ).start()

        status = terrain.status(lat, lon, radius)
        status["radius_km"] = radius
        self._json(status)

    def sampleAction(self):
        self.send_response(
            bookmarkimport.SAMPLE_CSV,
            content_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="bookmark-import-example.csv"'},
        )
