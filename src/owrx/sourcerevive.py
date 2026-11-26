"""
Give a dead SDR another chance, once a minute.

openwebrx never retries a radio that would not start. `SdrSource.start()` is
called from exactly two places - the device's own constructor and `addClient`
- so a source that was not there at start-up stays dead for the whole life of
the process, and every client is told "no more SDR devices available" until
somebody restarts openwebrx.

That is a reasonable design when the radio is a USB stick in the same machine:
if it did not open, it is not going to open, and something is wrong that a
person should look at. It is the wrong design when the radio is on another
machine across a network, which is the arrangement this modification exists
for. There, "it did not open" usually means the other machine was rebooting,
or the wi-fi blinked at the wrong moment - a condition that cures itself in a
minute, with nobody to see it.

There are two ways a source can be dead, and the difference is the whole
reason this file needed a second attempt:

  * It is marked failed. `fail()` sets a flag, `start()` returns immediately
    while it is set, and nothing anywhere clears it again.

  * It is marked nothing at all. `start()` hands the process to a monitor
    thread, and when the process ends that thread calls `fail()` only if the
    source had reached the RUNNING state. A source that died on the way up
    never reached it, so the monitor clears itself and leaves the flag alone.
    The source is then neither failed nor available - which for an unattended
    radio is a silent death: `isFailed()` is False, so nothing ever looks at
    it again, and every client is still turned away.

So the question to ask once a minute is not "did it fail" but "should this be
running, and is it". For a device that is not always-on, "not running" is the
normal idle state and means nothing is wrong at all.

One more trap: `start()` begins with `if self.monitor: return`, which comes
*before* it looks at the failed flag. A source that failed while its connector
process was still alive therefore has a live monitor thread, and start() on it
does nothing whatsoever - it returns in a fraction of a second, having neither
started anything nor reported a problem. Such a source has to be stopped
first, which reaps the process and the thread, and only then started.

Starting the radio again is only half of it. openwebrx keeps a second, much
smaller list beside the devices it knows about: ActiveSdrSources, the ones a
client may actually be given. A device is dropped from that list the moment it
fails and is put back only when it is *enabled*, because nothing in openwebrx
expects a device to recover on its own. Leave it at that and a revived radio
runs beautifully while every client is still told "no more SDR devices
available" - which is worse than not reviving it at all, since the receiver
then looks healthy from the inside while serving nobody.

Re-admitting it is not a liberty: openwebrx decides what belongs on that list
with `isEnabled() and not isFailed()`, so the moment the failed flag is down
the device belongs there by openwebrx's own rule. Doing it *before* starting
the radio also keeps the books straight if the start fails, because the
handler that records a failure deletes the device from that list and throws
`KeyError` if it has already gone - an upstream fault that fires on the second
failure in a row, and one this ordering avoids entirely.

Nothing here restarts openwebrx and nothing disconnects a listener. A receiver
whose radio went away comes back on its own within a minute of it returning.
"""

import logging
import threading
import time

logger = logging.getLogger(__name__)

DEFAULT_INTERVAL = 60
MIN_INTERVAL = 10

# A connector that cannot reach its radio gives up in about a tenth of a
# second, and openwebrx counts a device as up the instant the process exists.
# Waiting a moment before believing it is the difference between a log that
# says what happened and a log that announces a recovery which already died.
GRACE = 2

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


def _readmit(source, name):
    """Put a device back on the list clients are served from."""
    try:
        from owrx.sdr import SourceStateHandler
    except Exception:
        logger.exception("could not import the handler that admits %s", name)
        return

    # The handler is registered as one of the device's own clients, which is
    # the only place it can be reached from here. onEnable() is openwebrx's
    # own way of saying "this device may be used again"; calling it rather
    # than writing to the list means every subscriber - the profile list, the
    # service scheduler - hears about it the way it expects to.
    for client in list(getattr(source, "clients", []) or []):
        if isinstance(client, SourceStateHandler):
            try:
                client.onEnable()
            except Exception:
                logger.exception("could not put %s back on the list", name)
            return
    logger.debug("%s has no state handler, so there is no list to put it on", name)


def _revive(source, listed=True):
    """Bring one source back, if it is down and ought not to be."""
    name = "unknown"
    try:
        name = source.getId()
    except Exception:
        pass

    try:
        if not source.isEnabled():
            return
        failed = source.isFailed()
        # isAvailable() is "the monitor thread exists", which is as close as
        # openwebrx comes to saying the device is actually up.
        available = source.isAvailable()
        always_on = source.isAlwaysOn()
    except Exception:
        logger.exception("could not read the state of %s", name)
        return

    if available and not failed:
        if not listed:
            logger.info(
                "%s is running but had fallen off the list clients are served "
                "from: putting it back", name
            )
            _readmit(source, name)
        return  # running, or on its way up

    if not failed and not always_on:
        return  # idle because nobody is listening: that is not a fault

    # A failed source still holding its process cannot be started: start()
    # returns at its first line while the monitor thread is alive. Reap it.
    if available:
        if getattr(source, "process", None) is None:
            # Caught between a dead process and a monitor that has not
            # finished clearing itself. It will be tidy in a moment.
            logger.debug(
                "%s is mid-handover; leaving it for the next round", name
            )
            return
        logger.info("%s failed but still holds its process: stopping it first", name)
        try:
            source.stop()
        except Exception:
            logger.exception("could not stop %s", name)
            return

    # There is no API for this: `fail()` sets the flag and nothing clears it.
    # Writing the attribute is the whole of the fix, and the alternative would
    # be diverting the large upstream module this lives in to add one setter.
    try:
        source.failed = False
    except Exception:
        logger.exception("could not clear the failed flag on %s", name)
        return

    # The flag is down, so by openwebrx's own rule the device belongs on the
    # list again - and if the start below fails, the handler that records the
    # failure needs to find it there.
    if not listed:
        _readmit(source, name)

    if not always_on:
        logger.debug(
            "%s is allowed to start again, and will as soon as a listener asks "
            "for it rather than now, when nobody has", name
        )
        return

    logger.info("%s is down: starting it again", name)
    try:
        source.start()
    except Exception:
        logger.exception("could not start %s", name)
        return

    time.sleep(GRACE)

    # Judge the result by isAvailable() after the grace period, not by the
    # failed flag: the flag was cleared by hand a moment ago, so it says
    # nothing, while isAvailable() is the monitor thread that this start either
    # created or did not. Reading the flag straight away is what made the first
    # version of this file announce a recovery that had not happened.
    try:
        if source.isAvailable() and not source.isFailed():
            logger.info("%s is back", name)
        else:
            logger.debug("%s did not come back this time; trying again in a minute", name)
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
            active = SdrService.getActiveSources()
        except Exception:
            logger.exception("could not list the sdr devices")
            continue
        for key, source in list(sources.items()):
            try:
                # Assume it is listed if the question cannot be answered: a
                # needless re-admission is a worse guess than none.
                try:
                    listed = key in active
                except Exception:
                    listed = True
                _revive(source, listed)
            except Exception:
                logger.exception("could not look after one of the sdr devices")


def start():
    """Begin watching for dead devices. Safe to call once, at start-up."""
    global _thread
    if _thread is not None:
        return
    if _interval() <= 0:
        logger.debug("not retrying dead sdr devices: switched off")
        return
    logger.debug("dead sdr devices will be retried every %d s", _interval())
    stop = threading.Event()
    _thread = threading.Thread(target=_loop, args=(stop,), daemon=True,
                               name="sdr-revive")
    _thread.start()
