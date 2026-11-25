from owrx.details import ReceiverDetails
from owrx import autohf
from owrx.dsp import DspManager
from owrx.cpu import CpuUsageThread
from owrx.sdr import SdrService
from owrx.source import SdrSourceState, SdrClientClass, SdrSourceEventClient
from owrx.client import ClientRegistry, TooManyClientsException
from owrx.feature import FeatureDetector
from owrx.version import openwebrx_version
from owrx.bands import Bandplan
from owrx.bookmarks import Bookmarks, Bookmark
from owrx.map import Map
from owrx.property import PropertyStack, PropertyDeleted
from owrx.modes import Modes, DigitalMode
from owrx.config import Config
from owrx.waterfall import WaterfallOptions
from owrx.websocket import Handler
from queue import Queue, Full, Empty
from abc import ABCMeta, abstractmethod
import json
import threading
import struct

import logging
import os

logger = logging.getLogger(__name__)

PoisonPill = object()


class Client(Handler, metaclass=ABCMeta):
    def __init__(self, conn):
        self.conn = conn
        self.multithreadingQueue = Queue(100)

        def mp_passthru():
            run = True
            while run:
                try:
                    data = self.multithreadingQueue.get()
                    if data is PoisonPill:
                        run = False
                    else:
                        self.send(data)
                    self.multithreadingQueue.task_done()
                except (EOFError, OSError, ValueError):
                    run = False
                except Exception:
                    logger.exception("Exception on client multithreading queue")

            # unset the queue object to free shared memory file descriptors
            self.multithreadingQueue = None

        threading.Thread(target=mp_passthru, name="connection_mp_passthru").start()

    def send(self, data):
        try:
            self.conn.send(data)
        except IOError:
            logger.exception("error in Client::send()")
            self.close(error=True)

    def close(self, error: bool = False):
        if self.multithreadingQueue is not None:
            while True:
                try:
                    self.multithreadingQueue.get(block=False)
                except Empty:
                    break
            try:
                self.multithreadingQueue.put(PoisonPill, block=False)
            except Full:
                # this shouldn't happen, we just emptied the queue, but it's not worth risking the exception
                logger.exception("impossible queue state: Full after Empty")
        self.conn.close(socketError=error)

    def mp_send(self, data):
        if self.multithreadingQueue is None:
            return
        try:
            self.multithreadingQueue.put(data, block=False)
        except Full:
            self.close(error=True)

    @abstractmethod
    def handleTextMessage(self, conn, message):
        pass

    def handleBinaryMessage(self, conn, data):
        logger.error("unsupported binary message, discarding")

    def handleClose(self):
        self.close()


class OpenWebRxClient(Client, metaclass=ABCMeta):
    def __init__(self, conn):
        super().__init__(conn)

        receiver_details = ReceiverDetails()

        def send_receiver_info(*args):
            receiver_info = receiver_details.__dict__()
            self.write_receiver_details(receiver_info)

        self._detailsSubscription = receiver_details.wire(send_receiver_info)
        send_receiver_info()

    def write_receiver_details(self, details):
        self.send({"type": "receiver_details", "value": details})

    def close(self, error: bool = False):
        self._detailsSubscription.cancel()
        super().close(error)


