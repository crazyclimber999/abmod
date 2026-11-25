"""
5-tone (SELCALL) decoder supporting the common standards.

The same digit sits at a different frequency in every standard, so a decoder
built for one of them stays silent on the others. All the known sets are
therefore evaluated in parallel and the sequence is reported together with the
standard that produced it.

One FFT per window is computed and shared by every standard: running a separate
Goertzel per standard would be several times the work, which matters on a
Raspberry Pi.
"""

import numpy as np
import logging

logger = logging.getLogger(__name__)

# digit -> frequency, per standard. "R" is the repeat tone, which stands for
# "same digit as the previous one": two identical tones in a row cannot be told
# apart by duration alone.
TONE_SETS = {
    # CCIR and EEA share the digit frequencies and differ only in timing and
    # in the special tones, so a single table covers both.
    #
    # The repeat tone is 2110 Hz. It was 2400 Hz here, which is wrong and was
    # the reason real CCIR traffic would not decode: 2400 Hz in this system is
    # the group tone "A", not the repeat. A call sending 3, 1, repeat, 0, 1 -
    # that is 31101 - therefore had its third tone go unrecognised, the
    # sequence came out four digits long, and nothing was ever emitted.
    # Measured off the air at 2109 Hz before being changed.
    "CCIR": {
        "1": 1124.0, "2": 1197.0, "3": 1275.0, "4": 1358.0, "5": 1447.0,
        "6": 1540.0, "7": 1640.0, "8": 1747.0, "9": 1860.0, "0": 1981.0,
        "R": 2110.0,
    },
    "ZVEI1": {
        "1": 1060.0, "2": 1160.0, "3": 1270.0, "4": 1400.0, "5": 1530.0,
        "6": 1670.0, "7": 1830.0, "8": 2000.0, "9": 2200.0, "0": 2400.0,
        "R": 2800.0,
    },
    "ZVEI2": {
        "1": 1060.0, "2": 1160.0, "3": 1270.0, "4": 1400.0, "5": 1530.0,
        "6": 1670.0, "7": 1830.0, "8": 2000.0, "9": 2200.0, "0": 970.0,
        "R": 2800.0,
    },
    "DZVEI": {
        "1": 970.0, "2": 1060.0, "3": 1160.0, "4": 1270.0, "5": 1400.0,
        "6": 1530.0, "7": 1670.0, "8": 1830.0, "9": 2000.0, "0": 2400.0,
        "R": 2800.0,
    },
    "EIA": {
        "1": 741.0, "2": 882.0, "3": 1023.0, "4": 1164.0, "5": 1305.0,
        "6": 1446.0, "7": 1587.0, "8": 1728.0, "9": 1869.0, "0": 600.0,
        "R": 459.0,
    },
    "CCITT": {
        "1": 697.0, "2": 770.0, "3": 852.0, "4": 941.0, "5": 1209.0,
        "6": 1335.0, "7": 1477.0, "8": 1633.0, "9": 1800.0, "0": 400.0,
        "R": 2400.0,
    },
}

SEQUENCE_LENGTH = 5

# A tone held longer than a whole sequence is a carrier, not digits. Five is
# the natural cap: it allows a call made of five identical digits, which is
# rare but legal, without letting a stuck transmitter generate endless ones.
MAX_REPEATS = 5

# Nominal length of one tone, per standard. Only used when FEWER than five
# tones were seen, to work out how many digits a held tone stands for.
NOMINAL_TONE_MS = {
    "CCIR": 100.0, "ZVEI1": 70.0, "ZVEI2": 70.0,
    "DZVEI": 70.0, "EIA": 33.0, "CCITT": 100.0,
}
DEFAULT_NOMINAL_MS = 100.0

# A run this much shorter than the typical one is a transition between two
# tones or a burst of noise, not a digit.
BLIP_RATIO = 0.6

# A real tone is one line in the spectrum; voice and noise are spread across
# it. This is the ratio between the strongest bin and the MEDIAN of the whole
# useful band - not of the standard's own eleven tones, which is the comparison
# that was missing and let every burst of speech look like a digit to all six
# standards at once.
#
# Measured on six minutes of real traffic, with the ground truth that every
# call on that channel is CCIR and starts with 31: a true call reaches 122,
# speech peaks at 38, a silent channel at 6. The gate at 20 took the decoder
# from 1 true call and 108 false ones to 9 true and 3 false on CCIR. It does
# not only remove rubbish: without it the noise windows interleaved with the
# real tones and corrupted the digit runs, so most real calls never came out
# at all.
MIN_PURITY = 20.0
PURITY_BAND = (500.0, 3000.0)

