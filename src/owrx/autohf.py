"""
Switches the RTL-SDR into direct sampling when the receiver is tuned below the
tuner's reach, and back out again when it returns.

An R820T cannot tune below roughly 24 MHz. Below that the only way in is the
ADC's own input - direct sampling - which on an RTL-SDR v3 is wired to the Q
branch. Measured on this hardware with rtl_connector: at 6 and 7 MHz with
direct sampling on, discrete lines stand 29 dB above the noise floor, which a
disconnected input does not produce.

The awkward part is that direct sampling is not a tunable parameter. It is a
command line option of the connector:

    .setMappings({"bias_tee": Flag("-b"), "direct_sampling": Option("-e")})

while the frequency travels live over the control socket. ConnectorSource's
onPropertyChange sends every change down that socket and never restarts, so
setting the property alone changes nothing: the connector was started with the
old value and keeps it. Switching profiles does not help either - it changes
properties the same way, and SdrSource has no restart of its own.

So the radio has to be stopped and started, and every listener loses a few
seconds of audio. That is not a cost worth paying silently, which is why it is
announced in the receiver's log.
"""

import logging
import threading

logger = logging.getLogger(__name__)

# Where the R820T gives up. Datasheets say 24 MHz; the last couple of MHz are
# poor anyway, so the switch happens a little above it rather than at the cliff.
TUNER_FLOOR_HZ = 24000000

# The Q branch. 1 is the I branch, which almost no board wires up.
DIRECT_SAMPLING_Q = 2
DIRECT_SAMPLING_OFF = 0

# One switch at a time, and never while another is half done: a stop() racing a
# start() leaves the source in a state nothing recovers from without a restart
# of the whole service.
_lock = threading.Lock()


def required_mode(center_freq, samp_rate=0):
    """
    Which direct sampling setting this centre frequency needs.

    The decision is made on the TOP of the sampled window, not on its centre: a
    window centred at 23 MHz reaches up to 24.25 MHz, and the tuner can serve
    all of it. Deciding on the centre alone would switch to direct sampling for
    a window the tuner could have covered, which is worse - direct sampling has
    no filtering in front of it and everything strong folds in.
    """
    try:
        top = int(center_freq) + int(samp_rate or 0) // 2
    except (TypeError, ValueError):
        return None
    return DIRECT_SAMPLING_OFF if top > TUNER_FLOOR_HZ else DIRECT_SAMPLING_Q


def current_mode(sdr):
    try:
        value = sdr.props["direct_sampling"]
    except (KeyError, TypeError):
        return DIRECT_SAMPLING_OFF
    try:
        return int(value)
    except (TypeError, ValueError):
        return DIRECT_SAMPLING_OFF


def supports_switching(sdr):
    """Only the plain rtl_sdr connector takes -e. Anything else is left alone."""
    try:
        return sdr.props["type"] in ("rtl_sdr", "rtl_sdr_soapy", "rtl_tcp")
    except (KeyError, TypeError):
        return False


def adjust(sdr, center_freq, announce=None):
    """
    Put the device in the right sampling mode for this frequency.

    Returns the new mode if the radio was restarted, None if nothing was
    needed. `announce` is called with a sentence for the listener's log before
    the radio goes down, so the gap is explained rather than just suffered.
    """
    if sdr is None or not supports_switching(sdr):
        return None

    try:
        samp_rate = int(sdr.props["samp_rate"])
    except (KeyError, TypeError, ValueError):
        samp_rate = 0

    wanted = required_mode(center_freq, samp_rate)
    if wanted is None:
        return None

    with _lock:
        if current_mode(sdr) == wanted:
            return None

        if announce is not None:
            if wanted == DIRECT_SAMPLING_Q:
                announce(
                    "Below {:.1f} MHz the tuner cannot reach: switching to direct "
                    "sampling. The receiver restarts, audio returns in a few "
                    "seconds.".format(TUNER_FLOOR_HZ / 1e6)
                )
            else:
                announce(
                    "Back above {:.1f} MHz: leaving direct sampling. The receiver "
                    "restarts, audio returns in a few seconds.".format(TUNER_FLOOR_HZ / 1e6)
                )

        logger.info(
            "direct sampling %s for %.3f MHz (was %s)",
            wanted, center_freq / 1e6, current_mode(sdr),
        )
        sdr.props["direct_sampling"] = wanted

        # The value is only read when the connector's command line is built, so
        # the process has to go round again for it to mean anything.
        try:
            sdr.stop()
            sdr.start()
        except Exception:
            logger.exception("could not restart the sdr for direct sampling")
            return None

        return wanted
