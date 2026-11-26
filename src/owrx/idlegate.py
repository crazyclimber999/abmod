"""
Parks the receiver on the APRS frequency while nobody is listening.

The receiver has two jobs that want two different frequencies. A listener
wants it wherever they left it - whatever Save Defaults wrote into the
profile. The igate wants it on the packet frequency, because the packet
service only runs when a band plan entry for it falls inside the sampled
window; move the centre away and `updateServices` finds nothing to decode,
direwolf is never started and the gateway goes quiet. See the igate section of
docs/en/configuration.md.

Those two jobs never actually overlap. Nobody is listening at four in the
morning, which is exactly when the gateway could be working. So: when the last
listener leaves, wait, then park on the packet frequency. When a listener
arrives, go back to the default at once.

The waiting matters. A listener who reloads the page, or loses a train
connection for ten seconds, is gone and back inside a few seconds, and parking
in between would cost them a device restart each time.

Nothing here writes settings.json. A parked receiver that is restarted comes
back on its default, which is the right way round: the parking is a temporary
state, not a configuration. Note that retuning does write the live, in-memory
configuration - the property stack's top layer IS the profile object - so the
saved default has to be read back off disk. See `_default_frequency`.

What this costs: the gateway stops the moment anyone connects, including a
passing visitor, and it is their connection that decides it rather than the
operator's. On a busy public receiver that can mean the gateway rarely runs.
That is the deal, and it is off by default.

It also does nothing at all unless the igate itself is switched on. The
parking has no purpose of its own: it exists to feed the igate, so with the
igate off the clock is never even started and the receiver stays where the
operator left it.
"""

import logging
import threading

from owrx import autohf

logger = logging.getLogger(__name__)

# owrx.client, owrx.config and owrx.sdr are imported inside the functions.
# This module is imported at the top of connection.py, before connection.py
# imports those three itself, and a cycle there would not fail politely - it
# would take the whole receiver down at start-up. Nothing here runs often
# enough for the lookup in sys.modules to matter.

# The settings page clamps these; the module does too, because a value can
# also arrive from a hand-edited settings.json.
MIN_TIMEOUT_MIN = 1
MAX_TIMEOUT_MIN = 240

_lock = threading.RLock()
_timer = None
_parked = None          # the SdrSource currently parked, or None
_parked_default = None  # where to go back to, read when parking


def _setting(key, fallback=None):
    try:
        from owrx.config import Config

        config = Config.get()
        return config[key] if key in config else fallback
    except Exception:
        return fallback


def _enabled():
    return bool(_setting("aprs_idle_enabled", False))


def _igate_enabled():
    """
    Whether the igate is switched on.

    The parking exists to feed the igate and has no other purpose. With the
    igate off, moving the receiver away from its saved default buys nothing at
    all, so the clock is not even started: see `_arm`.
    """
    return bool(_setting("aprs_igate_enabled", False))


def _timeout_seconds():
    try:
        minutes = int(_setting("aprs_idle_timeout", 10))
    except (TypeError, ValueError):
        minutes = 10
    return max(MIN_TIMEOUT_MIN, min(MAX_TIMEOUT_MIN, minutes)) * 60


def _idle_frequency():
    try:
        freq = int(_setting("aprs_idle_freq", 0) or 0)
    except (TypeError, ValueError):
        return None
    return freq if freq > 0 else None


def _default_frequency(sdr):
    """
    The centre frequency Save Defaults wrote for the profile in use.

    Read from settings.json on disk, and deliberately not from `Config.get()`.

    The live configuration looks like the obvious place and is the wrong one.
    `sdr.props` is a stack whose top layer is the profile's own PropertyLayer -
    the very object that lives at config["sdrs"][id]["profiles"][pid] - so
    every retune, this module's parking included, writes straight through into
    the live configuration. Ask it what the default is and it answers with
    wherever the receiver happens to be pointing, which is how the first
    version of this came back from parking onto the parked frequency instead of
    the default.

    settings.json is only written by Save Defaults, which is exactly the
    operator's intent this needs to honour, and an operator who saves a new
    default while the receiver is parked gets that new one on the way back.
    """
    try:
        import json

        from owrx.config.core import CoreConfig

        path = "{0}/settings.json".format(CoreConfig().get_data_directory())
        with open(path, "r") as f:
            saved = json.load(f)
        profile = saved["sdrs"][sdr.getId()]["profiles"][sdr.getProfileId()]
        return int(profile["center_freq"])
    except Exception:
        logger.exception("could not read the profile's saved centre frequency")
        return None


def _current_frequency(sdr):
    """Where the radio is pointing right now."""
    try:
        props = sdr.props
        return int(props["center_freq"]) if "center_freq" in props else None
    except Exception:
        return None


def _runs_without_listeners(sdr):
    """
    Whether this device keeps running with nobody connected.

    Without `always-on` the source is stopped as soon as the last listener
    leaves - background services register as INACTIVE clients and do not start
    it - so parking it would move a frequency on a radio that is switched off
    and the gateway still would not run.
    """
    try:
        props = sdr.props
        return bool(props["always-on"]) if "always-on" in props else False
    except Exception:
        return False


