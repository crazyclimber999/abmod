"""
Two-tone sequential paging decoder.

A two-tone page is one tone held for about a second, immediately followed by a
second tone held for several seconds. The pair identifies the station being
called. This is not a variation of the 5-tone decoder: there the tones are
short and come from a ten-digit alphabet, here they are long, continuous, and
drawn from tone plans that disagree with each other.

Because the tone plans disagree, the measured frequency is the primary result
and the plan is only a label. A listener can use "947.2 Hz / 332.6 Hz" even
when no plan matches, and a table that is slightly wrong cannot turn a correct
reading into a wrong one. The tones are long, so the frequency can be measured
far more precisely than a tone table needs: the FFT peak is refined by fitting
a parabola through its neighbours, which puts the reading within a hertz or so.
"""

import numpy as np
import logging

logger = logging.getLogger(__name__)

# Motorola Quick Call II tone groups, the most widely used plan. These are a
# label only, never a filter: a pair that matches nothing is still reported
# with its measured frequencies.
TONE_PLANS = {
    "QCII-1": [330.5, 349.0, 368.5, 389.0, 410.8, 433.7, 457.9, 483.5, 510.5, 539.0, 569.1],
    "QCII-2": [600.9, 634.5, 669.9, 707.3, 746.8, 788.5, 832.5, 879.0, 928.1, 980.0, 1034.7],
    "QCII-3": [1092.4, 1153.4, 1217.8, 1285.8, 1357.6, 1433.4, 1513.5, 1598.0, 1687.2, 1781.5, 1880.0],
    "QCII-4": [288.5, 296.5, 304.7, 313.0, 321.7, 339.6, 358.6, 378.6, 399.8, 422.1, 445.7],
    "QCII-5": [470.5, 496.8, 524.6, 553.9, 584.8, 617.4, 651.9, 688.3, 726.8, 767.4, 810.2],
    "QCII-6": [855.5, 903.2, 953.7, 1006.9, 1063.2, 1122.5, 1185.2, 1251.4, 1321.2, 1394.5, 1472.9],
    # the ZVEI tones are also used in pairs for paging in Europe
    "ZVEI": [2400.0, 1060.0, 1160.0, 1270.0, 1400.0, 1530.0, 1670.0, 1830.0, 2000.0, 2200.0],
}

# how far a measured tone may sit from a table entry and still be called a
# match. Paging transmitters are specified to about 1%, so this is generous
# without being loose enough to match the neighbouring tone in a group.
PLAN_TOLERANCE = 0.015

# Tones outside this range are not paging tones. The lower bound keeps rumble
# and the mains hum out, the upper one stays below the usual audio roll-off.
MIN_FREQ = 250.0
MAX_FREQ = 3000.0

# 2048 samples at 12 kHz is about 170 ms: short enough to see a one-second
# tone several times over, long enough for 5.9 Hz bins before interpolation.
WINDOW_SIZE = 2048
HOP_SIZE = 512

# two readings this close together are the same tone being held
SAME_TONE_RATIO = 0.02
# ... and this far apart are genuinely two different tones, so a single long
# tone cannot be split into a pair by a wobble in the middle
DISTINCT_TONE_RATIO = 0.03

# A is the short tone, B the long one. The ranges are wide because plans and
# transmitters differ; what matters is the shape, short then long.
MIN_A_MS, MAX_A_MS = 400.0, 2500.0
MIN_B_MS, MAX_B_MS = 800.0, 12000.0
# silence between the two tones; most plans run them back to back
MAX_GAP_MS = 400.0
# a gap longer than this ends the page
END_GAP_MS = 600.0

MIN_SNR = 4.0        # peak against the median of the spectrum
MIN_RMS = 0.002


class _Run(object):
    """One tone being held."""

    def __init__(self, frequency, window_ms):
        self.total_weight = 1.0
        self.weighted_sum = frequency
        self.duration_ms = window_ms

    @property
    def frequency(self):
        return self.weighted_sum / self.total_weight

    def extend(self, frequency, window_ms):
        self.weighted_sum += frequency
        self.total_weight += 1.0
        self.duration_ms += window_ms

    def matches(self, frequency):
        return abs(frequency - self.frequency) / self.frequency < SAME_TONE_RATIO


def match_plan(freq_a, freq_b):
    """
    Names the plan both tones belong to, or None.

    Both tones must come from the same group: a pair that happens to have one
    tone in one plan and the other in another is a coincidence, not a match.
    """
    for name, tones in TONE_PLANS.items():
        index_a = _index_in(tones, freq_a)
        index_b = _index_in(tones, freq_b)
        if index_a is not None and index_b is not None:
            return name, index_a + 1, index_b + 1
    return None