MIN_TONE_MS = 30.0     # EEA tones are 40 ms, CCIR 100 ms: stay permissive
MAX_GAP_MS = 600.0     # a longer silence ends the sequence
# 25 ms at 12 kHz gives 40 Hz wide FFT bins. This cannot go much lower: CCIR
# puts its tones 73 Hz apart, so a 10 ms window (100 Hz bins) blurs them
# together and the decoder stops recognising CCIR entirely.
WINDOW_MS = 25.0
# The windows OVERLAP: the window stays 25 ms for frequency resolution, but it
# advances only this far each time, so a tone's length is measured to about
# 10 ms instead of to the nearest 25 ms. Without the overlap a 70 ms tone is
# two or three windows - a 33% error - and any estimate of how long one tone
# is falls apart, turning single tones into repeated digits.
HOP_MS = 10.0
# How many times stronger the winning tone must be than the RUNNER-UP.
# This replaced a comparison against the average of the other tones, which was
# far too easy to clear and produced confidently wrong digits on real traffic.
# With this metric a sweep from 1.5 to 4.0 gives 18/18 correct decodes and zero
# wrong digits, including with speech mixed in, so the value is not critical;
# 2.5 sits comfortably in the middle.
MIN_SNR = 2.5
MIN_RMS = 0.002        # below this the window is silence, not a tone