def _tune(sdr, freq):
    """Centre the running device, direct sampling included."""
    sdr.props["center_freq"] = freq
    autohf.adjust(sdr, freq)


def _cancel_timer():
    global _timer
    cancelled = False
    with _lock:
        if _timer is not None:
            _timer.cancel()
            _timer = None
            cancelled = True
    if cancelled:
        # Said out loud because the silence used to be unreadable: a receiver
        # that never parks because visitors keep arriving looks exactly like a
        # receiver that never parks because something is broken.
        logger.debug("a listener arrived; the idle clock is cancelled")


def client_arrived():
    """
    A listener connected: cancel any pending parking and undo it.

    Called before the client picks its device and builds its configuration, so
    the frequency it is told about is already the restored one.
    """
    global _parked, _parked_default
    _cancel_timer()
    with _lock:
        if _parked is None:
            return

        sdr, back_to = _parked, _parked_default
        _parked = None
        _parked_default = None

    target = _default_frequency(sdr)
    if target is None:
        target = back_to
    if target is None:
        logger.warning("nothing to go back to; leaving the receiver where it is")
        return
    try:
        logger.info("listener back: returning to %.4f MHz", target / 1e6)
        _tune(sdr, target)
    except Exception:
        logger.exception("could not return the receiver to its default frequency")


def startup():
    """
    Arm the clock once at start-up.

    `client_gone` is otherwise the only thing that arms it, which would leave a
    freshly restarted receiver sitting on its default frequency until some
    visitor happened to connect and leave again. That is the wrong way round:
    the receiver nobody has visited since the last restart is exactly the one
    that should be gatewaying.
    """
    if not _enabled():
        return
    logger.debug("start-up: arming the idle clock")
    _arm()


def client_gone():
    """The last listener may have left: start the clock."""
    if not _enabled():
        return
    _arm()


def _arm():
    """Start the clock, unless somebody is listening or the igate is off."""
    global _timer
    if not _igate_enabled():
        logger.debug(
            "not arming the idle clock: the igate is off, so there is nothing "
            "to park for"
        )
        return
    try:
        from owrx.client import ClientRegistry

        listeners = ClientRegistry.getSharedInstance().clientCount()
        if listeners > 0:
            logger.debug(
                "not arming the idle clock: %d listener(s) still connected", listeners
            )
            return
    except Exception:
        logger.exception("could not count the clients; not parking")
        return

    seconds = _timeout_seconds()
    with _lock:
        if _timer is not None:
            _timer.cancel()
        _timer = threading.Timer(seconds, _park)
        _timer.daemon = True
        _timer.start()
    logger.debug("no listeners left; parking on the APRS frequency in %d s", seconds)


def _park():
    """The clock ran out. Park, unless something changed in the meantime."""
    global _timer, _parked, _parked_default
    with _lock:
        _timer = None
        if _parked is not None:
            return
    if not _enabled():
        return

    # Checked again here, not only when the clock started: the igate may have
    # been switched off while the clock ran, and then there is nothing to park
    # for any more.
    if not _igate_enabled():
        logger.info("not parking: the igate has been switched off")
        return

    freq = _idle_frequency()
    if freq is None:
        logger.warning("no idle frequency configured; not parking")
        return

    try:
        # The count is checked again here and not only when the clock started:
        # a listener who arrived during the wait cancels the timer, but a race
        # between that cancel and this call is possible, and parking under a
        # listener would restart the device under them.
        from owrx.client import ClientRegistry
        from owrx.sdr import SdrService

        if ClientRegistry.getSharedInstance().clientCount() > 0:
            logger.debug("a listener arrived while the clock ran; not parking")
            return
        sdr = SdrService.getFirstSource()
    except Exception:
        logger.exception("could not reach the sdr; not parking")
        return

    if sdr is None:
        return
    if not _runs_without_listeners(sdr):
        logger.info(
            "not parking on the APRS frequency: this device is not set to keep "
            "running at all times, so with nobody connected the radio is off "
            "and no service would run anyway"
        )
        return

    # Compared against where the radio is pointing NOW, not against the saved
    # default. A receiver whose saved default already is the APRS frequency -
    # the obvious setup for a station that mostly gates - still needs parking
    # after a visitor has moved the centre away and left, and comparing
    # against the default would skip exactly that case and leave the gateway
    # dead until the next restart.
    current = _current_frequency(sdr)
    if current is not None and current == freq:
        logger.debug("already on the APRS frequency; nothing to do")
        return

    default = _default_frequency(sdr)

    try:
        logger.info("no listeners: parking on %.4f MHz for APRS", freq / 1e6)
        _tune(sdr, freq)
    except Exception:
        logger.exception("could not park the receiver on the APRS frequency")
        return

    with _lock:
        _parked = sdr
        _parked_default = default