def _index_in(tones, frequency):
    best = None
    best_error = PLAN_TOLERANCE
    for index, tone in enumerate(tones):
        error = abs(frequency - tone) / tone
        if error < best_error:
            best_error = error
            best = index
    return best


class TwoToneDecoder(object):
    """
    Feed audio with process(samples); returns a list of dicts, one per page.
    """

    def __init__(self, sample_rate):
        self.sample_rate = sample_rate
        self.window_size = WINDOW_SIZE
        self.hop_size = HOP_SIZE
        self.hop_ms = self.hop_size * 1000.0 / sample_rate
        self._hann = np.hanning(self.window_size)
        self._freqs = np.fft.rfftfreq(self.window_size, 1.0 / sample_rate)
        self._low = int(np.searchsorted(self._freqs, MIN_FREQ))
        self._high = int(np.searchsorted(self._freqs, MAX_FREQ))
        self.reset()

    def reset(self):
        self._pending = np.zeros(0, dtype=np.float32)
        self.runs = []
        self.current = None
        self.silence_ms = 0.0

    def _peak(self, window):
        """The dominant frequency of one window, or None if nothing stands out."""
        if float(np.sqrt(np.mean(window ** 2))) < MIN_RMS:
            return None

        spectrum = np.abs(np.fft.rfft(window * self._hann))
        band = spectrum[self._low : self._high]
        if band.size < 3:
            return None

        index = int(np.argmax(band))
        peak = float(band[index])
        median = float(np.median(band))
        if median <= 0.0 or peak / median < MIN_SNR:
            return None

        absolute = index + self._low
        if absolute <= 0 or absolute >= spectrum.size - 1:
            return None

        # The true peak almost never sits exactly on a bin. Fitting a parabola
        # through the peak and its two neighbours recovers the offset, which
        # turns 5.9 Hz bins into a reading good to about a hertz.
        left, centre, right = spectrum[absolute - 1], spectrum[absolute], spectrum[absolute + 1]
        denominator = left - 2.0 * centre + right
        offset = 0.0 if denominator == 0 else 0.5 * (left - right) / denominator
        if abs(offset) > 1.0:
            offset = 0.0

        bin_width = self._freqs[1] - self._freqs[0]
        return float(self._freqs[absolute] + offset * bin_width)

    def process(self, samples):
        results = []
        if len(samples) == 0:
            return results
        self._pending = np.concatenate([self._pending, np.asarray(samples, dtype=np.float32)])

        while len(self._pending) >= self.window_size:
            window = self._pending[: self.window_size]
            self._pending = self._pending[self.hop_size :]

            frequency = self._peak(window)

            if frequency is None:
                self._closeRun()
                self.silence_ms += self.hop_ms
                if self.silence_ms >= END_GAP_MS:
                    results.extend(self._harvest())
                continue

            self.silence_ms = 0.0
            if self.current is not None and self.current.matches(frequency):
                self.current.extend(frequency, self.hop_ms)
            else:
                self._closeRun()
                self.current = _Run(frequency, self.hop_ms)

        for page in results:
            logger.info(
                "2-tone page decoded: %.1f Hz / %.1f Hz (%s)",
                page["tone_a"],
                page["tone_b"],
                page["plan"] or "no plan matched",
            )
        return results

    def _closeRun(self):
        if self.current is None:
            return
        # a run too short to be either tone is a transient, not a page
        if self.current.duration_ms >= MIN_A_MS:
            self.runs.append(self.current)
            if len(self.runs) > 8:
                self.runs = self.runs[-8:]
        self.current = None

    def _harvest(self):
        """Looks for a short tone followed by a long, different one."""
        results = []
        index = 0
        while index + 1 < len(self.runs):
            first, second = self.runs[index], self.runs[index + 1]
            if self._isPage(first, second):
                results.append(self._describe(first, second))
                index += 2
            else:
                index += 1
        self.runs = []
        return results

    @staticmethod
    def _isPage(first, second):
        if not (MIN_A_MS <= first.duration_ms <= MAX_A_MS):
            return False
        if not (MIN_B_MS <= second.duration_ms <= MAX_B_MS):
            return False
        # the second tone must be the longer one: that is what makes it a page
        # rather than two unrelated tones
        if second.duration_ms <= first.duration_ms:
            return False
        difference = abs(second.frequency - first.frequency) / first.frequency
        return difference >= DISTINCT_TONE_RATIO

    @staticmethod
    def _describe(first, second):
        plan = match_plan(first.frequency, second.frequency)
        return {
            "tone_a": round(first.frequency, 1),
            "tone_b": round(second.frequency, 1),
            "duration_a": int(round(first.duration_ms)),
            "duration_b": int(round(second.duration_ms)),
            "plan": plan[0] if plan else None,
            "tone_numbers": "{0}-{1}".format(plan[1], plan[2]) if plan else None,
        }

    def flush(self):
        self._closeRun()
        return self._harvest()
