"""
Wiring of the CCIR 5-tone decoder into the OpenWebRX DSP chain.

A demodulator here is a Chain of workers, not a class with a process() method:
the audio arrives through a reader and the results are written to a writer, the
same shape as PocsagParser and the other python stages.
"""

from csdr.chain.demodulator import ServiceDemodulator
from csdr.module import ThreadModule
from pycsdr.modules import Convert
from pycsdr.types import Format
from owrx.module.five_tone import FiveToneDecoder

import numpy as np
import pickle
import logging

logger = logging.getLogger(__name__)

AUDIO_RATE = 12000


class FiveToneParser(ThreadModule):
    """
    Reads demodulated audio and emits a dict for every decoded sequence.
    """

    # Temporary: when this file exists the demodulated audio is written next
    # to it, so a real transmission can be replayed offline against any version
    # of the decoder. Capped so it cannot fill the SD card, and off unless the
    # flag file is created by hand.
    CAPTURE_FLAG = "/tmp/5tone_capture"
    CAPTURE_FILE = "/tmp/5tone_capture.raw"
    CAPTURE_MAX_BYTES = 12000 * 2 * 600  # ten minutes at 12 kHz, 16 bit

    def __init__(self):
        self.decoder = FiveToneDecoder(AUDIO_RATE)
        self.dial_frequency = None
        self.capture = None
        self.captured = 0
        super().__init__()

    def _capture(self, data):
        import os

        if self.capture is None:
            if not os.path.exists(FiveToneParser.CAPTURE_FLAG):
                return
            self.capture = open(FiveToneParser.CAPTURE_FILE, "ab")
            logger.info("5-tone: capturing audio to %s", FiveToneParser.CAPTURE_FILE)
        if self.captured >= FiveToneParser.CAPTURE_MAX_BYTES:
            return
        self.capture.write(data)
        self.capture.flush()
        self.captured += len(data)

    def getInputFormat(self) -> Format:
        return Format.SHORT

    def getOutputFormat(self) -> Format:
        return Format.CHAR

    def setDialFrequency(self, frequency: int) -> None:
        self.dial_frequency = frequency

    def run(self):
        while self.doRun:
            data = self.reader.read()
            if data is None:
                self.doRun = False
                break
            try:
                raw = data.tobytes()
                try:
                    self._capture(raw)
                except Exception:
                    logger.exception("5-tone: audio capture failed")
                samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
                results = self.decoder.process(samples)
                # The standards overlap: ZVEI1 and ZVEI2 differ in one digit,
                # and DZVEI is ZVEI shifted by one, so a single transmission
                # often matches several. Group by sequence so the operator sees
                # one line per call with the standards that produced it.
                grouped = {}
                for standard, sequence in results:
                    grouped.setdefault(sequence, []).append(standard)
                for sequence, standards in grouped.items():
                    message = {
                        "mode": "5tone",
                        "sequence": sequence,
                        "standard": "/".join(standards),
                    }
                    if self.dial_frequency is not None:
                        message["freq"] = self.dial_frequency
                    self.writer.write(pickle.dumps(message))
            except Exception:
                logger.exception("error while decoding 5-tone audio")


class FiveToneDemodulator(ServiceDemodulator):
    def __init__(self):
        self.parser = FiveToneParser()
        super().__init__([Convert(Format.FLOAT, Format.SHORT), self.parser])

    def getFixedAudioRate(self) -> int:
        return AUDIO_RATE

    def setDialFrequency(self, frequency: int) -> None:
        self.parser.setDialFrequency(frequency)
