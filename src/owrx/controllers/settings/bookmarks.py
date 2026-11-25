from owrx.controllers.template import WebpageController
from owrx.controllers.admin import AdminAuthorizationMixin
from owrx.controllers.settings import SettingsBreadcrumb
from owrx.bookmarks import Bookmark, Bookmarks
from owrx.modes import Modes
from owrx.breadcrumb import Breadcrumb, BreadcrumbItem, BreadcrumbMixin
import json
import math

import logging

logger = logging.getLogger(__name__)


class BookmarksController(AdminAuthorizationMixin, BreadcrumbMixin, WebpageController):
    def get_breadcrumb(self) -> Breadcrumb:
        return SettingsBreadcrumb().append(BreadcrumbItem("Bookmark editor", "settings/bookmarks"))

    def template_variables(self):
        variables = super().template_variables()
        variables["bookmarks"] = self.render_table()
        return variables

    def render_table(self):
        bookmarks = Bookmarks.getSharedInstance().getBookmarks()
        emptyText = """
            <tr class="emptytext"><td colspan="5">
                No bookmarks in storage. You can add new bookmarks using the buttons below. 
            </td></tr>
        """

        return """
            <table class="table bookmark-table" data-modes='{modes}'>
                <tr>
                    <th class="select"><input type="checkbox" class="bookmark-select-all"
                        title="Select all"></th>
                    <th>Name</th>
                    <th class="frequency">Frequency</th>
                    <th>Modulation</th>
                    <th>Actions</th>
                </tr>
                {bookmarks}
            </table>
        """.format(
            bookmarks="".join(self.render_bookmark(b) for b in bookmarks) if bookmarks else emptyText,
            modes=json.dumps({m.modulation: m.name for m in Modes.getAvailableModes()}),
        )

    def render_bookmark(self, bookmark: Bookmark):
        def render_frequency(freq):
            suffixes = {
                0: "",
                3: "k",
                6: "M",
                9: "G",
                12: "T",
            }
            exp = 0
            if freq > 0:
                exp = int(math.log10(freq) / 3) * 3
            num = freq
            suffix = ""
            if exp in suffixes:
                num = freq / 10 ** exp
                suffix = suffixes[exp]
            return "{num:g} {suffix}Hz".format(num=num, suffix=suffix)

        mode = Modes.findByModulation(bookmark.getModulation())
        return """
            <tr data-id="{id}">
                <td class="select"><input type="checkbox" class="bookmark-select"></td>
                <td data-editor="name" data-value="{name}">{name}</td>
                <td data-editor="frequency" data-value="{frequency}" class="frequency">{rendered_frequency}</td>
                <td data-editor="modulation" data-value="{modulation}">{modulation_name}</td>
                <td>
                    <button type="button" class="btn btn-sm btn-danger bookmark-delete">delete</button>
                </td>
            </tr>
        """.format(
            id=id(bookmark),
            name=bookmark.getName(),
            # TODO render frequency in si units
            frequency=bookmark.getFrequency(),
            rendered_frequency=render_frequency(bookmark.getFrequency()),
            modulation=bookmark.getModulation() if mode is None else mode.modulation,
            modulation_name=bookmark.getModulation() if mode is None else mode.name,
        )

    def _findBookmark(self, bookmark_id):
        bookmarks = Bookmarks.getSharedInstance()
        try:
            return next(b for b in bookmarks.getBookmarks() if id(b) == bookmark_id)
        except StopIteration:
            return None

    def update(self):
        bookmark_id = int(self.request.matches.group(1))
        bookmark = self._findBookmark(bookmark_id)
        if bookmark is None:
            self.send_response("{}", content_type="application/json", code=404)
            return
        try:
            data = json.loads(self.get_body().decode("utf-8"))
            for key in ["name", "frequency", "modulation"]:
                if key in data:
                    value = data[key]
                    if key == "frequency":
                        value = int(value)
                    setattr(bookmark, key, value)
            Bookmarks.getSharedInstance().store()
            # TODO this should not be called explicitly... bookmarks don't have any event capability right now, though
            Bookmarks.getSharedInstance().notifySubscriptions(bookmark)
            self.send_response("{}", content_type="application/json", code=200)
        except json.JSONDecodeError:
            self.send_response("{}", content_type="application/json", code=400)

    def new(self):
        bookmarks = Bookmarks.getSharedInstance()

        def create(bookmark_data):
            # sanitize
            data = {
                "name": bookmark_data["name"],
                "frequency": int(bookmark_data["frequency"]),
                "modulation": bookmark_data["modulation"],
            }
            bookmark = Bookmark(data)
            bookmarks.addBookmark(bookmark)
            return {"bookmark_id": id(bookmark)}

        try:
            data = json.loads(self.get_body().decode("utf-8"))
            result = [create(b) for b in data]
            bookmarks.store()
            self.send_response(json.dumps(result), content_type="application/json", code=200)
        except json.JSONDecodeError:
            self.send_response("{}", content_type="application/json", code=400)

    def delete(self):
        bookmark_id = int(self.request.matches.group(1))
        bookmark = self._findBookmark(bookmark_id)
        if bookmark is None:
            self.send_response("{}", content_type="application/json", code=404)
            return
        bookmarks = Bookmarks.getSharedInstance()
        bookmarks.removeBookmark(bookmark)
        bookmarks.store()
        self.send_response("{}", content_type="application/json", code=200)

    def deleteSelected(self):
        """
        Removes several bookmarks at once.

        The per-bookmark DELETE would do the same thing one request at a time,
        which for a list of a few hundred means a few hundred round trips and a
        few hundred rewrites of the file. This removes them in one pass and
        writes once.
        """
        try:
            body = self.get_body(1024 * 1024)
            ids = json.loads(body.decode("utf-8")).get("ids")
        except Exception:
            self.send_response('{"error": "bad request"}', content_type="application/json", code=400)
            return
        if not isinstance(ids, list) or not ids:
            self.send_response('{"error": "nothing selected"}', content_type="application/json", code=400)
            return

        wanted = set()
        for value in ids:
            try:
                wanted.add(int(value))
            except (TypeError, ValueError):
                continue

        bookmarks = Bookmarks.getSharedInstance()
        current = list(bookmarks.getBookmarks())
        keep = [b for b in current if id(b) not in wanted]
        removed = len(current) - len(keep)

        if not removed:
            # A bookmark is identified by the address of its object in this
            # process, which is upstream's design and is not stable: anything
            # that makes the list reload from disk - another administrator, an
            # import - replaces every object and silently invalidates every
            # identifier the open page is holding. Measured: after one reload,
            # none of 230 still matched. Saying so beats deleting nothing and
            # reporting success.
            self.send_response(
                json.dumps({
                    "error": "None of those bookmarks are there any more. The list has changed "
                             "since this page was loaded - reload it and select them again.",
                    "removed": 0,
                    "total": len(current),
                }),
                content_type="application/json",
                code=409,
            )
            return

        bookmarks.bookmarks = keep
        bookmarks.store()

        self.send_response(
            json.dumps({"removed": removed, "total": len(keep)}),
            content_type="application/json",
            code=200,
        )

    def indexAction(self):
        self.serve_template("settings/bookmarks.html", **self.template_variables())
