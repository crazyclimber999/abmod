from owrx.controllers.settings import SettingsFormController, SettingsBreadcrumb
from owrx.form.section import Section
from owrx.form.input.converter import OptionalConverter
from owrx.form.input.aprs import AprsBeaconSymbols, AprsAntennaDirections
from owrx.form.input import TextInput, CheckboxInput, DropdownInput, NumberInput
from owrx.breadcrumb import Breadcrumb, BreadcrumbItem


class ReportingController(SettingsFormController):
    def getTitle(self):
        return "Spotting and reporting"

    def get_breadcrumb(self) -> Breadcrumb:
        return SettingsBreadcrumb().append(BreadcrumbItem("Spotting and reporting", "settings/reporting"))

    def getSections(self):
        return [
            # The APRS-IS section used to be here. It now lives under
            # General settings, next to the other APRS settings, so that one
            # page owns these keys instead of two pages editing the same ones.
            Section(
                "pskreporter settings",
                CheckboxInput(
                    "pskreporter_enabled",
                    "Enable sending spots to pskreporter.info",
                ),
                TextInput(
                    "pskreporter_callsign",
                    "pskreporter callsign",
                    infotext="This callsign will be used to send spots to pskreporter.info",
                ),
                TextInput(
                    "pskreporter_antenna_information",
                    "Antenna information",
                    infotext="Antenna description to be sent along with spots to pskreporter",
                    converter=OptionalConverter(),
                ),
            ),
            Section(
                "WSPRnet settings",
                CheckboxInput(
                    "wsprnet_enabled",
                    "Enable sending spots to wsprnet.org",
                ),
                TextInput(
                    "wsprnet_callsign",
                    "wsprnet callsign",
                    infotext="This callsign will be used to send spots to wsprnet.org",
                ),
            ),
        ]
