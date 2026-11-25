from owrx.controllers import Controller
from owrx.details import ReceiverDetails
from string import Template
import pkg_resources


class TemplateController(Controller):
    def render_template(self, file, **vars):
        file_content = pkg_resources.resource_string("htdocs", file).decode("utf-8")
        template = Template(file_content)

        return template.safe_substitute(**vars)

    def serve_template(self, file, **vars):
        self.send_response(self.render_template(file, **vars), content_type="text/html")

    def default_variables(self):
        return {}


class WebpageController(TemplateController):
    def get_document_root(self):
        path_parts = [part for part in self.request.path[1:].split("/")]
        levels = max(0, len(path_parts) - 1)
        return "../" * levels

    def is_logged_in(self):
        user = self.current_user()
        return user is not None and user.is_enabled() and not user.must_change_password

    def current_user(self):
        # deferred import: owrx.controllers.admin imports session, which imports
        # this module. Importing it at the top would create a cycle.
        from owrx.controllers.admin import Authentication

        return Authentication().getUser(self.request)

    def _status_bar(self, text, href=None, background=None):
        """
        Styled like the progress bars of the status panel, but with its own class:
        the OpenWebRX progressbar component takes over every .openwebrx-progressbar
        element and replaces its content, which would wipe out the link.
        """
        style = ' style="background-color: {0};"'.format(background) if background else ""
        if href:
            return '<a class="openwebrx-user-bar" href="{href}"{style}>{text}</a>'.format(
                href=href, style=style, text=text
            )
        return '<div class="openwebrx-user-bar"{style}>{text}</div>'.format(style=style, text=text)

    def user_info(self):
        from html import escape

        user = self.current_user()
        root = self.get_document_root()

        if user is None:
            return self._status_bar("Login", href="{0}login?ref=%2F".format(root))

        role = "admin" if user.is_admin() else "user"
        return self._status_bar(
            "{name} ({role})".format(name=escape(user.name), role=role)
        ) + self._status_bar("Logout", href="{0}logout".format(root), background="#503000")

    def is_admin(self):
        user = self.current_user()
        return self.is_logged_in() and user.is_admin()

    def save_defaults_button(self):
        # it rewrites the receiver configuration for everyone, so it is not even
        # shown to the others; the websocket handler refuses them anyway
        if not self.is_admin():
            return ""
        return (
            '<div class="openwebrx-panel-line">'
            '<button class="openwebrx-button" onclick="save_defaults();"'
            ' style="width:100%; font-size:10px; padding:4px 0;">Save Defaults</button>'
            "</div>"
        )

    def _home_href(self):
        # on /map and /settings the document root is an empty string, and an
        # href="" would point at the page itself
        root = self.get_document_root()
        return root if root else "./"

    def receiver_button(self):
        root = self.get_document_root()
        content = (
            '<svg viewBox="0 0 80 80"><use xlink:href="{root}static/gfx/svg-defs.svg#panel-receiver"></use></svg>'
            "<br/>Receiver"
        ).format(root=root)

        if self.request.path == "/":
            return '<div class="button" data-toggle-panel="openwebrx-panel-receiver">{0}</div>'.format(content)

        # outside the receiver page data-toggle-panel has no panel to open: the
        # button was inert and there was no way back, since the logo links to
        # the openwebrx.de website
        return '<a class="button" href="{href}" title="Back to the receiver">{content}</a>'.format(
            href=self._home_href(), content=content
        )

    def bookmarks_button(self):
        root = self.get_document_root()
        content = (
            '<svg viewBox="0 0 80 80"><use xlink:href="{root}static/gfx/svg-defs.svg#bookmark"></use></svg>'
            "<br/>Bookmarks"
        ).format(root=root)

        # The header is shared with the settings, map and login pages, where the
        # bookmarks panel does not exist at all. Showing the button there would
        # promise something those pages cannot deliver, so it is only rendered on
        # the receiver page.
        if self.request.path != "/":
            return ""

        if not self.is_logged_in():
            # the button stays visible but leads to the login page; ref=/ sends
            # the user back to the receiver rather than to the settings
            return (
                '<a class="button openwebrx-bookmarks-button" href="{root}login?ref=%2F"'
                ' title="Bookmarks (login required)">{content}</a>'
            ).format(root=root, content=content)

        return (
            '<div class="button openwebrx-bookmarks-button" onclick="toggle_memory_panel();"'
            ' title="Bookmarks">{content}</div>'
        ).format(content=content)

    def header_variables(self):
        variables = {"document_root": self.get_document_root()}
        variables.update(ReceiverDetails().__dict__())
        variables["bookmarks_button"] = self.bookmarks_button()
        variables["receiver_button"] = self.receiver_button()
        return variables

    def bookmarks_panel(self):
        if not self.is_logged_in():
            return ""
        return self.render_template("include/bookmarks.include.html")

    def template_variables(self):
        header = self.render_template("include/header.include.html", **self.header_variables())
        return {
            "header": header,
            "bookmarks_panel": self.bookmarks_panel(),
            "save_defaults_button": self.save_defaults_button(),
            "user_info": self.user_info(),
            "document_root": self.get_document_root(),
        }


class IndexController(WebpageController):
    def indexAction(self):
        self.serve_template("index.html", **self.template_variables())


class MapController(WebpageController):
    def indexAction(self):
        # the map used to need a Google API key and was useless without one;
        # it is drawn with Leaflet on open tiles now, so it always works
        self.serve_template("map.html", **self.template_variables())