class OpenWebRxReceiverClient(OpenWebRxClient, SdrSourceEventClient):
    sdr_config_keys = [
        "waterfall_levels",
        "samp_rate",
        "start_mod",
        "start_freq",
        "center_freq",
        "initial_squelch_level",
        "sdr_id",
        "profile_id",
        "squelch_auto_margin",
    ]

    global_config_keys = [
        "waterfall_scheme",
        "waterfall_colors",
        "waterfall_auto_levels",
        "waterfall_auto_min_range",
        "fft_size",
        "audio_compression",
        "fft_compression",
        "max_clients",
        "tuning_precision",
    ]

    def __init__(self, conn, user=None):
        super().__init__(conn)

        self.user = user
        self.dsp = None
        self.dspLock = threading.Lock()
        self.sdr = None
        self.configSubs = []
        self.bookmarkSub = None
        self.connectionProperties = {}

        try:
            ClientRegistry.getSharedInstance().addClient(self)
        except TooManyClientsException:
            self.write_backoff_message("Too many clients")
            self.close()
            raise

        self.setupGlobalConfig()
        self.stack = self.setupStack()

        self.setSdr()

        features = FeatureDetector().feature_availability()
        self.write_features(features)

        modes = Modes.getModes()
        self.write_modes(modes)

        self.configSubs.append(SdrService.getActiveSources().wire(self._onSdrDeviceChanges))
        self.configSubs.append(SdrService.getAvailableProfiles().wire(self._sendProfiles))
        self._sendProfiles()

        CpuUsageThread.getSharedInstance().add_client(self)

    def setupStack(self):
        stack = PropertyStack()
        # stack layer 0 reserved for sdr properties
        # stack.addLayer(0, self.sdr.getProps())
        stack.addLayer(1, Config.get())
        configProps = stack.filter(*OpenWebRxReceiverClient.sdr_config_keys)

        def sendConfig(changes=None):
            if changes is None:
                config = configProps.__dict__()
            else:
                # transform deletions into Nones
                config = {k: v if v is not PropertyDeleted else None for k, v in changes.items()}
            if (
                (changes is None or "start_freq" in changes or "center_freq" in changes)
                and "start_freq" in configProps
                and "center_freq" in configProps
            ):
                config["start_offset_freq"] = configProps["start_freq"] - configProps["center_freq"]
            if (changes is None or "profile_id" in changes) and self.sdr is not None:
                config["sdr_id"] = self.sdr.getId()
            self.write_config(config)

        def sendBookmarks(*args):
            cf = configProps["center_freq"]
            srh = configProps["samp_rate"] / 2
            dial_frequencies = []
            bookmarks = []
            if "center_freq" in configProps and "samp_rate" in configProps:
                frequencyRange = (cf - srh, cf + srh)
                # dial frequencies come from the bandplan and stay visible to
                # everyone; bookmark tags are user data and do not
                dial_frequencies = Bandplan.getSharedInstance().collectDialFrequencies(frequencyRange)
                if self._bookmarks_allowed():
                    bookmarks = [b.__dict__() for b in Bookmarks.getSharedInstance().getBookmarks(frequencyRange)]
            self.write_dial_frequencies(dial_frequencies)
            self.write_bookmarks(bookmarks)

        def updateBookmarkSubscription(*args):
            if self.bookmarkSub is not None:
                self.bookmarkSub.cancel()
            if "center_freq" in configProps and "samp_rate" in configProps:
                cf = configProps["center_freq"]
                srh = configProps["samp_rate"] / 2
                frequencyRange = (cf - srh, cf + srh)
                self.bookmarkSub = Bookmarks.getSharedInstance().subscribe(frequencyRange, sendBookmarks)
                sendBookmarks()

        self.configSubs.append(configProps.wire(sendConfig))
        self.configSubs.append(stack.filter("center_freq", "samp_rate").wire(updateBookmarkSubscription))

        # send initial config
        sendConfig()
        return stack

    def setupGlobalConfig(self):
        def writeConfig(changes):
            # TODO it would be nicer to have all options available and switchable in the client
            # this restores the existing functionality for now, but there is lots of potential
            if "waterfall_scheme" in changes or "waterfall_colors" in changes:
                scheme = WaterfallOptions(globalConfig["waterfall_scheme"]).instantiate()
                changes["waterfall_colors"] = scheme.getColors()
            self.write_config(changes)

        globalConfig = Config.get().filter(*OpenWebRxReceiverClient.global_config_keys)
        self.configSubs.append(globalConfig.wire(writeConfig))
        writeConfig(globalConfig.__dict__())

    def onStateChange(self, state: SdrSourceState):
        if state is SdrSourceState.RUNNING:
            self.handleSdrAvailable()
        elif state is SdrSourceState.STOPPING:
            # Upstream only listens for RUNNING, which is enough while the
            # source only ever stops because the last listener left. It is not
            # enough when the source is restarted underneath a listener who is
            # still there - switching the device into direct sampling does
            # exactly that. Without this the old dsp chain stays wired to a
            # process that has gone, the waterfall freezes, and handleSdrAvailable
            # then reconfigures that same dead chain instead of building a new
            # one.
            self.stopDsp()

    def onFail(self):
        logger.warning('SDR device "%s" has failed, selecting new device', self.sdr.getName())
        self.write_log_message('SDR device "{0}" has failed, selecting new device'.format(self.sdr.getName()))
        self.setSdr()

    def onDisable(self):
        logger.warning('SDR device "%s" was disabled, selecting new device', self.sdr.getName())
        self.write_log_message('SDR device "{0}" was disabled, selecting new device'.format(self.sdr.getName()))
        self.setSdr()

    def onShutdown(self):
        logger.warning('SDR device "%s" is shutting down, selecting new device', self.sdr.getName())
        self.write_log_message('SDR device "{0}" is shutting down, selecting new device'.format(self.sdr.getName()))
        self.setSdr()

    def getClientClass(self) -> SdrClientClass:
        return SdrClientClass.USER

    def _onSdrDeviceChanges(self, changes):
        # restart the client if an sdr has become available
        if self.sdr is None and any(s is not PropertyDeleted for s in changes.values()):
            self.setSdr()

    def _sendProfiles(self, *args):
        profiles = [{"id": pid, "name": name} for pid, name in SdrService.getAvailableProfiles().items()]
        self.write_profiles(profiles)

    def handleTextMessage(self, conn, message):
        try:
            message = json.loads(message)
            if "type" in message:
                if message["type"] == "dspcontrol":
                    dsp = self.getDsp()
                    if dsp is None:
                        logger.warning("DSP not available; discarding client dspcontrol message")
                    else:
                        if "action" in message and message["action"] == "start":
                            dsp.start()

                        if "params" in message:
                            params = message["params"]
                            dsp.setProperties(params)

                elif message["type"] == "setsdr":
                    if "params" in message:
                        self.setSdr(message["params"]["sdr"])
                elif message["type"] == "selectprofile":
                    if "params" in message and "profile" in message["params"]:
                        profile = message["params"]["profile"].split("|")
                        self.setSdr(profile[0])
                        self.sdr.activateProfile(profile[1])
                elif message["type"] == "setcenterfreq":
                    if "params" in message and "freq" in message["params"]:
                        if self.sdr is not None:
                            try:
                                freq = int(message["params"]["freq"])
                                # The frequency goes into the properties FIRST,
                                # and only then is the sampling mode considered.
                                # Direct sampling is a command line option, so
                                # changing it restarts the connector, and the
                                # connector builds its command line from these
                                # same properties: set the frequency first and
                                # it comes up already tuned and already in the
                                # right mode, in one go.
                                #
                                # The other way round - restart, then retune
                                # over the control socket - leaves the
                                # connector starting on the OLD frequency in
                                # the NEW mode, which for a tuner asked to
                                # reach 6 MHz means it never comes up properly.
                                # Measured: it ended on 15.001 MHz, neither the
                                # frequency it left nor the one it was asked
                                # for.
                                self.sdr.props["center_freq"] = freq
                                autohf.adjust(
                                    self.sdr, freq, announce=self.write_log_message
                                )
                                # sempre, non solo quando cambia: cosi
                                # l'indicatore e corretto anche se un altro
                                # client ha mosso la radio nel frattempo
                                self.write_config(
                                    {"direct_sampling": autohf.current_mode(self.sdr)}
                                )
                                dsp = self.getDsp()
                                if dsp is not None:
                                    dsp.props["center_freq"] = freq
                                self.write_config({"center_freq": freq})
                                logger.debug("Center frequency changed to %d Hz", freq)
                            except (ValueError, KeyError) as e:
                                logger.warning("Failed to set center_freq: %s", e)
                elif message["type"] == "setsamplerate":
                    if "params" in message and "samp_rate" in message["params"]:
                        if self.sdr is not None:
                            try:
                                samp_rate = int(message["params"]["samp_rate"])
                                self.sdr.props["samp_rate"] = samp_rate
                                self.write_config({"samp_rate": samp_rate})
                                logger.debug("Sample rate changed to %d Hz", samp_rate)
                            except (ValueError, KeyError) as e:
                                logger.warning("Failed to set samp_rate: %s", e)
                elif message["type"] == "setgain":
                    if "params" in message and "gain" in message["params"]:
                        if self.sdr is not None:
                            try:
                                gain = message["params"]["gain"]
                                self.sdr.props["rf_gain"] = gain
                                self.write_config({"rf_gain": gain})
                                logger.debug("RF gain changed to %s", gain)
                            except (ValueError, KeyError) as e:
                                logger.warning("Failed to set rf_gain: %s", e)
                elif message["type"] == "setsquelch":
                    if "params" in message and "squelch" in message["params"]:
                        if self.sdr is not None:
                            try:
                                squelch = int(message["params"]["squelch"])
                                self.sdr.props["squelch_level"] = squelch
                                self.write_config({"squelch_level": squelch})
                                logger.debug("Squelch changed to %d dB", squelch)
                            except (ValueError, KeyError) as e:
                                logger.warning("Failed to set squelch_level: %s", e)
                elif message["type"] == "savedefaults":
                    # writes the receiver configuration for everyone, so it is
                    # restricted to administrators
                    if not self._defaults_allowed():
                        logger.warning("unauthorized savedefaults request")
                        self.write_defaults_saved(False, "Administrator privileges required")
                    else:
                        self._save_defaults(message.get("params", {}))
                elif message["type"] == "getbandplan":
                    # same rule as the bookmarks: readable once logged in
                    if not self._bookmarks_allowed():
                        logger.warning("unauthorized getbandplan request")
                    else:
                        self._send_bandplan()
                elif message["type"] in ("savebandplanentry", "deletebandplanentry"):
                    # editing the bandplan changes the receiver for everyone
                    if not self._defaults_allowed():
                        logger.warning("unauthorized bandplan edit: %s", message["type"])
                        self.write_bandplan_result(False, "Administrator privileges required")
                    elif "params" not in message:
                        self.write_bandplan_result(False, "Missing parameters")
                    elif message["type"] == "savebandplanentry":
                        self._save_bandplan_entry(message["params"])
                    else:
                        self._delete_bandplan_entry(message["params"])
                elif message["type"] in ("getmemories", "savememory", "deletememory"):
                    # Hiding the button in the template is not enough: without this
                    # check the bookmarks would stay readable and writable by anyone
                    # able to send the message over the websocket.
                    if not self._bookmarks_allowed():
                        logger.warning("unauthorized bookmark request: %s", message["type"])
                    elif message["type"] == "getmemories":
                        self._send_memories()
                    elif message["type"] == "savememory":
                        if "params" in message:
                            self._save_memory(message["params"])
                    elif message["type"] == "deletememory":
                        if "params" in message and "name" in message["params"]:
                            self._delete_memory(message["params"]["name"])
                elif message["type"] == "connectionproperties":
                    if "params" in message:
                        self.connectionProperties = message["params"]
                        if self.dsp:
                            self.getDsp().setProperties(self.connectionProperties)

            else:
                logger.warning("received message without type: {0}".format(message))

        except json.JSONDecodeError:
            logger.warning("message is not json: {0}".format(message))

    # the raw-json handling lives in owrx.bands, shared with the settings page

    def _send_bandplan(self):
        self.write_bandplan(Bandplan.getSharedInstance().listEntries())

    def _save_bandplan_entry(self, params):
        try:
            ok, message = Bandplan.getSharedInstance().saveEntry(
                params.get("modulation"), params.get("frequency", 0), params.get("original")
            )
            if ok:
                logger.info("bandplan entry saved by %s: %s", self.user.name, params.get("modulation"))
            self.write_bandplan_result(ok, message)
            if ok:
                self._send_bandplan()
        except Exception as e:
            logger.exception("Failed to save bandplan entry")
            self.write_bandplan_result(False, "Failed to save: {0}".format(e))

    def _delete_bandplan_entry(self, params):
        try:
            ok, message = Bandplan.getSharedInstance().deleteEntry(
                params.get("band"), params.get("modulation"), params.get("frequency", 0)
            )
            if ok:
                logger.info("bandplan entry deleted by %s: %s", self.user.name, params.get("modulation"))
            self.write_bandplan_result(ok, message)
            if ok:
                self._send_bandplan()
        except Exception as e:
            logger.exception("Failed to delete bandplan entry")
            self.write_bandplan_result(False, "Failed to delete: {0}".format(e))

    def _defaults_allowed(self):
        return self._bookmarks_allowed() and self.user.is_admin()

    def _save_defaults(self, params=None):
        """
        Persists the receiver panel values into settings.json, so that they
        survive a restart. Until now setcenterfreq/setsamplerate/setgain/
        setsquelch only changed the running properties.

        The values come from the client, which sends what the panel currently
        shows. Reading them back from self.sdr.props does not work for the
        squelch: that is a per-client demodulator setting and never appears
        among the SDR properties, so it was silently skipped and only the
        center frequency ended up being saved.
        """
        params = params or {}
        if self.sdr is None:
            self.write_defaults_saved(False, "No SDR device selected")
            return
        try:
            config = Config.get()
            sdr_id = self.sdr.getId()
            profile_id = self.sdr.getProfileId()
            sdrs = config["sdrs"]

            # PropertyLayer supports "in" and indexing, but has no .get()
            if sdr_id not in sdrs:
                self.write_defaults_saved(False, "Current device not found in the configuration")
                return
            device = sdrs[sdr_id]
            if "profiles" not in device or profile_id not in device["profiles"]:
                self.write_defaults_saved(False, "Current profile not found in the configuration")
                return

            profile = device["profiles"][profile_id]
            props = self.sdr.props
            saved = []

            def pick(key, fallback_key=None):
                # what the panel sent wins; the SDR properties are the fallback
                if key in params and params[key] not in (None, ""):
                    return params[key]
                source = fallback_key or key
                return props[source] if source in props else None

            center_freq = pick("center_freq")
            if center_freq is not None:
                profile["center_freq"] = int(center_freq)
                saved.append("center frequency")

            samp_rate = pick("samp_rate")
            if samp_rate is not None:
                profile["samp_rate"] = int(samp_rate)
                saved.append("sample rate")

            # Gain and squelch are deliberately NOT saved from here: they are set
            # from the settings pages, and writing them back from the receiver
            # panel would overwrite a deliberate choice made there.

            # the tuned frequency, so the receiver comes back where it was
            start_freq = pick("start_freq")
            if start_freq is not None:
                start_freq = int(start_freq)
                # out of range it would only produce a warning at startup
                if abs(start_freq - int(profile["center_freq"])) <= int(profile["samp_rate"]) / 2:
                    profile["start_freq"] = start_freq
                    saved.append("tuned frequency")

            start_mod = pick("start_mod")
            if start_mod:
                profile["start_mod"] = start_mod
                saved.append("modulation")

            if not saved:
                self.write_defaults_saved(False, "Nothing to save")
                return

            # the key has to be reassigned: the config layering does not notice
            # changes made in place inside nested structures
            config["sdrs"] = sdrs
            config.store()

            logger.info(
                "receiver defaults saved for %s/%s by %s: %s", sdr_id, profile_id, self.user.name, ", ".join(saved)
            )
            self.write_defaults_saved(True, "Defaults saved: " + ", ".join(saved))
        except Exception as e:
            logger.exception("Failed to save receiver defaults")
            self.write_defaults_saved(False, "Failed to save: {0}".format(e))

    def _bookmarks_allowed(self):
        # same criteria as AuthorizationMixin.isAuthorized()
        return (
            self.user is not None
            and self.user.is_enabled()
            and not self.user.must_change_password
        )

    def _send_memories(self):
        memories = self._load_memories()
        self.write_memories(memories)

    def _save_memory(self, params):
        name = params.get("name", "").strip()
        freq = int(params.get("frequency", 0))
        modulation = params.get("modulation", "nfm")
        if name and freq > 0:
            memory = self._store_memory(name, freq, modulation)
            if memory:
                self.write_memory_saved(memory)

    def _store_memory(self, name, freq, modulation):
        try:
            bookmarks = Bookmarks.getSharedInstance()
            self._remove_by_name(bookmarks, name)
            bookmarks.addBookmark(Bookmark({"name": name, "frequency": freq, "modulation": modulation}))
            bookmarks.store()
            logger.debug("Bookmark saved: %s -> %d Hz", name, freq)
            return {"name": name, "frequency": freq, "modulation": modulation}
        except Exception as e:
            logger.warning("Failed to save bookmark: %s", e)
            return None

    def _remove_by_name(self, bookmarks, name):
        for existing in [b for b in bookmarks.getBookmarks() if b.getName() == name]:
            bookmarks.removeBookmark(existing)

    def _delete_memory(self, name):
        try:
            bookmarks = Bookmarks.getSharedInstance()
            self._remove_by_name(bookmarks, name)
            bookmarks.store()
            self.write_memory_deleted(name)
            logger.debug("Bookmark deleted: %s", name)
        except Exception as e:
            logger.warning("Failed to delete bookmark: %s", e)

    def _load_memories(self):
        try:
            return [
                {"name": b.getName(), "frequency": b.getFrequency(), "modulation": b.getModulation()}
                for b in Bookmarks.getSharedInstance().getBookmarks()
            ]
        except Exception as e:
            logger.warning("Failed to load bookmarks: %s", e)
            return []

    def setSdr(self, id=None):
        next = None
        if id is not None:
            next = SdrService.getSource(id)
        if next is None:
            next = SdrService.getFirstSource()

        # exit condition: no change
        if next == self.sdr and next is not None:
            return

        self.stopDsp()
        self.stack.removeLayerByPriority(0)

        if self.sdr is not None:
            self.sdr.removeClient(self)

        self.sdr = next

        if next is None:
            # exit condition: no sdrs available
            logger.warning("no more SDR devices available")
            self.handleNoSdrsAvailable()
            return

        self.sdr.addClient(self)

    def handleSdrAvailable(self):
        self.getDsp().setProperties(self.connectionProperties)
        self.stack.replaceLayer(0, self.sdr.getProps())

        self.sdr.addSpectrumClient(self)

        # The DS badge belongs here and not in the initial configuration: that
        # one is assembled before the device is attached, so it cannot yet say
        # which input the radio is using, and a listener who reloaded the page
        # while the receiver was below the tuner's floor saw the badge vanish
        # even though nothing had changed. This runs whenever the source
        # becomes available - on the first connection and after every restart.
        self.write_config({"direct_sampling": autohf.current_mode(self.sdr)})

    def handleNoSdrsAvailable(self):
        self.write_sdr_error("No SDR Devices available")

    def close(self, error: bool = False):
        if self.sdr is not None:
            self.sdr.removeClient(self)
        self.stopDsp()
        CpuUsageThread.getSharedInstance().remove_client(self)
        ClientRegistry.getSharedInstance().removeClient(self)
        while self.configSubs:
            self.configSubs.pop().cancel()
        if self.bookmarkSub is not None:
            self.bookmarkSub.cancel()
            self.bookmarkSub = None
        super().close(error)

    def stopDsp(self):
        with self.dspLock:
            if self.dsp is not None:
                self.dsp.stop()
                self.dsp = None
        if self.sdr is not None:
            self.sdr.removeSpectrumClient(self)

    def getDsp(self):
        with self.dspLock:
            if self.dsp is None and self.sdr is not None:
                self.dsp = DspManager(self, self.sdr)
        return self.dsp

    def write_spectrum_data(self, data):
        self.mp_send(bytes([0x01]) + data)

    def write_dsp_data(self, data):
        self.send(bytes([0x02]) + data)

    def write_hd_audio(self, data):
        self.send(bytes([0x04]) + data)

    def write_s_meter_level(self, level):
        # may contain more than one sample, so only take the last 4 bytes = 1 float
        level, = struct.unpack('f', level[-4:])
        try:
            self.send({"type": "smeter", "value": level})
        except ValueError:
            logger.warning("unable to send smeter value: %s", str(level))

    def write_cpu_usage(self, usage):
        self.mp_send({"type": "cpuusage", "value": usage})

    def write_clients(self, clients):
        self.mp_send({"type": "clients", "value": clients})

    def write_secondary_fft(self, data):
        self.send(bytes([0x03]) + data)

    def write_secondary_demod(self, message):
        self.send({"type": "secondary_demod", "value": message})

    def write_secondary_dsp_config(self, cfg):
        self.send({"type": "secondary_config", "value": cfg})

    def write_config(self, cfg):
        self.send({"type": "config", "value": cfg})

    def write_profiles(self, profiles):
        self.send({"type": "profiles", "value": profiles})

    def write_memories(self, memories):
        self.send({"type": "memories", "value": memories})

    def write_memory_saved(self, memory):
        self.send({"type": "memory_saved", "value": memory})

    def write_memory_deleted(self, name):
        self.send({"type": "memory_deleted", "value": name})

    def write_features(self, features):
        self.send({"type": "features", "value": features})

    def write_metadata(self, metadata):
        self.send({"type": "metadata", "value": metadata})

    def write_dial_frequencies(self, frequencies):
        self.send({"type": "dial_frequencies", "value": frequencies})

    def write_bandplan(self, entries):
        self.send({"type": "bandplan_entries", "value": entries})

    def write_bandplan_result(self, ok, message):
        self.send({"type": "bandplan_result", "value": {"ok": ok, "message": message}})

    def write_defaults_saved(self, ok, message):
        self.send({"type": "defaults_saved", "value": {"ok": ok, "message": message}})

    def write_bookmarks(self, bookmarks):
        self.send({"type": "bookmarks", "value": bookmarks})

    def write_log_message(self, message):
        self.send({"type": "log_message", "value": message})

    def write_sdr_error(self, message):
        self.send({"type": "sdr_error", "value": message})

    def write_demodulator_error(self, message):
        self.send({"type": "demodulator_error", "value": message})

    def write_backoff_message(self, reason):
        self.send({"type": "backoff", "reason": reason})

    def write_modes(self, modes):
        def to_json(m):
            res = {
                "modulation": m.modulation,
                "name": m.name,
                "type": "digimode" if isinstance(m, DigitalMode) else "analog",
                "requirements": m.requirements,
                "squelch": m.squelch,
            }
            if m.bandpass is not None:
                res["bandpass"] = {"low_cut": m.bandpass.low_cut, "high_cut": m.bandpass.high_cut}
            if isinstance(m, DigitalMode):
                res["underlying"] = m.underlying
            return res

        self.send({"type": "modes", "value": [to_json(m) for m in modes]})


