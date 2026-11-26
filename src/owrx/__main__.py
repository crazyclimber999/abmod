import logging

# the linter will complain about this, but the logging must be configured before importing all the other modules
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

from http.server import HTTPServer
from owrx.http import RequestHandler
from owrx.config.core import CoreConfig
from owrx.config import Config
from owrx.config.commands import MigrateCommand
from owrx.feature import FeatureDetector
from owrx.sdr import SdrService
from owrx import idlegate
from socketserver import ThreadingMixIn
from owrx.service import Services
from owrx.websocket import WebSocketConnection
from owrx.reporting import ReportingEngine
from owrx.version import openwebrx_version
from owrx.audio.queue import DecoderQueue
from owrx.admin import add_admin_parser, run_admin_action
from owrx.aprsfi import AprsFiPoller
import signal
import argparse

# Imported here only to force it fully loaded before any thread starts.
# multiprocessing.context.Pipe imports multiprocessing.connection lazily,
# at the moment a websocket arrives; when that first happens while
# another thread is importing during start-up, the partially initialised
# module raises ImportError and the connection is dropped. Loading it up
# front costs nothing and removes the race.
import multiprocessing.connection  # noqa: F401


class ThreadedHttpServer(ThreadingMixIn, HTTPServer):
    pass


class SignalException(Exception):
    pass


def handleSignal(sig, frame):
    raise SignalException("Received Signal {sig}".format(sig=sig))


def main():
    parser = argparse.ArgumentParser(description="OpenWebRX - Open Source SDR Web App for Everyone!")
    parser.add_argument("-v", "--version", action="store_true", help="Show the software version")
    parser.add_argument("--debug", action="store_true", help="Set loglevel to DEBUG")

    moduleparser = parser.add_subparsers(title="Modules", dest="module")
    adminparser = moduleparser.add_parser("admin", help="Administration actions")
    add_admin_parser(adminparser)

    configparser = moduleparser.add_parser("config", help="Configuration actions")
    configcommandparser = configparser.add_subparsers(title="Commands", dest="command")

    migrateparser = configcommandparser.add_parser("migrate", help="Migrate configuration files")
    migrateparser.set_defaults(cls=MigrateCommand)

    args = parser.parse_args()

    # set loglevel to info for CLI commands
    if args.module is not None and not args.debug:
        logging.getLogger().setLevel(logging.INFO)

    if args.version:
        print("OpenWebRX version {version}".format(version=openwebrx_version))
        return 0

    if args.module == "admin":
        return run_admin_action(adminparser, args)

    if args.module == "config":
        return run_admin_action(configparser, args)

    return start_receiver()


def start_receiver():
    print(
        """

OpenWebRX - Open Source SDR Web App for Everyone!  | for license see LICENSE file in the package
_________________________________________________________________________________________________

Author contact info:    Jakob Ketterl, DD5JFK <dd5jfk@darc.de>
Documentation:          https://github.com/jketterl/openwebrx/wiki
Support and info:       https://groups.io/g/openwebrx

    """
    )

    logger.info("OpenWebRX version {0} starting up...".format(openwebrx_version))

    for sig in [signal.SIGINT, signal.SIGTERM]:
        signal.signal(sig, handleSignal)

    # config warmup
    Config.validateConfig()
    coreConfig = CoreConfig()

    featureDetector = FeatureDetector()
    failed = featureDetector.get_failed_requirements("core")
    if failed:
        logger.error(
            "you are missing required dependencies to run openwebrx. "
            "please check that the following core requirements are installed and up to date: %s",
            ", ".join(failed)
        )
        for f in failed:
            description = featureDetector.get_requirement_description(f)
            if description:
                logger.error("description for %s:\n%s", f, description)
        return 1

    # Get error messages about unknown / unavailable features as soon as possible
    # start up "always-on" sources right away
    SdrService.getAllSources()

    Services.start()

    # watches the configured callsigns on aprs.fi; does nothing until a key
    # and at least one callsign are configured
    AprsFiPoller.start()

    # nobody is connected yet, so start the clock that parks the receiver on
    # the APRS frequency; does nothing unless that rule is switched on
    idlegate.startup()

    try:
        server = ThreadedHttpServer(("0.0.0.0", coreConfig.get_web_port()), RequestHandler)
        server.serve_forever()
    except SignalException:
        pass

    WebSocketConnection.closeAll()
    Services.stop()
    AprsFiPoller.getSharedInstance().stop()
    SdrService.stopAllSources()
    ReportingEngine.stopAll()
    DecoderQueue.stopAll()

    return 0
