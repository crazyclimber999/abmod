"""
Reading bookmark lists out of spreadsheets.

Repeater lists are published as spreadsheets, so importing one means reading
whichever format the publisher happened to use. Three are handled:

  * .xls  - the old binary Excel format, which needs xlrd. The one list this
            was written for (the Italian repeater list at ik2ane.it) is in it.
  * .xlsx - a zip of XML, so it is read with the standard library alone.
  * .csv  - read with the standard library, delimiter sniffed.

Nothing here decides what the columns mean: that is the operator's job, and
the importer offers the mapping as dropdowns. This module only turns a file
into a table of strings.
"""

from urllib.request import Request, urlopen
from urllib.parse import urlparse

import csv
import io
import re
import zipfile
import xml.etree.ElementTree as ET

import logging

logger = logging.getLogger(__name__)

# A repeater list is a few hundred kilobytes. The limit is here so a wrong URL
# cannot pull an unbounded download into the receiver's memory.
MAX_BYTES = 8 * 1024 * 1024
FETCH_TIMEOUT = 30
USER_AGENT = "OpenWebRX bookmark importer"

# how many rows are handed to the browser; the whole Italian list is about
# 1600 rows, so this leaves plenty of room without risking a huge page
MAX_ROWS = 20000



# The value meaning "leave these rows out entirely".
SKIP = "__skip__"

# Starting point for the modulation mapping, worked out from the legend inside
# the ik2ane repeater list (its "istruzioni" sheet) and from what this receiver
# can actually demodulate.
#
#   EL / EL-SVX  EchoLink and SvxLink are analogue FM with an internet link,
#                so the RF side is ordinary NFM.
#   ...+A        "sistema analogico/digitale": the repeater takes both, so the
#                analogue traffic on it is receivable even though the digital
#                is not.
#   WL           WinLink is data over FM; NFM lets you hear it, nothing decodes
#                it here.
#   the rest     digital only, and dmr/dstar/ysf/nxdn all need an AMBE codec
#                that this receiver does not have. Skipped by default rather
#                than imported as NFM, which would only produce bookmarks that
#                tune to a carrier nobody can decode.
#
# This is only the starting point: the operator edits it in the page and can
# store the result as the new default. When the AMBE question is settled, DMR
# becomes one dropdown away from being mapped to `dmr` for good.
DEFAULT_MODULATION_MAP = {
    "": "nfm",
    "EL": "nfm",
    "EL-SVX": "nfm",
    "WL": "nfm",
    "ALLMODE": "nfm",
    "C4FM+A": "nfm",
    "DMR+A": "nfm",
    "DS+A": "nfm",
    "NXDN+A": "nfm",
    "DMR": SKIP,
    "DS": SKIP,
    "C4FM": SKIP,
    "NXDN": SKIP,
    "TDMA": SKIP,
    "2D": SKIP,
    "3D": SKIP,
    "DS+NXDN": SKIP,
}

DEFAULT_FALLBACK = "nfm"

# The default source. Editable in the page, and the whole setup - this URL, the
# header row, the column mapping, the units, the regions and the modulations -
# can be stored as the new default from there.
DEFAULT_SOURCE_URL = "https://www.ik2ane.it/pontixls.xls"

# Every field the page remembers, with what it falls back to. Keeping the list
# here means the server validates exactly what the page offers, instead of the
# two drifting apart.
DEFAULT_IMPORT_SETUP = {
    "url": DEFAULT_SOURCE_URL,
    "headerRow": 0,
    # column indices; -1 means "not mapped". They are only a starting point:
    # a file with a different layout is re-guessed from its headers.
    "fields": {},
    "extras": [],
    "regions": [],
    "modmap": DEFAULT_MODULATION_MAP,
    "fallback": DEFAULT_FALLBACK,
    # The listenability filter's own settings, so they are remembered like the
    # rest of the page instead of being fixed in the template.
    "reach": {"margin": 6, "distance": 200, "horizon": False, "nearest": False},
}


def normalise_key(value):
    """Source values differ in case and padding between published lists."""
    return str(value or "").strip().upper()

class ImportError_(Exception):
    pass


