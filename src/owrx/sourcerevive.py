"""
Give a failed SDR another chance, once a minute.

openwebrx marks a source that would not start as failed and then never tries
it again: `SdrSource.start()` begins with `if self.isFailed(): return`, and
nothing anywhere sets that flag back to False. `start()` is called from
exactly two places - the device's own constructor, and `addClient` - so a
source that failed at start-up stays dead for the whole life of the process,
and every client is told "no more SDR devices available" until somebody
restarts openwebrx.

That is a reasonable design when the radio is a USB stick in the same
machine: if it did not open, it is not going to open, and something is wrong
that a person should look at. It is the wrong design when the radio is on
another machine across a network, which is the arrangement this modification
exists for. There, "it did not open" usually means the other machine was
rebooting, or the wi-fi blinked at the wrong moment - a condition that cures
itself in a minute, with nobody to see it.

So: once a minute, clear the flag on any failed source and, if the device is
meant to run unattended, start it again. If the radio is still unreachable it
fails once more, the log gains one line, and we try again a minute later.
Nothing is restarted, no listener is disconnected, and a receiver whose
dongle went away comes back on its own within a minute of it returning.

A device that is not always-on gets its flag cleared but is not started: with
no listeners there is nothing to run for, and the next client to arrive will
start it through the path openwebrx already has.
"""

import logging
import threading

logger = logging.getLogger(__name__)

DEFAULT_INTERVAL = 60
MIN_INTERVAL = 10

_thread = None


def _setting(key, fallback):
    try:
        from owrx.config import Config

        config = Config.get()
        return config[key] if key in config else fallback
    except Exception:
        return fallback


def _interval():
    try:
        seconds = int(_setting("sdr_retry_interval", DEFAULT_INTERVAL))
    except (TypeError, ValueError):
        return DEFAULT_INTERVAL
    if seconds <= 0:
        return 0  # switched off
    return max(MIN_INTERVAL, seconds)


def _revive(source):
    """Clear the failed flag and, where it makes sense, start the device."""
    name = "unknown"
    try:
        name = source.getId()
    except Exception:
        pass

    try:
        if not source.isFailed():
            return
        if not source.isEnabled():
            return
    except Exception:
        return

    # There is no API for this: `fail()` sets the flag and nothing clears it.
    # Writing the attribute is the whole of the fix, and the alternative would
    # be diverting the large upstream module this lives in to add one setter.
    try:
        source.failed = False
    except Exception:
        logger.exception("could not clear the failed flag on %s", name)
        return

    try:
        always_on = source.isAlwaysOn()
    except Exception:
        always_on = False

    if not always_on:
        logger.debug(
            "%s was failed and is now allowed to start again; waiting for a "
            "listener rather than starting a device nobody asked for", name
        )
        return

    logger.info("%s had failed: trying it again", name)
    try:
        source.start()
    except Exception:
        logger.exception("could not restart %s", name)
        return

    try:
        if source.isFailed():
            logger.debug("%s did not come back this time; trying again later", name)
        else:
            logger.info("%s is back", name)
    except Exception:
        pass


def _loop(stop: threading.Event):
    while True:
        seconds = _interval()
        if seconds <= 0:
            # Switched off in the configuration; look again in a minute in
            # case it is switched back on without a restart.
            if stop.wait(DEFAULT_INTERVAL):
                return
            continue
        if stop.wait(seconds):
            return
        try:
            from owrx.sdr import SdrService

            sources = SdrService.getAllSources()
        except Exception:
            logger.exception("could not list the sdr devices")
            continue
        for source in list(sources.values()):
            _revive(source)


def start():
    """Begin watching for failed devices. Safe to call once, at start-up."""
    global _thread
    if _thread is not None:
        return
    if _interval() <= 0:
        logger.debug("not retrying failed sdr devices: switched off")
        return
    logger.debug("failed sdr devices will be retried every %d s", _interval())
    stop = threading.Event()
    _thread = threading.Thread(target=_loop, args=(stop,), daemon=True,
                               name="sdr-revive")
    _thread.start()
