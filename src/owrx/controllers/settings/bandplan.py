from owrx.controllers.template import WebpageController
from owrx.controllers.admin import AdminAuthorizationMixin
from owrx.controllers.settings import SettingsBreadcrumb
from owrx.bands import Bandplan
from owrx.breadcrumb import Breadcrumb, BreadcrumbItem, BreadcrumbMixin
from urllib.parse import parse_qs, urlencode
from html import escape

import logging

logger = logging.getLogger(__name__)


class BandplanController(AdminAuthorizationMixin, BreadcrumbMixin, WebpageController):
    def get_breadcrumb(self) -> Breadcrumb:
        return SettingsBreadcrumb().append(BreadcrumbItem("Bandplan", "settings/bandplan"))

    def template_variables(self):
        variables = super().template_variables()
        variables["bandplan"] = self.render_table()
        variables["message"] = self.render_message()
        return variables

    def render_message(self):
        if "msg" not in self.request.query:
            return ""
        key = self.request.query["msg"][0]
        ok = key.startswith("ok:")
        text = key[3:] if ok else key[6:] if key.startswith("error:") else ""
        if not text:
            return ""
        return '<div class="alert alert-{0}">{1}</div>'.format("success" if ok else "danger", escape(text))

    def render_table(self):
        entries = sorted(Bandplan.getSharedInstance().listEntries(), key=lambda e: e["frequency"])
        if not entries:
            return '<p class="text-muted">The bandplan is empty.</p>'
        return """
            <table class="table">
                <tr>
                    <th>Band</th>
                    <th>Mode</th>
                    <th class="frequency">Frequency</th>
                    <th>Actions</th>
                </tr>
                {rows}
            </table>
        """.format(rows="".join(self.render_entry(e) for e in entries))

    def render_entry(self, entry):
        return """
            <tr>
                <td>{band}</td>
                <td>{mode}</td>
                <td class="frequency">{freq} MHz</td>
                <td>
                    <form method="POST" action="bandplan" class="form-inline" style="gap:6px;">
                        <input type="hidden" name="action" value="save">
                        <input type="hidden" name="original_band" value="{band}">
                        <input type="hidden" name="original_mode" value="{mode}">
                        <input type="hidden" name="original_frequency" value="{raw}">
                        <input type="text" name="modulation" value="{mode}" class="form-control form-control-sm"
                               style="width:7em;" required>
                        <input type="number" name="frequency" value="{freq}" step="any"
                               class="form-control form-control-sm" style="width:9em;" required>
                        <button type="submit" class="btn btn-sm btn-primary">Save</button>
                    </form>
                    <form method="POST" action="bandplan" class="d-inline">
                        <input type="hidden" name="action" value="delete">
                        <input type="hidden" name="band" value="{band}">
                        <input type="hidden" name="modulation" value="{mode}">
                        <input type="hidden" name="frequency" value="{raw}">
                        <button type="submit" class="btn btn-sm btn-danger">Delete</button>
                    </form>
                </td>
            </tr>
        """.format(
            band=escape(entry["band"] or "", quote=True),
            mode=escape(entry["modulation"], quote=True),
            freq=self.format_frequency(entry["frequency"]),
            raw=entry["frequency"],
        )

    @staticmethod
    def format_frequency(hz):
        # 4 decimals when needed, so a 12.5 kHz raster is not truncated
        return "{0:.4f}".format(hz / 1e6).rstrip("0").rstrip(".")

    def _redirect(self, ok, text):
        self.send_redirect(
            "{0}settings/bandplan?{1}".format(
                self.get_document_root(), urlencode({"msg": ("ok:" if ok else "error:") + text})
            )
        )

    def processFormData(self):
        data = parse_qs(self.get_body().decode("utf-8"))
        data = {k: v[0] for k, v in data.items()}
        action = data.get("action", "")
        bandplan = Bandplan.getSharedInstance()

        try:
            if action == "delete":
                ok, message = bandplan.deleteEntry(
                    data.get("band"), data.get("modulation"), int(data.get("frequency", 0))
                )
                return self._redirect(ok, message)

            if action in ("save", "add"):
                frequency = int(round(float(data.get("frequency", 0)) * 1e6))
                original = None
                if data.get("original_mode"):
                    original = {
                        "band": data.get("original_band"),
                        "modulation": data.get("original_mode"),
                        "frequency": int(data.get("original_frequency", 0)),
                    }
                ok, message = bandplan.saveEntry(data.get("modulation"), frequency, original)
                return self._redirect(ok, message)
        except ValueError:
            return self._redirect(False, "Invalid frequency")
        except Exception as e:
            logger.exception("bandplan settings error")
            return self._redirect(False, str(e))

        self._redirect(False, "Unknown action")

    def indexAction(self):
        self.serve_template("settings/bandplan.html", **self.template_variables())