class _StandardState:
    """State machine for one standard."""

    def __init__(self, name, tones):
        self.name = name
        self.tones = tones
        self.nominal_ms = NOMINAL_TONE_MS.get(name, DEFAULT_NOMINAL_MS)
        self.reset()

    def reset(self):
        self.runs = []          # (tone, duration_ms) still to be interpreted
        self.current = None
        self.current_ms = 0.0
        self.silence_ms = 0.0

    def commit(self):
        if self.current is None or self.current_ms < MIN_TONE_MS:
            self.current = None
            self.current_ms = 0.0
            return
        self.runs.append((self.current, self.current_ms))
        self.current = None
        self.current_ms = 0.0

    def digits(self):
        """
        Turns the tone runs of this burst into digits.

        A five-tone call carries five digits, and that constraint does most of
        the work. When five or more runs were heard, each one is simply a digit
        and no reasoning about duration is needed. Only when FEWER than five
        were heard must a held tone stand for a repeated digit — which is how a
        repeat is sent when the repeat tone is not used — and only then is the
        nominal length of the standard consulted.

        Measuring the unit from the burst instead was tried and is much worse:
        a 25 ms blip at the boundary between two tones becomes the unit and
        every real tone inflates into four digits.
        """
        runs = [(tone, duration) for tone, duration in self.runs if duration >= MIN_TONE_MS]
        if not runs:
            return []

        # Drop the blips: a run far shorter than the typical one is a
        # transition or the noise burst the squelch lets through when it opens.
        durations = sorted(duration for _, duration in runs)
        typical = durations[len(durations) // 2]
        substantial = [(t, d) for t, d in runs if d >= typical * BLIP_RATIO]
        if substantial:
            runs = substantial

        if len(runs) >= SEQUENCE_LENGTH:
            tones = [tone for tone, _ in runs]
        else:
            # Fewer than five tones were heard, so at least one of them has to
            # stand for a repeated digit. How many depends on how long one tone
            # is - and that is measured from this burst, not read from a table.
            #
            # The shortest run left after the blips were dropped IS a single
            # tone: a burst with a repeat in it still contains the singles
            # around it. Reading the length from a table instead is what broke
            # this twice: a system sending 150 ms tones against a table saying
            # 100 ms turns every single tone into two digits, and 31101 comes
            # out as 10011.
            #
            # Only when there is nothing to compare against - one single run,
            # which is five identical digits sent as one long tone - is the
            # nominal length of the standard the best guess available.
            if len(runs) > 1:
                unit = max(min(duration for _, duration in runs), MIN_TONE_MS)
            else:
                unit = self.nominal_ms

            tones = []
            for tone, duration in runs:
                ripetizioni = max(1, min(int(round(duration / unit)), MAX_REPEATS))
                tones.extend([tone] * ripetizioni)

        out = []
        for tone in tones:
            digit = out[-1] if (tone == "R" and out) else (None if tone == "R" else tone)
            if digit is not None:
                out.append(digit)
        return out


class FiveToneDecoder:
    """
    Feed audio with process(samples); returns a list of (standard, sequence)
    for the sequences completed by that chunk.
    """

    def __init__(self, sample_rate, standards=None):
        self.sample_rate = sample_rate
        self.window_size = max(8, int(sample_rate * WINDOW_MS / 1000.0))
        self.hop_size = max(1, int(sample_rate * HOP_MS / 1000.0))
        self.hop_ms = self.hop_size * 1000.0 / sample_rate
        self._hann = np.hanning(self.window_size)
        # costruita alla prima finestra, quando si conosce la sua lunghezza
        self._purity_band = None

        names = standards or list(TONE_SETS)
        self.states = [_StandardState(n, TONE_SETS[n]) for n in names]

        # every frequency any standard cares about, mapped to its FFT bin
        freqs = np.fft.rfftfreq(self.window_size, 1.0 / sample_rate)
        self._bins = {}
        for state in self.states:
            for frequency in state.tones.values():
                if frequency not in self._bins:
                    self._bins[frequency] = int(np.argmin(np.abs(freqs - frequency)))

        self._pending = np.zeros(0, dtype=np.float32)

    def reset(self):
        for state in self.states:
            state.reset()
        self._pending = np.zeros(0, dtype=np.float32)

    def _magnitudes(self, window):
        spectrum = np.abs(np.fft.rfft(window * self._hann))
        if self._purity_band is None:
            freqs = np.fft.rfftfreq(len(window), 1.0 / self.sample_rate)
            self._purity_band = (freqs >= PURITY_BAND[0]) & (freqs <= PURITY_BAND[1])
        band = spectrum[self._purity_band]
        if band.size:
            median = float(np.median(band))
            if median > 0.0 and float(band.max()) / median < MIN_PURITY:
                # nothing in this window stands out from the broadband floor,
                # so there is no tone here whatever the tone bins say
                return {frequency: 0.0 for frequency in self._bins}
        return {frequency: float(spectrum[b]) for frequency, b in self._bins.items()}

    @staticmethod
    def _best_digit(tones, magnitudes):
        """
        The dominant digit of one standard, or None if nothing stands out.

        The winner is compared with the RUNNER-UP, not with the average of the
        others. Comparing against the average is far too easy to satisfy: most
        of the ten remaining bins sit near zero, so they drag the average down
        and a merely noisy peak clears the bar. That produced digits that were
        confidently wrong. Against the second best, a real tone wins by a wide
        margin while noise does not.
        """
        values = sorted(((magnitudes[f], digit) for digit, f in tones.items()), reverse=True)
        best_value, best = values[0]
        second_value = values[1][0] if len(values) > 1 else 0.0
        if best_value <= 0.0:
            return None
        if second_value <= 0.0:
            return best
        return best if (best_value / second_value) >= MIN_SNR else None

    def process(self, samples):
        results = []
        if len(samples) == 0:
            return results
        self._pending = np.concatenate([self._pending, np.asarray(samples, dtype=np.float32)])

        while len(self._pending) >= self.window_size:
            window = self._pending[: self.window_size]
            self._pending = self._pending[self.hop_size :]

            if float(np.sqrt(np.mean(window ** 2))) < MIN_RMS:
                magnitudes = None
            else:
                magnitudes = self._magnitudes(window)

            for state in self.states:
                tone = None if magnitudes is None else self._best_digit(state.tones, magnitudes)

                if tone is None:
                    state.commit()
                    state.silence_ms += self.hop_ms
                    if state.silence_ms >= MAX_GAP_MS and state.runs:
                        # The sequence is read when the gap closes it, and the
                        # LAST five digits are taken rather than the first: a
                        # burst of noise as the squelch opens adds a spurious
                        # digit at the front, while the end is always the real
                        # tail of the call.
                        digits = state.digits()
                        if len(digits) >= SEQUENCE_LENGTH:
                            results.append((state.name, "".join(digits[-SEQUENCE_LENGTH:])))
                        state.runs = []
                    continue

                state.silence_ms = 0.0
                if tone == state.current:
                    state.current_ms += self.hop_ms
                else:
                    state.commit()
                    state.current = tone
                    state.current_ms = self.hop_ms

                # A long burst must not grow without bound, but the unit used
                # to count repeats comes from the runs themselves, so the
                # trimming is generous: dropping too much would take away the
                # short run the unit is measured from.
                if len(state.runs) > SEQUENCE_LENGTH * 4:
                    state.runs = state.runs[-SEQUENCE_LENGTH * 2 :]

        for standard, sequence in results:
            logger.info("5-tone sequence decoded (%s): %s", standard, sequence)
        return results

    def flush(self):
        results = []
        for state in self.states:
            state.commit()
            digits = state.digits()
            if len(digits) >= SEQUENCE_LENGTH:
                results.append((state.name, "".join(digits[-SEQUENCE_LENGTH:])))
            state.runs = []
        return results
