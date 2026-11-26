/*
 * Reads the CTCSS sub-audible tone out of the demodulated audio.
 *
 * It runs in the browser, on the same samples the speaker gets. That is not a
 * shortcut: the tone was measured on exactly this data - audio pulled from the
 * receiver's websocket and decoded from ADPCM - and came out 34.7 times the
 * surrounding noise floor, 0.20 Hz from the nominal 107.2 Hz. The de-emphasis
 * in OpenWebRX's NFM chain is a low-pass, so it lifts the sub-audible end
 * rather than removing it, and there is no high-pass anywhere in that chain to
 * strip it. Radios usually filter CTCSS out so you do not hear it; this one
 * does not, which is why there is something left to measure.
 *
 * Goertzel rather than an FFT: 39 known frequencies are far cheaper to test
 * one by one than a whole transform, and after decimating to about 1 kHz the
 * whole thing costs a few hundred thousand operations a second.
 */

function CtcssDetector(onTone) {
    this.onTone = onTone;
    this.rateIn = 12000;
    this.rateOut = 1000;
    this.reset();
}

// The 39 standard tones. 254.1 is in some tables as a 40th; it is left out
// because it sits close enough to 250.3 to swap with it under noise.
CtcssDetector.TONES = [
     67.0,  69.3,  71.9,  74.4,  77.0,  79.7,  82.5,  85.4,  88.5,  91.5,
     94.8,  97.4, 100.0, 103.5, 107.2, 110.9, 114.8, 118.8, 123.0, 127.3,
    131.8, 136.5, 141.3, 146.2, 151.4, 156.7, 162.2, 167.9, 173.8, 179.9,
    186.2, 192.8, 203.5, 210.7, 218.1, 225.7, 233.6, 241.8, 250.3
];

// Two seconds. A CTCSS tone is continuous, so there is no hurry, and the
// length buys resolution: the closest pairs in the table are about 2.5 Hz
// apart and a shorter window smears them together.
CtcssDetector.WINDOW_S = 2.0;

// Measured: a real tone stands 34.7x above the median of the band. Noise with
// no tone peaks around 5x. Eight is well clear of both.
CtcssDetector.MIN_RATIO = 8.0;

// The winner must also beat the runner-up. The 5-tone decoder learnt this the
// hard way: compared against an average, a merely noisy peak clears the bar,
// because most of the other bins sit near zero and drag the average down.
CtcssDetector.MIN_MARGIN = 1.8;

CtcssDetector.prototype.reset = function() {
    this.decimate = Math.max(1, Math.round(this.rateIn / this.rateOut));
    this.rateOut = this.rateIn / this.decimate;
    this.acc = 0;
    this.accCount = 0;
    this.buffer = new Float32Array(Math.round(this.rateOut * CtcssDetector.WINDOW_S));
    this.filled = 0;
    this.sinceTest = 0;
    this.lastTone = null;
    this.tunedAt = null;
    this.pending = null;
    this.pendingCount = 0;
};

CtcssDetector.prototype.setSampleRate = function(rate) {
    if (!rate || rate === this.rateIn) return;
    this.rateIn = rate;
    this.rateOut = 1000;
    this.reset();
};

/* Averaging groups of samples is a crude low-pass, but the only thing that
 * matters below 260 Hz is that nothing above 500 Hz folds down onto it, and a
 * box of 12 samples at 12 kHz puts its first null at 1 kHz. */
CtcssDetector.prototype.push = function(samples) {
    if (!samples || !samples.length) return;
    for (var i = 0; i < samples.length; i++) {
        this.acc += samples[i];
        if (++this.accCount < this.decimate) continue;
        var v = this.acc / this.decimate;
        this.acc = 0;
        this.accCount = 0;

        if (this.filled < this.buffer.length) {
            this.buffer[this.filled++] = v;
        } else {
            this.buffer.copyWithin(0, 1);
            this.buffer[this.buffer.length - 1] = v;
        }
        // test twice a second once the buffer is full
        if (this.filled >= this.buffer.length && ++this.sinceTest >= this.rateOut / 2) {
            this.sinceTest = 0;
            this.test();
        }
    }
};

CtcssDetector.prototype.goertzel = function(frequency) {
    var n = this.buffer.length;
    var k = 2 * Math.cos(2 * Math.PI * frequency / this.rateOut);
    var s0 = 0, s1 = 0, s2 = 0;
    for (var i = 0; i < n; i++) {
        s0 = this.buffer[i] + k * s1 - s2;
        s2 = s1;
        s1 = s0;
    }
    return Math.sqrt(s1 * s1 + s2 * s2 - k * s1 * s2);
};

/* The frequency the tone was heard on. A tone belongs to the frequency it was
 * heard on: move away and it means nothing any more, while staying put it
 * still holds even after the carrier drops. */
CtcssDetector.prototype.setTunedProbe = function(probe) {
    this.tunedProbe = probe;
};

CtcssDetector.prototype.test = function() {
    // retuned: what we knew no longer applies
    if (this.tunedProbe) {
        var tuned = this.tunedProbe();
        if (tuned !== null && tuned !== undefined) {
            if (this.tunedAt !== null && this.tunedAt !== undefined && tuned !== this.tunedAt) {
                this.tunedAt = tuned;
                this.pending = null;
                this.pendingCount = 0;
                if (this.lastTone !== null) {
                    this.lastTone = null;
                    if (this.onTone) this.onTone(null, 0);
                }
                return;
            }
            this.tunedAt = tuned;
        }
    }

    var magnitudes = [];
    var i;
    for (i = 0; i < CtcssDetector.TONES.length; i++) {
        magnitudes.push(this.goertzel(CtcssDetector.TONES[i]));
    }
    var ordered = magnitudes.slice().sort(function(a, b) { return a - b; });
    var median = ordered[Math.floor(ordered.length / 2)];
    var best = ordered[ordered.length - 1];
    var second = ordered[ordered.length - 2];
    var tone = CtcssDetector.TONES[magnitudes.indexOf(best)];

    var ok = median > 0 && best / median >= CtcssDetector.MIN_RATIO
          && second > 0 && best / second >= CtcssDetector.MIN_MARGIN;

    // One window is a guess; two in a row is a reading. A transmission that
    // only just opened often gives one good window and one ragged one.
    if (ok && tone === this.pending) {
        this.pendingCount++;
    } else {
        this.pending = ok ? tone : null;
        this.pendingCount = ok ? 1 : 0;
    }

    /* Once read, the tone STAYS. CTCSS only exists while there is a carrier,
     * but it is a property of the channel rather than of the moment: clearing
     * it at the end of a transmission would mean showing it for two seconds
     * and then removing the very information that was wanted. A different tone
     * replaces it; retuning forgets it; otherwise it stays. */
    if (this.pendingCount >= 2 && this.pending !== this.lastTone) {
        this.lastTone = this.pending;
        if (this.onTone) {
            this.onTone(this.lastTone, best / median);
        }
    }
};

CtcssDetector.prototype.clear = function() {
    var had = this.lastTone;
    this.reset();
    if (had && this.onTone) this.onTone(null, 0);
};
