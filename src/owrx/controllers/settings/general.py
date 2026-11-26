from owrx.controllers.settings import SettingsFormController
from owrx.form.section import Section
from owrx.config.core import CoreConfig
from owrx.form.input import (
    TextInput,
    NumberInput,
    CheckboxInput,
    FloatInput,
    TextAreaInput,
    DropdownInput,
    ExponentialInput,
    Option,
)
from owrx.form.input.converter import WaterfallColorsConverter, IntConverter, OptionalConverter
from owrx.form.input.aprs import AprsBeaconSymbols, AprsAntennaDirections
from owrx.form.input.receiverid import ReceiverKeysConverter
from owrx.form.input.gfx import AvatarInput, TopPhotoInput
from owrx.form.input.device import WaterfallLevelsInput, WaterfallAutoLevelsInput
from owrx.form.input.location import LocationInput
from owrx.waterfall import WaterfallOptions
from owrx.breadcrumb import Breadcrumb, BreadcrumbItem
from owrx.controllers.settings import SettingsBreadcrumb
import shutil
import os
import re
from glob import glob

import logging

logger = logging.getLogger(__name__)


class PasswordInput(TextInput):
    """
    A text field rendered as a password field.

    This only stops the value being read off the screen: it is still in the
    HTML of the page like every other setting, so the protection that matters
    is that the whole settings area is administrator-only.
    """

    def input_properties(self, value, errors):
        props = super().input_properties(value, errors)
        props["type"] = "password"
        return props


