"""
DMR without the AMBE codec: identities and talkgroups, no voice.

OpenWebRX's DMR mode needs two things. One is digiham, which synchronises on
the TDMA bursts and pulls out both the voice frames and the signalling - radio
IDs, talkgroup, timeslot, call type. The other is an AMBE+2 decoder, which
turns those voice frames into audio.

Only the first is free. digiham is in the Debian repository and is installed
here; the codec is not. codecserver ships exactly one driver, libambe3k.so,
and that is not a software decoder at all - it drives an AMBE-3000 chip over a
serial port, so without the hardware MbeSynthesizer has no codec to ask and
has_codecserver_ambe() comes back false. That single missing piece takes the
whole mode away, signalling included, even though the signalling never passes
through the codec.

That last point is what makes this worth doing. In DigihamChain the metadata
leaves the decoder by its own route:

    self.decoder.setMetaWriter(buffer)

The decoder, not the synthesizer. So the chain can end at the decoder and the
metadata still arrives: who is transmitting, on which talkgroup, in which
timeslot, resolved against RadioID by the existing MetaParser, shown in the
panel the DMR mode already has. What is lost is the audio, and only the audio.

An AMBE-3000 dongle would fill that gap, and if one ever appears the full chain
comes back on its own - dsp.py prefers it whenever the codec is there.
"""

import logging
import time

from csdr.chain.demodulator import (
    BaseDemodulatorChain,
    DialFrequencyReceiver,
    FixedAudioRateChain,
    FixedIfSampleRateChain,
    MetaProvider,
    SlotFilterChain,
)
from csdr.module import ThreadModule
from digiham.modules import DcBlock, DmrDecoder, GfskDemodulator, WideRrcFilter
from pycsdr.modules import Buffer, FmDemod, Writer
from pycsdr.types import Format
from owrx.meta import MetaParser

logger = logging.getLogger(__name__)

AUDIO_RATE = 8000
IF_RATE = 48000


class VoiceToSilence(ThreadModule):
    """
    Drains the decoder's voice output and puts silence in its place.

    The draining is not optional. The decoder writes voice frames and
    signalling to two different buffers, and a buffer nobody reads fills up and
    blocks the writer - so leaving the voice output unread would stop the
    metadata as well, which is the one thing this mode exists to deliver.

    The silence is a courtesy: it keeps an audio stream present and at zero
    rather than absent, so the client behaves as it does in any other mode.

    It is paced by the clock rather than by the amount of data read. A frame
    count would be exact, but it would rest on an assumed number of bytes per
    frame, and digiham publishes no header to check that against. Real time is
    the thing actually being matched, so it is measured directly, and the cap
    keeps the first read after a long silence from emitting the whole gap.
    """

    MAX_CHUNK_S = 0.2

    def __init__(self):
        self.lastEmit = None
        super().__init__()

    def getInputFormat(self) -> Format:
        return Format.CHAR

    def getOutputFormat(self) -> Format:
        return Format.SHORT

    def run(self):
        while self.doRun:
            data = self.reader.read()
            if data is None:
                self.doRun = False
                break
            now = time.monotonic()
            if self.lastEmit is None:
                self.lastEmit = now
                continue
            elapsed = min(now - self.lastEmit, VoiceToSilence.MAX_CHUNK_S)
            self.lastEmit = now
            samples = int(elapsed * AUDIO_RATE)
            if samples > 0:
                try:
                    self.writer.write(bytes(2 * samples))
                except Exception:
                    logger.exception("could not write silence")


class DmrMeta(
    BaseDemodulatorChain,
    FixedIfSampleRateChain,
    FixedAudioRateChain,
    DialFrequencyReceiver,
    MetaProvider,
    SlotFilterChain,
):
    """
    The DMR chain of DigihamChain with the vocoder taken out.

    Everything up to and including the decoder is upstream's, unchanged: the
    same filter, the same symbol rate, the same decoder. Only MbeSynthesizer,
    DigitalVoiceFilter and the AGC are gone, because all three exist to shape
    audio that is not being produced.
    """

    def __init__(self):
        self.decoder = DmrDecoder()
        self.metaParser = None
        self.dialFrequency = None
        super().__init__([
            FmDemod(),
            DcBlock(),
            WideRrcFilter(),
            GfskDemodulator(samplesPerSymbol=10),
            self.decoder,
            VoiceToSilence(),
        ])

    def getFixedIfSampleRate(self) -> int:
        return IF_RATE

    def getFixedAudioRate(self) -> int:
        return AUDIO_RATE

    def supportsSquelch(self) -> bool:
        return False

    def setMetaWriter(self, writer: Writer) -> None:
        if self.metaParser is None:
            self.metaParser = MetaParser()
            buffer = Buffer(Format.CHAR)
            self.decoder.setMetaWriter(buffer)
            self.metaParser.setReader(buffer.getReader())
            if self.dialFrequency is not None:
                self.metaParser.setDialFrequency(self.dialFrequency)
        self.metaParser.setWriter(writer)

    def setSlotFilter(self, slotFilter: int) -> None:
        self.decoder.setSlotFilter(slotFilter)

    def setDialFrequency(self, frequency: int) -> None:
        self.dialFrequency = frequency
        if self.metaParser is None:
            return
        self.metaParser.setDialFrequency(frequency)

    def stop(self):
        if self.metaParser is not None:
            self.metaParser.stop()
        super().stop()