class MapConnection(OpenWebRxClient):
    def __init__(self, conn):
        super().__init__(conn)

        pm = Config.get()
        filtered_config = pm.filter(
            "map_tile_url",
            "map_tile_attribution",
            "receiver_gps",
            "map_position_retention_time",
            "receiver_name",
        )
        filtered_config.wire(self.write_config)

        self.write_config(filtered_config.__dict__())

        Map.getSharedInstance().addClient(self)

    def handleTextMessage(self, conn, message):
        pass

    def close(self, error: bool = False):
        Map.getSharedInstance().removeClient(self)
        super().close(error)

    def write_config(self, cfg):
        self.send({"type": "config", "value": cfg})

    def write_update(self, update):
        self.mp_send({"type": "update", "value": update})


class HandshakeMessageHandler(Handler):
    """
    This handler receives text messages, but will only respond to the second handshake string.
    As soon as a valid handshake is received, the handler replaces itself with the corresponding handler type.
    """

    def __init__(self, user=None):
        # user authenticated during the HTTP->websocket upgrade, used to
        # authorize the bookmark messages
        self.user = user

    def handleTextMessage(self, conn, message):
        if message[:16] == "SERVER DE CLIENT":
            meta = message[17:].split(" ")
            handshake = {v[0]: "=".join(v[1:]) for v in map(lambda x: x.split("="), meta)}

            logger.debug("client connection initialized")

            client = None
            if "type" in handshake:
                if handshake["type"] == "receiver":
                    client = OpenWebRxReceiverClient
                elif handshake["type"] == "map":
                    client = MapConnection
                else:
                    logger.warning("invalid connection type: %s", handshake["type"])

            if client is not None:
                logger.debug("handshake complete, handing off to %s", client.__name__)
                # hand off all further communication to the correspondig connection
                conn.send("CLIENT DE SERVER server=openwebrx version={version}".format(version=openwebrx_version))
                if client is OpenWebRxReceiverClient:
                    conn.setMessageHandler(client(conn, self.user))
                else:
                    conn.setMessageHandler(client(conn))
            else:
                logger.warning('invalid handshake received')
        else:
            logger.warning("not answering client request since handshake is not complete")

    def handleBinaryMessage(self, conn, data):
        pass

    def handleClose(self):
        pass
