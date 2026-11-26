from owrx.source import SdrSource, SdrDeviceDescription
from owrx.socket import getAvailablePort
from owrx.property import PropertyDeleted
import socket
import threading
from owrx.command import Flag, Option
from typing import List
from owrx.form.input import Input, NumberInput, CheckboxInput

import logging

logger = logging.getLogger(__name__)

# Source types whose device is not on this machine's USB bus, so something
# else can re-open it behind openwebrx's back.
#
# For those, the gain has to be re-asserted. openwebrx sends it once, when it
# starts the connector, and the connector does not send it again when it
# merely reconnects. rtl_tcp resets the tuner when a client connects, so any
# reconnection - its own restart, a wi-fi blink, a cable pulled - leaves the
# dongle at minimum gain while every setting still reads correctly. Measured
# on a live receiver: an off-centre noise floor 14 dB down after a
# reconnection, with the configuration untouched, which is a thoroughly
# confusing thing to look at.
GAIN_REASSERT_TYPES = ("rtl_tcp", "soapy_remote")

# How often to say it again. Setting an RTL tuner to the gain it already has
# costs nothing and is not audible, so this is cheap; thirty seconds bounds
# how long a receiver can sit deaf after a reconnection.
GAIN_REASSERT_INTERVAL = 30


class ConnectorSource(SdrSource):
    def __init__(self, id, props):
        self.controlSocket = None
        self.controlPort = getAvailablePort()
        # Guards writes to the control socket. The gain keeper below writes
        # from its own thread, and two unsynchronised sendall() calls could
        # interleave their bytes into one unparseable line.
        self.controlLock = threading.Lock()
        self.gainKeeper = None
        self.gainKeeperStop = None
        super().__init__(id, props)

    def getCommandMapper(self):
        return (
            super()
            .getCommandMapper()
            .setMappings(
                {
                    "samp_rate": Option("-s"),
                    "tuner_freq": Option("-f"),
                    "port": Option("-p"),
                    "controlPort": Option("-c"),
                    "device": Option("-d"),
                    "iqswap": Flag("-i"),
                    "rtltcp_compat": Option("-r"),
                    "ppm": Option("-P"),
                    "rf_gain": Option("-g"),
                }
            )
        )

    def sendControlMessage(self, changes):
        with self.controlLock:
            if self.controlSocket is None:
                return
            for prop, value in changes.items():
                if value is PropertyDeleted:
                    value = None
                logger.debug("sending property change over control socket: {0} changed to {1}".format(prop, value))
                self.controlSocket.sendall("{prop}:{value}\n".format(prop=prop, value=value).encode())

    def onPropertyChange(self, changes):
        if self.monitor is None:
            return
        if (
            ("center_freq" in changes or "lfo_offset" in changes)
            and "lfo_offset" in self.sdrProps
            and self.sdrProps["lfo_offset"] is not None
        ):
            changes["center_freq"] = self.sdrProps["center_freq"] + self.sdrProps["lfo_offset"]
            changes.pop("lfo_offset", None)
        self.sendControlMessage(changes)

    def needsGainReassert(self) -> bool:
        """Whether this device can lose its gain without openwebrx noticing."""
        try:
            if "type" not in self.props or self.props["type"] not in GAIN_REASSERT_TYPES:
                return False
            # Nothing to re-assert if no gain was asked for. "auto" is left
            # alone on purpose: re-sending it would be re-asking for automatic
            # gain, which is a mode rather than a value.
            if "rf_gain" not in self.props:
                return False
            gain = self.props["rf_gain"]
            return gain is not None and str(gain).strip().lower() not in ("", "auto", "none")
        except Exception:
            return False

    def _keepGain(self, stop: threading.Event):
        while not stop.wait(GAIN_REASSERT_INTERVAL):
            try:
                if "rf_gain" not in self.props:
                    continue
                gain = self.props["rf_gain"]
                if gain is None:
                    continue
                self.sendControlMessage({"rf_gain": gain})
            except Exception:
                # A broken socket means the source is going away; the device's
                # own machinery will deal with that. Re-asserting a gain is
                # never worth taking anything down for.
                logger.debug("could not re-assert the gain; leaving it to the next round")

    def startGainKeeper(self):
        if self.gainKeeper is not None or not self.needsGainReassert():
            return
        logger.debug(
            "re-asserting the gain every %d s: this device is served over the network, "
            "and a reconnection would otherwise leave it at minimum gain",
            GAIN_REASSERT_INTERVAL,
        )
        self.gainKeeperStop = threading.Event()
        self.gainKeeper = threading.Thread(
            target=self._keepGain, args=(self.gainKeeperStop,), daemon=True,
            name="gain-keeper-%s" % self.getId(),
        )
        self.gainKeeper.start()

    def stopGainKeeper(self):
        if self.gainKeeperStop is not None:
            self.gainKeeperStop.set()
        self.gainKeeper = None
        self.gainKeeperStop = None

    def postStart(self):
        logger.debug("opening control socket...")
        controlSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        controlSocket.connect(("localhost", self.controlPort))
        with self.controlLock:
            self.controlSocket = controlSocket
        self.startGainKeeper()

    def stop(self):
        self.stopGainKeeper()
        super().stop()
        with self.controlLock:
            if self.controlSocket:
                self.controlSocket.close()
                self.controlSocket = None

    def getControlPort(self):
        return self.controlPort

    def getCommandValues(self):
        values = super().getCommandValues()
        values["port"] = self.getPort()
        values["controlPort"] = self.getControlPort()
        return values


class ConnectorDeviceDescription(SdrDeviceDescription):
    def getInputs(self) -> List[Input]:
        return super().getInputs() + [
            NumberInput(
                "rtltcp_compat",
                "Port for rtl_tcp compatible data",
                infotext="Activate an rtl_tcp compatible interface on the port number specified.<br />"
                + "Note: Port is only available on the local machine, not on the network.<br />"
                + "Note: IQ data may be degraded by the downsampling process to 8 bits.",
            ),
            CheckboxInput(
                "iqswap",
                "Swap I and Q channels",
                infotext="Swapping inverts the spectrum, so this is useful in combination with an inverting mixer",
            ),
        ]

    def getDeviceOptionalKeys(self):
        return super().getDeviceOptionalKeys() + ["rtltcp_compat", "iqswap"]

    def getProfileOptionalKeys(self):
        return super().getProfileOptionalKeys() + ["iqswap"]