class GeneralSettingsController(SettingsFormController):
    def getTitle(self):
        return "General Settings"

    def get_breadcrumb(self) -> Breadcrumb:
        return SettingsBreadcrumb().append(BreadcrumbItem("General Settings", "settings/general"))

    def getSections(self):
        return [
            Section(
                "Receiver information",
                TextInput("receiver_name", "Receiver name"),
                TextInput("receiver_location", "Receiver location"),
                NumberInput(
                    "receiver_asl",
                    "Receiver elevation",
                    append="meters above mean sea level",
                ),
                TextInput("receiver_admin", "Receiver admin"),
                LocationInput("receiver_gps", "Receiver coordinates"),
                TextInput("photo_title", "Photo title"),
                TextAreaInput("photo_desc", "Photo description", infotext="HTML supported "),
            ),
            Section(
                "Receiver images",
                AvatarInput(
                    "receiver_avatar",
                    "Receiver Avatar",
                    infotext="For performance reasons, images are cached. "
                    + "It can take a few hours until they appear on the site.",
                ),
                TopPhotoInput(
                    "receiver_top_photo",
                    "Receiver Panorama",
                    infotext="For performance reasons, images are cached. "
                    + "It can take a few hours until they appear on the site.",
                ),
            ),
            Section(
                "Receiver limits",
                NumberInput(
                    "max_clients",
                    "Maximum number of clients",
                ),
            ),
            Section(
                "Receiver listings",
                TextAreaInput(
                    "receiver_keys",
                    "Receiver keys",
                    converter=ReceiverKeysConverter(),
                    infotext="Put the keys you receive on listing sites (e.g. "
                    + '<a href="https://www.receiverbook.de" target="_blank">Receiverbook</a>) here, one per line',
                ),
            ),
            Section(
                "Waterfall settings",
                DropdownInput(
                    "waterfall_scheme",
                    "Waterfall color scheme",
                    options=WaterfallOptions,
                ),
                TextAreaInput(
                    "waterfall_colors",
                    "Custom waterfall colors",
                    infotext="Please provide 6-digit hexadecimal RGB colors in HTML notation (#RRGGBB)"
                    + " or HEX notation (0xRRGGBB), one per line",
                    converter=WaterfallColorsConverter(),
                ),
                NumberInput(
                    "fft_fps",
                    "FFT speed",
                    infotext="This setting specifies how many lines are being added to the waterfall per second. "
                    + "Higher values will give you a faster waterfall, but will also use more CPU.",
                    append="frames per second",
                ),
                NumberInput("fft_size", "FFT size", append="bins"),
                FloatInput(
                    "fft_voverlap_factor",
                    "FFT vertical overlap factor",
                    infotext="If fft_voverlap_factor is above 0, multiple FFTs will be used for creating a line on the "
                    + "diagram.",
                ),
                WaterfallLevelsInput("waterfall_levels", "Waterfall levels"),
                WaterfallAutoLevelsInput(
                    "waterfall_auto_levels",
                    "Automatic adjustment margins",
                    infotext="Specifies the upper and lower dynamic headroom that should be added when automatically "
                    + "adjusting waterfall colors",
                ),
                NumberInput(
                    "waterfall_auto_min_range",
                    "Automatic adjustment minimum range",
                    append="dB",
                    infotext="Minimum dynamic range the waterfall should cover after automatically adjusting "
                    + "waterfall colors",
                ),
            ),
            Section(
                "Compression",
                DropdownInput(
                    "audio_compression",
                    "Audio compression",
                    options=[
                        Option("adpcm", "ADPCM"),
                        Option("none", "None"),
                    ],
                ),
                DropdownInput(
                    "fft_compression",
                    "Waterfall compression",
                    options=[
                        Option("adpcm", "ADPCM"),
                        Option("none", "None"),
                    ],
                ),
            ),
            Section(
                "Display settings",
                DropdownInput(
                    "tuning_precision",
                    "Tuning precision",
                    options=[Option(str(i), "{} Hz".format(10 ** i)) for i in range(0, 6)],
                    converter=IntConverter(),
                ),
            ),
            Section(
                "Map settings",
                TextInput(
                    "map_tile_url",
                    "Map tile URL",
                    infotext="Template of the tile server the map is drawn from, in the usual "
                    + "{z}/{x}/{y} scheme. Leave the default to use OpenStreetMap.",
                ),
                TextInput(
                    "map_tile_attribution",
                    "Map tile attribution",
                    infotext="Credit shown in the corner of the map. Whoever serves the tiles "
                    + "decides what has to appear here, so check their terms before changing it.",
                ),
                NumberInput(
                    "map_position_retention_time",
                    "Map retention time",
                    infotext="Specifies how log markers / grids will remain visible on the map",
                    append="s",
                ),
            ),
            Section(
                "APRS: positions from aprs.fi (incoming)",
                PasswordInput(
                    "aprsfi_api_key",
                    "aprs.fi API key",
                    infotext="Found under 'My account' on aprs.fi. The key stays on the server "
                    + "and is never sent to the browser. Leave empty to switch this off.",
                ),
                TextInput(
                    "aprsfi_callsigns",
                    "Callsigns to watch",
                    infotext="Comma separated, for example N0CALL-9, N0CALL-7. Their last known "
                    + "position is drawn on the map next to the stations the receiver hears "
                    + "itself. aprs.fi answers at most 20 callsigns per query.",
                ),
                NumberInput(
                    "aprsfi_poll_interval",
                    "Polling interval",
                    infotext="How often aprs.fi is asked. Their terms ask for no more than one "
                    + "query per minute, so anything below 60 s is treated as 60 s.",
                    append="s",
                ),
            ),
            Section(
                "APRS: igate (outgoing)",
                # These settings already existed upstream, on the "Spotting and
                # reporting" page. They were moved here, next to the aprs.fi
                # ones, because that is where an operator looks for anything
                # APRS - and removed from the other page, so there is exactly
                # one place that edits them.
                CheckboxInput(
                    "aprs_igate_enabled",
                    "Send received APRS data to the APRS-IS network",
                    infotext="This makes the receiver <strong>send</strong>, the opposite "
                    + "direction to the aprs.fi settings above. The APRS-IS network only "
                    + "accepts data from background decoders, so a packet service has to be "
                    + "running for anything to be forwarded.",
                ),
                TextInput(
                    "aprs_callsign",
                    "APRS callsign",
                    infotext="The callsign the receiver identifies itself with on APRS-IS. "
                    + "Leaving it at N0CALL would put the station on the network under a "
                    + "placeholder that is not yours.",
                ),
                TextInput("aprs_igate_server", "APRS-IS server"),
                PasswordInput(
                    "aprs_igate_password",
                    "APRS-IS passcode",
                    infotext="The numeric passcode for the callsign above, not a website "
                    + "password. Without it the server accepts the connection but marks it "
                    + "<em>unverified</em>, and silently discards everything sent.",
                ),
                NumberInput(
                    "aprs_igate_beacon_interval",
                    "Beacon interval",
                    infotext="How often the position is repeated. A fixed station does not need "
                    + "to shout: 30 minutes is normal, and anything under 10 is poor manners on "
                    + "a shared network. Clamped to between 5 and 240.",
                    append="min",
                ),
                CheckboxInput(
                    "aprs_igate_beacon",
                    "Send the receiver position to the APRS-IS network",
                    infotext="Check that the receiver location is correct under Receiver "
                    + "details before enabling this: the position becomes public.",
                ),
                DropdownInput(
                    "aprs_igate_symbol",
                    "APRS beacon symbol",
                    AprsBeaconSymbols,
                ),
                TextInput(
                    "aprs_igate_comment",
                    "APRS beacon text",
                    infotext="Sent as the APRS comment alongside the position",
                    converter=OptionalConverter(),
                ),
                NumberInput(
                    "aprs_igate_height",
                    "Antenna height",
                    infotext="Antenna height above average terrain (HAAT)",
                    append="m",
                    converter=OptionalConverter(),
                ),
                NumberInput(
                    "aprs_igate_gain",
                    "Antenna gain",
                    append="dBi",
                    converter=OptionalConverter(),
                ),
                DropdownInput("aprs_igate_dir", "Antenna direction", AprsAntennaDirections),
                # The igate and a listener want the receiver on two different
                # frequencies, and they never want it at the same time: the
                # packet service only runs where a band plan entry for it falls
                # inside the sampled window, so a listener who tunes elsewhere
                # takes the gateway down. These three let the receiver do both
                # jobs, each when the other is not needed.
                CheckboxInput(
                    "aprs_idle_enabled",
                    "Park on the APRS frequency when nobody is listening",
                    infotext="With nobody connected the receiver moves itself to the frequency "
                    + "below, so the gateway keeps working; the moment someone connects it goes "
                    + "back to the centre frequency saved for the profile. It needs <em>Keep "
                    + "device running at all times</em> on the device, otherwise the radio is "
                    + "simply off with nobody connected. Note that <strong>any</strong> visitor "
                    + "connecting stops the gateway, not just you.",
                ),
                ExponentialInput(
                    "aprs_idle_freq",
                    "Idle APRS frequency",
                    "Hz",
                    infotext="Where to park. It has to be a frequency the band plan has a "
                    + "packet entry for, otherwise no service starts there and the receiver "
                    + "waits on an empty channel. 144.800 MHz in Europe, 144.390 MHz in North "
                    + "America.",
                ),
                NumberInput(
                    "aprs_idle_timeout",
                    "Wait before parking",
                    infotext="A listener who reloads the page is gone and back within seconds, "
                    + "and parking in between would cost them a device restart. Clamped to "
                    + "between 1 and 240.",
                    append="min",
                ),
            ),
            Section(
                "Receiving antenna",
                NumberInput(
                    "receiver_antenna_height",
                    "Height above ground",
                    infotext="Where the antenna is, not where the receiver is. This decides how "
                    + "far the horizon is and what the signal has to clear on the way.",
                    append="m",
                ),
                NumberInput(
                    "receiver_antenna_gain",
                    "Gain",
                    infotext="2 dBi is a plain vertical. Only used by the listenability estimate.",
                    append="dBi",
                ),
                TextInput(
                    "receiver_antenna_pattern",
                    "Horizontal pattern",
                    infotext="Gain relative to the figure above, in dB, as numbers read evenly "
                    + "around the compass starting at north: eight values are one every 45 "
                    + "degrees, thirty-six are one every 10. For example "
                    + "<code>0,-3,-10,-18,-25,-18,-10,-3</code> is a beam pointing north. "
                    + "<strong>Leave it empty for an omnidirectional antenna</strong>, which is "
                    + "what is assumed when nothing is given.",
                    converter=OptionalConverter(),
                ),
            ),
            Section(
                "Listenability estimate",
                NumberInput(
                    "terrain_radius_km",
                    "Terrain data radius",
                    infotext="How far around the receiver elevation data is kept, for working out "
                    + "what the ground blocks. Roughly 1.3 MB of download and 0.4 MB on disk per "
                    + "kilometre of radius.",
                    append="km",
                ),
                NumberInput(
                    "propagation_remote_erp",
                    "Assumed transmitter power",
                    infotext="No repeater list carries the power of its stations, so one figure "
                    + "is assumed for all of them. 40 dBm is 10 W.",
                    append="dBm",
                ),
                NumberInput(
                    "propagation_remote_height",
                    "Assumed remote antenna height",
                    infotext="Above the ground at the far end. The ground itself is taken from "
                    + "the elevation data.",
                    append="m",
                ),
                NumberInput(
                    "propagation_sensitivity",
                    "Usable signal level",
                    infotext="The level at which a signal counts as listenable. -116 dBm is about "
                    + "what narrow FM needs to be readable.",
                    append="dBm",
                ),
            ),
        ]

    def remove_existing_image(self, image_id):
        config = CoreConfig()
        # remove all possible file extensions
        for ext in ["png", "jpg", "webp"]:
            try:
                os.unlink("{}/{}.{}".format(config.get_data_directory(), image_id, ext))
            except FileNotFoundError:
                pass

    def handle_image(self, data, image_id):
        if image_id in data:
            config = CoreConfig()
            if data[image_id] == "restore":
                self.remove_existing_image(image_id)
            elif data[image_id]:
                if not data[image_id].startswith(image_id):
                    logger.warning("invalid file name: %s", data[image_id])
                else:
                    # get file extension (at least 3 characters)
                    # should be all lowercase since they are set by the upload script
                    pattern = re.compile(".*\\.([a-z]{3,})$")
                    matches = pattern.match(data[image_id])
                    if matches is None:
                        logger.warning("could not determine file extension for %s", image_id)
                    else:
                        self.remove_existing_image(image_id)
                        ext = matches.group(1)
                        data_file = "{}/{}.{}".format(config.get_data_directory(), image_id, ext)
                        temporary_file = "{}/{}".format(config.get_temporary_directory(), data[image_id])
                        shutil.copy(temporary_file, data_file)
            del data[image_id]
            # remove any accumulated temporary files on save
            for file in glob("{}/{}*".format(config.get_temporary_directory(), image_id)):
                os.unlink(file)

    def processData(self, data):
        # Image handling
        for img in ["receiver_avatar", "receiver_top_photo"]:
            self.handle_image(data, img)
        # special handling for waterfall colors: custom colors only stay in config if custom color scheme is selected
        if "waterfall_scheme" in data:
            scheme = WaterfallOptions(data["waterfall_scheme"])
            if scheme is not WaterfallOptions.CUSTOM and "waterfall_colors" in data:
                data["waterfall_colors"] = None
        super().processData(data)