def fetch(url):
    """Downloads a spreadsheet, refusing anything that is not plain http(s)."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ImportError_("Only http and https URLs can be fetched")
    if not parsed.netloc:
        raise ImportError_("That does not look like a URL")

    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=FETCH_TIMEOUT) as response:
        data = response.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ImportError_("The file is larger than {0} MB".format(MAX_BYTES // (1024 * 1024)))
    if not data:
        raise ImportError_("The server sent an empty file")
    return data


def detect_format(data, filename=None):
    if data[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        return "xls"
    if data[:4] == b"PK\x03\x04":
        return "xlsx"
    if filename:
        lower = filename.lower()
        for suffix in ("xlsx", "xls", "csv", "tsv"):
            if lower.endswith("." + suffix):
                return "csv" if suffix == "tsv" else suffix
    return "csv"


def parse(data, filename=None):
    """
    Returns (rows, sheets, sheet_used). Every cell is a string: the mapping
    step has to show the operator exactly what is in the file.
    """
    kind = detect_format(data, filename)
    if kind == "xls":
        return _parse_xls(data)
    if kind == "xlsx":
        return _parse_xlsx(data)
    return _parse_csv(data)


def _clean(value):
    if value is None:
        return ""
    if isinstance(value, float):
        # a spreadsheet stores every number as a float, and a frequency of
        # 144725 must not come out as "144725.0"
        if value == int(value):
            return str(int(value))
        return repr(value)
    return str(value).strip()


def _parse_xls(data):
    try:
        import xlrd
    except ImportError:
        raise ImportError_(
            "This is an old-format .xls file, which needs the xlrd library. "
            "Install it with: sudo apt install python3-xlrd — or save the file "
            "as .xlsx or .csv and upload that instead."
        )

    book = xlrd.open_workbook(file_contents=data)
    sheets = book.sheet_names()
    # the first sheet with more than a couple of rows: these files tend to
    # carry instructions and copyright notices on sheets of their own
    sheet = book.sheet_by_index(0)
    rows = []
    for r in range(min(sheet.nrows, MAX_ROWS)):
        rows.append([_clean(sheet.cell_value(r, c)) for c in range(sheet.ncols)])
    return rows, sheets, sheets[0] if sheets else ""


_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def _parse_xlsx(data):
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            for si in root.findall(_NS + "si"):
                shared.append("".join(t.text or "" for t in si.iter(_NS + "t")))

        names = [n for n in z.namelist() if n.startswith("xl/worksheets/sheet")]
        if not names:
            raise ImportError_("No worksheet found in the file")
        names.sort()
        root = ET.fromstring(z.read(names[0]))

        rows = []
        for row in root.iter(_NS + "row"):
            cells = {}
            for cell in row.findall(_NS + "c"):
                ref = cell.get("r") or ""
                match = re.match(r"([A-Z]+)", ref)
                index = _column_index(match.group(1)) if match else len(cells)
                value = cell.find(_NS + "v")
                text = value.text if value is not None else None
                if cell.get("t") == "s" and text is not None:
                    try:
                        text = shared[int(text)]
                    except (ValueError, IndexError):
                        text = ""
                elif cell.get("t") == "inlineStr":
                    inline = cell.find(_NS + "is")
                    text = "".join(t.text or "" for t in inline.iter(_NS + "t")) if inline is not None else ""
                cells[index] = _clean(text)
            if cells:
                width = max(cells) + 1
                rows.append([cells.get(i, "") for i in range(width)])
            else:
                rows.append([])
            if len(rows) >= MAX_ROWS:
                break

    width = max((len(r) for r in rows), default=0)
    rows = [r + [""] * (width - len(r)) for r in rows]
    return rows, ["sheet1"], "sheet1"


def _column_index(letters):
    index = 0
    for ch in letters:
        index = index * 26 + (ord(ch) - 64)
    return index - 1


def _parse_csv(data):
    for encoding in ("utf-8-sig", "latin-1"):
        try:
            text = data.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ImportError_("Could not read the file as text")

    sample = text[:8192]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel

    rows = []
    for row in csv.reader(io.StringIO(text), dialect):
        rows.append([_clean(c) for c in row])
        if len(rows) >= MAX_ROWS:
            break

    width = max((len(r) for r in rows), default=0)
    rows = [r + [""] * (width - len(r)) for r in rows]
    return rows, ["csv"], "csv"


def column_label(index):
    """0 -> A, 25 -> Z, 26 -> AA: the letters a spreadsheet shows."""
    label = ""
    index += 1
    while index > 0:
        index, remainder = divmod(index - 1, 26)
        label = chr(65 + remainder) + label
    return label


# Deliberately free of real callsigns, locators and place names: this file is
# published with the project and an example should not point at anybody.
SAMPLE_CSV = """Name,Frequency,Modulation,Region,Locator,Notes
N0CALL R0,145600000,nfm,Region One,AA00aa,Example repeater
N0CALL RU12,430300000,nfm,Region Two,AA00aa,Another one
Example beacon,144412500,usb,Region Two,AA00aa,Frequencies are in Hz here
"""
