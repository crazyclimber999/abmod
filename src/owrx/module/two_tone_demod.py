"""
Wiring of the two-tone paging decoder into the OpenWebRX DSP chain.

Same shape as the 5-tone decoder: a Chain of workers, with the audio arriving
through a reader and the results written to a writer.
"""

from csdr.chain.demodulator import ServiceDemodulator
from csdr.module import ThreadModule
from pycsdr.modules import Convert
from pycsdr.types import Format
from owrx.module.two_tone import TwoToneDecoder

import numpy as np
import pickle
import logging

logger = logging.getLogger(__name__)

AUDIO_RATE = 12000


class TwoToneParser(ThreadModule):
    """Reads demodulated audio and emits a dict for every decoded page."""

    def __init__(self):
        self.decoder = TwoToneDecoder(AUDIO_RATE)
        self.dial_frequency = None
        super().__init__()

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
                samples = np.frombuffer(data.tobytes(), dtype=np.int16).astype(np.float32) / 32768.0
                for page in self.decoder.process(samples):
                    message = {
                        "mode": "2tone",
                        "tone_a": page["tone_a"],
                        "tone_b": page["tone_b"],
                        "duration_a": page["duration_a"],
                        "duration_b": page["duration_b"],
                        "plan": page["plan"],
                        "tone_numbers": page["tone_numbers"],
                    }
                    if self.dial_frequency is not None:
                        message["freq"] = self.dial_frequency
                    self.writer.write(pickle.dumps(message))
            except Exception:
                logger.exception("error while decoding 2-tone audio")


class TwoToneDemodulator(ServiceDemodulator):
    def __init__(self):
        self.parser = TwoToneParser()
        super().__init__([Convert(Format.FLOAT, Format.SHORT), self.parser])

    def getFixedAudioRate(self) -> int:
        return AUDIO_RATE

    def setDialFrequency(self, frequency: int) -> None:
        self.parser.setDialFrequency(frequency)
